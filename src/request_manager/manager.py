from __future__ import annotations

from dataclasses import dataclass, field

from request_manager.callbacks import (
    Callbacks,
    DependentCallback,
    FetchCallback,
    IndependentCallback,
    RawExpectCallback,
    ValidatedExpectCallback,
)
from request_manager.exceptions import RequestManagerException
from request_manager.logger import logger, setup_logging
from request_manager.types import ClientContext, Response


@dataclass(slots=True)
class Runtime:
    client: ClientContext | None = None


@dataclass(frozen=True, slots=True)
class RequestManager:
    runtime: Runtime = field(default_factory=Runtime)
    callbacks: Callbacks = field(default_factory=Callbacks)

    error: type[RequestManagerException] = field(default=RequestManagerException)

    fetch = property(lambda self: self.callbacks.fetch)
    expect = property(lambda self: self.callbacks.expect)

    def __post_init__(self) -> None:
        setup_logging()

    def client(self, client: ClientContext):
        self.runtime.client = client
        return client

    async def run(self) -> None:
        if self.runtime.client is None:
            raise RequestManagerException("There is no client configured")

        async with self.runtime.client as client:
            logger.info("Fetching %d sources", len(self.callbacks.fetching))

            responses: dict[FetchCallback, Response] = {}
            pending = list(self.callbacks.fetching)

            while pending:
                progressed = False

                for source in list(pending):
                    match source:
                        case IndependentCallback(fn=fn):
                            request = fn()

                        case DependentCallback(fn=fn, dependency=dep):
                            if dep not in responses:
                                continue  # dependency not resolved yet, keep going

                            request = fn(responses[dep])

                    response = await client.fetch(request)

                    for expected in self.callbacks.expecting[source]:
                        match expected:
                            case ValidatedExpectCallback(fn=expect_fn, type_=type_):
                                expect_fn(client.validate(response, type_=type_))
                            case RawExpectCallback(fn=expect_fn):
                                expect_fn(response)

                    responses[source] = response
                    pending.remove(source)
                    progressed = True

                if not progressed:
                    raise RequestManagerException(
                        "Circular or unresolved fetch dependency"
                    )
