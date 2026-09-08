from __future__ import annotations

import argparse
import asyncio
from abc import ABC
from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from typing import cast, overload

from pydantic import BaseModel

from request_manager.arguments import load_arguments
from request_manager.exceptions import RequestManagerException
from request_manager.logger import setup_logging
from request_manager.runners import DependantRunner
from request_manager.types import (
    Callbacks,
    ClientContext,
    DependentCallback,
    DependentFetchFn,
    ExpectCallback,
    FetchCallback,
    IndependentCallback,
    IndependentFetchFn,
    RawExpectCallback,
    RawExpectFn,
    ResponseType,
    ValidatedExpectCallback,
    ValidatedExpectFn,
)


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
    def fetch[T: ResponseType = bytes](
        self,
        depends_on: FetchCallback[T],
        type_: type[T],
    ) -> Callable[[DependentFetchFn[T]], DependentCallback[T]]: ...

    def fetch[T: ResponseType = bytes](
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
                cast("DependentCallback[ResponseType]", callback)
            )
            return callback

        return _inner_dependent

    @overload
    def expect[T: ResponseType = bytes](
        self,
        fetch: FetchCallback[T],
        type_: None = None,
    ) -> Callable[[RawExpectFn], RawExpectCallback]: ...

    @overload
    def expect[T: ResponseType = bytes](
        self,
        fetch: FetchCallback[T],
        type_: type[T],
    ) -> Callable[[ValidatedExpectFn[T]], ValidatedExpectCallback[T]]: ...

    def expect[T: ResponseType = bytes](
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
                    cast("FetchCallback[ResponseType]", fetch)
                ].append(callback)
                return callback

            return _inner_not_validated

        def _inner_validated(
            fn: ValidatedExpectFn[T],
            /,
        ) -> ValidatedExpectCallback[T]:
            callback = ValidatedExpectCallback(fn, type_)
            self.callbacks.expecting[cast("FetchCallback[ResponseType]", fetch)].append(
                cast("ExpectCallback[ResponseType]", callback)
            )
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

        async with self.runtime.client as client:
            runner = DependantRunner(client=client, callbacks=self.callbacks)

            async with asyncio.TaskGroup() as tg:
                for source in self.callbacks.fetching:
                    tg.create_task(runner.run(source))


@dataclass(frozen=True, slots=True, kw_only=True)
class _ArgsRequestManager[ArgsT: BaseModel](RequestManager):
    arguments: ArgsT


@dataclass(frozen=True, slots=True, kw_only=True)
class _NoArgsRequestManager(RequestManager): ...
