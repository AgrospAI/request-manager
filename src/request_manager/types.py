from __future__ import annotations

from abc import abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Protocol, Self, cast, overload

from pydantic import BaseModel

type Headers = dict[str, Any]
type ResponseType = BaseModel | bytes

type MaybeAwaitable[T] = T | Awaitable[T]

type IndependentFetchFn = Callable[[], MaybeAwaitable[Request]]
type DependentFetchFn[T: ResponseType = bytes] = Callable[
    [Response[T]], MaybeAwaitable[Request]
]

type RawExpectFn[T: ResponseType = bytes] = Callable[
    [Response[T]], MaybeAwaitable[None]
]
type ValidatedExpectFn[T: ResponseType = bytes] = Callable[
    [Response[T]], MaybeAwaitable[None]
]

type FetchCallback[T: ResponseType = bytes] = IndependentCallback | DependentCallback[T]
type ExpectCallback[T: ResponseType = bytes] = (
    RawExpectCallback | ValidatedExpectCallback[T]
)


@dataclass(frozen=True)
class RawExpectCallback:
    fn: RawExpectFn


@dataclass(frozen=True)
class ValidatedExpectCallback[T: ResponseType = bytes]:
    fn: ValidatedExpectFn[T]
    type_: type[T]


@dataclass(frozen=True)
class IndependentCallback:
    fn: IndependentFetchFn


@dataclass(frozen=True)
class DependentCallback[T: ResponseType = bytes]:
    fn: DependentFetchFn[T]
    dependency: FetchCallback[T]
    type_: type[T]


@dataclass(slots=True)
class Callbacks:
    fetching: list[FetchCallback[ResponseType]] = field(default_factory=list)
    expecting: dict[FetchCallback[ResponseType], list[ExpectCallback[ResponseType]]] = (
        field(default_factory=lambda: defaultdict(list))
    )


@dataclass(frozen=True, slots=True)
class RequestOptions:
    timeout: float = 0.0
    retries: int = -1
    retry_backoff: float = 0.2
    is_success: Callable[[Response[Any]], bool] | None = None


@dataclass(frozen=True, slots=True)
class Request:
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
    url: str | None = None
    path: str | None = None
    headers: Headers | None = None
    body: Any = None
    options: RequestOptions = field(default_factory=RequestOptions)

    def is_successful(self, response: Response[bytes]) -> bool:
        return self.options.is_success is not None and self.options.is_success(response)


@dataclass(frozen=True, slots=True)
class Response[T: ResponseType = bytes]:
    request: Request

    status_code: int
    body: T
    headers: Headers | None = None

    to_dict = asdict

    @property
    def is_ok(self) -> bool:
        return 100 <= self.status_code < 400


class ClientError(BaseException):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(*args)
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class Client(Protocol):
    """Base client interface, represents a client capable of making requests."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    def __call__(self) -> Self:
        return self

    @abstractmethod
    async def fetch(
        self,
        request: Request,
    ) -> Response[bytes]:
        """Make a request

        Args:
            request (Request): request to be done

        Returns:
            Response[bytes]: request response
        """

    @overload
    def validate(
        self,
        response: Response[bytes],
        type_: type[bytes],
    ) -> Response[bytes]: ...

    @overload
    def validate(
        self,
        response: Response[bytes],
        type_: type[BaseModel],
    ) -> Response[BaseModel]: ...

    def validate[T: ResponseType](
        self,
        response: Response[bytes],
        type_: type[T],
    ) -> Response[T]:
        """Validate a given response using a pydantic BaseModel

        Args:
            response (Response): response to validate
            type_ (type[T]): BaseModel type to build an instance of or bytes

        Returns:
            Response[T]: a new response with the validated body
        """

        if type_ is bytes:
            return cast("Response[T]", response)

        return replace(
            response,
            body=type_.model_validate_json(response.body),  # type:ignore
        )


class Runner(Protocol):
    async def run[T: ResponseType](self, source: FetchCallback[T]) -> None:
        """Execute given source"""


type ClientContext = AbstractAsyncContextManager[Client]
