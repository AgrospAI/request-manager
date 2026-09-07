from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Self

from pydantic import BaseModel

type Headers = dict[str, Any]


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


@dataclass(frozen=True, slots=True)
class Response[BodyT: bytes | BaseModel]:
    request: Request

    status_code: int
    body: BodyT
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


class BaseClient(ABC):
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

    def validate[T: BaseModel](
        self,
        response: Response[bytes],
        type_: type[T],
    ) -> Response[T]:
        """Validate a given response using a pydantic BaseModel

        Args:
            response (Response): response to validate
            type_ (type[T]): BaseModel type to build an instance upon

        Returns:
            Response[T]: a new response with the validated body
        """

        return replace(
            response,
            body=type_.model_validate_json(response.body),  # type: ignore
        )


type ClientContext = AbstractAsyncContextManager[BaseClient]
