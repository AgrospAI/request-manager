from __future__ import annotations

import asyncio
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
from request_manager.logger import setup_logging
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

        responses: dict[FetchCallback, Response] = {}
        futures: dict[FetchCallback, asyncio.Future[Response]] = {
            source: asyncio.get_event_loop().create_future()
            for source in self.callbacks.fetching
        }

        async with self.runtime.client as client:

            async def _run(source: FetchCallback) -> None:
                match source:
                    case IndependentCallback(fn=fn):
                        request = fn()
                    case DependentCallback(fn=fn, dependency=dep):
                        if dep not in futures:
                            raise RequestManagerException("Unresolved fetch dependency")
                        request = fn(await futures[dep])

                response = await client.fetch(request)

                for expected in self.callbacks.expecting[source]:
                    match expected:
                        case ValidatedExpectCallback(fn=expect_fn, type_=type_):
                            expect_fn(client.validate(response, type_=type_))
                        case RawExpectCallback(fn=expect_fn):
                            expect_fn(response)

                responses[source] = response
                futures[source].set_result(response)

            async with asyncio.TaskGroup() as tg:
                for source in self.callbacks.fetching:
                    tg.create_task(_run(source))
