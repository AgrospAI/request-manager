from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal, Self, cast

from pydantic import BaseModel

type Headers = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Request:
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
    path: str | None = None
    headers: Headers | None = None
    body: bytes | None = None


@dataclass(frozen=True, slots=True)
class Response[BodyT]:
    status_code: int
    body: BodyT
    headers: Headers | None = None

    to_dict = asdict


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
