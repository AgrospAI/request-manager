from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import overload

from pydantic import BaseModel

from request_manager.types import Request, Response

type IndependentFetchFn = Callable[[], Request]
type DependentFetchFn = Callable[[Response], Request]

type RawExpectFn = Callable[[Response[bytes]], None]
type ValidatedExpectFn[T: BaseModel] = Callable[[Response[T]], None]

type FetchCallback = IndependentCallback | DependentCallback
type ExpectCallback = RawExpectCallback | ValidatedExpectCallback[BaseModel]


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


@dataclass(slots=True)
class Callbacks:
    fetching: list[FetchCallback] = field(default_factory=list)
    expecting: dict[FetchCallback, list[ExpectCallback]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # --- Function decorators ---

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

    def fetch(
        self,
        depends_on: FetchCallback | None = None,
    ):
        if depends_on is None:

            def _inner_independent(fn: IndependentFetchFn, /) -> IndependentCallback:
                callback = IndependentCallback(fn)
                self.fetching.append(callback)
                return callback

            return _inner_independent

        def _inner_dependent(fn: DependentFetchFn, /) -> DependentCallback:
            callback = DependentCallback(fn, depends_on)
            self.fetching.append(callback)
            return callback

        return _inner_dependent

    @overload
    def expect(
        self,
        fetch: FetchCallback,
        type_: None = None,
    ) -> Callable[[RawExpectFn], RawExpectCallback]: ...

    @overload
    def expect(
        self,
        fetch: FetchCallback,
        type_: type[BaseModel],
    ) -> Callable[
        [ValidatedExpectFn[BaseModel]], ValidatedExpectCallback[BaseModel]
    ]: ...

    def expect(
        self,
        fetch: FetchCallback,
        type_: type[BaseModel] | None = None,
    ):
        if type_ is None:

            def _inner_unvalidated(
                fn: RawExpectFn,
                /,
            ) -> RawExpectCallback:
                callback = RawExpectCallback(fn)
                self.expecting[fetch].append(callback)
                return callback

            return _inner_unvalidated

        def _inner_validated(
            fn: ValidatedExpectFn[BaseModel],
            /,
        ) -> ValidatedExpectCallback:
            callback = ValidatedExpectCallback[BaseModel](fn, type_)
            self.expecting[fetch].append(callback)
            return callback

        return _inner_validated

    # ---
