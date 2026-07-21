from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, cast, overload

from pydantic import BaseModel

from request_manager.exceptions import RequestManagerException
from request_manager.logger import logger, setup_logging
from request_manager.types import ClientContext, Request, Response

type ClientFn = Callable[[], ClientContext]

type IndependentFetchFn = Callable[[], Request]
type DependentFetchFn = Callable[[Response], Request]

type RawExpectFn = Callable[[Response[bytes]], None]
type ValidatedExpectFn[T: BaseModel] = Callable[[Response[T]], None]


@dataclass(frozen=True)
class RawExpectCallback:
    fn: RawExpectFn


@dataclass(frozen=True)
class ValidatedExpectCallback[T: BaseModel]:
    fn: ValidatedExpectFn[T]
    type_: type[T]


@dataclass(frozen=True)
class IndependentCallback:
    fn: IndependentFetchFn


@dataclass(frozen=True)
class DependentCallback:
    fn: DependentFetchFn
    dependency: FetchCallback


type FetchFn = IndependentFetchFn | DependentFetchFn
type ExpectFn[T: BaseModel | bytes = bytes] = Callable[[Response[T]], None]

type FetchCallback = IndependentCallback | DependentCallback
type ExpectCallback = RawExpectCallback | ValidatedExpectCallback[BaseModel]


@dataclass(slots=True)
class Callbacks:
    client: ClientFn | None = None
    fetching: list[FetchCallback] = field(default_factory=list)
    expecting: dict[FetchCallback, list[ExpectCallback]] = field(
        default_factory=lambda: defaultdict(list)
    )


@dataclass(frozen=True, slots=True)
class RequestManager:
    callbacks: Callbacks = field(default_factory=Callbacks)

    def __post_init__(self) -> None:
        setup_logging()

    # --- Function decorators ---

    def client(self, fn: ClientFn):
        self.callbacks.client = fn
        return fn

    @overload
    def fetch(
        self,
        depends_on: None = None,
    ) -> Callable[[IndependentFetchFn], IndependentCallback]: ...

    @overload
    def fetch(
        self,
        depends_on: FetchCallback,
    ) -> Callable[[DependentFetchFn], DependentCallback]: ...

    def fetch(self, depends_on: FetchCallback | None = None):
        def __inner(fn: FetchFn) -> FetchCallback:
            callback = (
                IndependentCallback(cast(IndependentFetchFn, fn))
                if depends_on is None
                else DependentCallback(cast(DependentFetchFn, fn), depends_on)
            )

            self.callbacks.fetching.append(callback)

            return callback

        return __inner

    @overload
    def expect(
        self,
        fetch: FetchCallback,
        type_: None = None,
    ) -> Callable[[RawExpectFn], RawExpectFn]: ...

    @overload
    def expect[T: BaseModel](
        self,
        fetch: FetchCallback,
        type_: type[T],
    ) -> Callable[[ValidatedExpectFn[T]], ValidatedExpectFn[T]]: ...

    def expect(self, fetch: FetchCallback, type_: type[BaseModel] | None = None):
        def inner(fn):
            callback = (
                RawExpectCallback(fn=fn)
                if type_ is None
                else ValidatedExpectCallback(fn=fn, type_=type_)
            )
            self.callbacks.expecting[fetch].append(callback)
            return fn

        return inner

    # ---

    async def run(self) -> None:
        if self.callbacks.client is None:
            raise RequestManagerException("There is no client configured")

        async with self.callbacks.client() as client:
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
