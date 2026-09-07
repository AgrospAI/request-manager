from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
import time
from abc import ABC
from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from typing import cast, overload

from pydantic import BaseModel

from request_manager.arguments import load_arguments
from request_manager.callbacks import (
    Callbacks,
    DependentCallback,
    DependentFetchFn,
    ExpectCallback,
    FetchCallback,
    IndependentCallback,
    IndependentFetchFn,
    RawExpectCallback,
    RawExpectFn,
    ValidatedExpectCallback,
    ValidatedExpectFn,
)
from request_manager.exceptions import RequestManagerException
from request_manager.logger import setup_logging
from request_manager.types import ClientContext, ClientError, Response


@dataclass(slots=True)
class Runtime:
    client: ClientContext | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestManager(ABC):
    client: InitVar[ClientContext | None] = field(default=None)
    parser: argparse.ArgumentParser = field(init=False)

    runtime: Runtime = field(default_factory=Runtime)
    callbacks: Callbacks = field(default_factory=Callbacks)

    error: type[RequestManagerException] = field(default=RequestManagerException)

    # --- Function decorators ---

    @overload
    def fetch(
        self,
        depends_on: None = None,
        type_: None = None,
    ) -> Callable[[IndependentFetchFn], IndependentCallback]: ...

    @overload
    def fetch[T: BaseModel | bytes = bytes](
        self,
        depends_on: FetchCallback[T],
        type_: type[T],
    ) -> Callable[[DependentFetchFn[T]], DependentCallback[T]]: ...

    def fetch[T: BaseModel | bytes = bytes](
        self,
        depends_on: FetchCallback[T] | None = None,
        type_: type[T] | None = None,
    ):
        if depends_on is None:

            def _inner_independent(fn: IndependentFetchFn, /) -> IndependentCallback:
                callback = IndependentCallback(fn)
                self.callbacks.fetching.append(callback)
                return callback

            return _inner_independent

        if type_ is None:
            raise RuntimeError("Must define 'type_' alongside 'depends_on'")

        def _inner_dependent(fn: DependentFetchFn[T], /) -> DependentCallback[T]:
            callback = DependentCallback(fn, depends_on, type_)
            self.callbacks.fetching.append(
                cast("DependentCallback[BaseModel | bytes]", callback)
            )
            return callback

        return _inner_dependent

    @overload
    def expect[T: BaseModel | bytes = bytes](
        self,
        fetch: FetchCallback[T],
        type_: None = None,
    ) -> Callable[[RawExpectFn], RawExpectCallback]: ...

    @overload
    def expect[T: BaseModel | bytes = bytes](
        self,
        fetch: FetchCallback[T],
        type_: type[T],
    ) -> Callable[[ValidatedExpectFn[T]], ValidatedExpectCallback[T]]: ...

    def expect[T: BaseModel | bytes = bytes](
        self,
        fetch: FetchCallback[T],
        type_: type[T] | None = None,
    ):
        if type_ is None:

            def _inner_not_validated(
                fn: RawExpectFn,
                /,
            ) -> RawExpectCallback:
                callback = RawExpectCallback(fn)
                self.callbacks.expecting[
                    cast("FetchCallback[BaseModel | bytes]", fetch)
                ].append(callback)
                return callback

            return _inner_not_validated

        def _inner_validated(
            fn: ValidatedExpectFn[T],
            /,
        ) -> ValidatedExpectCallback[T]:
            callback = ValidatedExpectCallback[T](fn, type_)
            self.callbacks.expecting[
                cast("FetchCallback[BaseModel | bytes]", fetch)
            ].append(cast("ExpectCallback[BaseModel | bytes]", callback))
            return callback

        return _inner_validated

    # ---

    @overload
    @classmethod
    def create[ArgsT: BaseModel](
        cls,
        *,
        client: ClientContext | None = None,
        arguments: type[ArgsT],
    ) -> _ArgsRequestManager[ArgsT]: ...

    @overload
    @classmethod
    def create(
        cls,
        *,
        client: ClientContext | None = None,
        arguments: None,
    ) -> _NoArgsRequestManager: ...

    @classmethod
    def create[ArgsT: BaseModel](
        cls,
        *,
        client: ClientContext | None = None,
        arguments: type[ArgsT] | None,
    ) -> _NoArgsRequestManager | _ArgsRequestManager[ArgsT]:
        return (
            _NoArgsRequestManager(client=client)
            if arguments is None
            else _ArgsRequestManager(
                client=client,
                arguments=load_arguments(arguments),
            )
        )

    def __post_init__(self, client: ClientContext | None) -> None:
        setup_logging()

        if client is not None:
            self.set_client(client)

    def set_client(self, client: ClientContext) -> ClientContext:
        self.runtime.client = client
        return client

    def run(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            loop.create_task(self.arun())
        else:
            asyncio.run(self.arun())

    async def arun(self) -> None:
        if self.runtime.client is None:
            raise RequestManagerException("There is no client configured")

        responses: dict[FetchCallback, Response] = {}
        futures: dict[
            FetchCallback[BaseModel | bytes],
            asyncio.Future[Response[BaseModel | bytes]],
        ] = {
            source: cast(
                "asyncio.Future[Response[BaseModel | bytes]]",
                asyncio.get_event_loop().create_future(),
            )
            for source in self.callbacks.fetching
        }

        async with self.runtime.client as client:

            async def _run[T: BaseModel | bytes](source: FetchCallback[T]) -> None:

                match source:
                    case IndependentCallback(fn=fn):
                        request = fn()
                    case DependentCallback(fn=fn, dependency=dep, type_=type_):
                        if dep not in futures:
                            raise RequestManagerException("Unresolved fetch dependency")

                        if type_ is bytes:
                            request = fn(await futures[dep])  # type: ignore
                        else:
                            request = fn(
                                client.validate(await futures[dep], type_=type_)  # type: ignore
                            )

                if inspect.isawaitable(request):
                    request = await request

                print(
                    f"[{source.fn.__name__}] Will retry for {request.options.retries} attempts or {request.options.timeout} seconds"
                )

                start = time.monotonic()
                deadline = (
                    time.monotonic() + request.options.timeout
                    if request.options.timeout
                    else None
                )
                attempt = 0

                while True:
                    attempt += 1
                    is_exhausted_attempts = (
                        request.options.retries != -1
                        and attempt > request.options.retries + 1
                    )
                    is_exhausted_time = (
                        deadline is not None and time.monotonic() >= deadline
                    )
                    elapsed = time.monotonic() - start

                    try:
                        response = await client.fetch(request)

                        if (
                            request.options.is_success is not None
                            and not request.options.is_success(response)
                        ):
                            raise ClientError(
                                f"Attempt {attempt} [{elapsed:07.3f}s]: Response not successful"
                            )

                        break
                    except ClientError as e:
                        print(e, file=sys.stderr)

                        if is_exhausted_attempts or is_exhausted_time:
                            raise ClientError(
                                f"Response unsuccessful after {attempt} attempt(s) in {request.options.timeout} seconds"
                            )

                        backoff = request.options.retry_backoff * attempt
                        if deadline is not None:
                            backoff = min(backoff, deadline - time.monotonic())

                        print(f"Retrying after {backoff:.1f} seconds ...")
                        await asyncio.sleep(max(backoff, 0))

                for expected in self.callbacks.expecting[
                    cast("FetchCallback[BaseModel | bytes]", source)
                ]:
                    match expected:
                        case ValidatedExpectCallback(fn=expect_fn, type_=type__):
                            expect_fn(client.validate(response, type_=type__))  # type: ignore
                        case RawExpectCallback(fn=expect_fn):
                            expect_fn(response)

                responses[source] = response  # type: ignore
                futures[source].set_result(response)  # type: ignore

            async with asyncio.TaskGroup() as tg:
                for source in self.callbacks.fetching:
                    tg.create_task(_run(source))


@dataclass(frozen=True, slots=True, kw_only=True)
class _ArgsRequestManager[ArgsT: BaseModel](RequestManager):
    arguments: ArgsT


@dataclass(frozen=True, slots=True, kw_only=True)
class _NoArgsRequestManager(RequestManager): ...
