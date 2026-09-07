from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Awaitable

from pydantic import BaseModel

from request_manager.types import Request, Response

type MaybeAwaitable[T] = T | Awaitable[T]

type IndependentFetchFn = Callable[[], MaybeAwaitable[Request]]
type DependentFetchFn[T: BaseModel | bytes = bytes] = Callable[
    [Response[T]], MaybeAwaitable[Request]
]

type RawExpectFn = Callable[[Response[bytes]], MaybeAwaitable[None]]
type ValidatedExpectFn[T: BaseModel | bytes = bytes] = Callable[
    [Response[T]], MaybeAwaitable[None]
]

type FetchCallback[T: BaseModel | bytes = bytes] = (
    IndependentCallback | DependentCallback[T]
)
type ExpectCallback[T: BaseModel | bytes = bytes] = (
    RawExpectCallback | ValidatedExpectCallback[T]
)


@dataclass(frozen=True)
class RawExpectCallback:
    fn: RawExpectFn


@dataclass(frozen=True)
class ValidatedExpectCallback[T: BaseModel | bytes = bytes]:
    fn: ValidatedExpectFn[T]
    type_: type[T]


@dataclass(frozen=True)
class IndependentCallback:
    fn: IndependentFetchFn


@dataclass(frozen=True)
class DependentCallback[T: BaseModel | bytes = bytes]:
    fn: DependentFetchFn[T]
    dependency: FetchCallback[T]
    type_: type[T]


@dataclass(slots=True)
class Callbacks:
    fetching: list[FetchCallback[BaseModel | bytes]] = field(default_factory=list)
    expecting: dict[
        FetchCallback[BaseModel | bytes], list[ExpectCallback[BaseModel | bytes]]
    ] = field(default_factory=lambda: defaultdict(list))
