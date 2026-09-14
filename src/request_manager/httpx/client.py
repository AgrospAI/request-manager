import logging
from dataclasses import dataclass
from typing import Annotated, override
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from request_manager.arguments import LazyArguments
from request_manager.types import Client, ClientError, Request, Response

logging.getLogger("httpx").setLevel(logging.WARNING)


class HttpxClientConfig(BaseModel):
    base_url: Annotated[
        str,
        Field(default="", description="Base URL used for the requests"),
    ]

    authorization_header: Annotated[
        str,
        Field(description="API authorization header to use", default="Authorization"),
    ]

    authorization_scheme: Annotated[
        str,
        Field(description="API authorization scheme to use", default="Bearer"),
    ]

    api_key: Annotated[
        str | None,
        Field(description="API key to use", default=None),
    ]

    timeout: Annotated[
        float,
        Field(description="Maximum timeout for reponse arrival", default=5.0),
    ]


@dataclass(slots=True)
class HttpxClient(Client):
    _lazy_config: LazyArguments[HttpxClientConfig]
    _client: httpx.AsyncClient | None = None

    @classmethod
    def default(cls) -> Client:
        return cls(_lazy_config=LazyArguments(HttpxClientConfig))

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            config = self._lazy_config.get()
            self._client = build_httpx_client(config)
        assert self._client is not None
        return self._client

    async def __aenter__(self):
        client = self._ensure_client()
        await client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        if self._client is not None:
            await self._client.__aexit__(*exc_info)

    @override
    async def fetch(
        self,
        request: Request,
    ) -> Response[bytes]:
        client = self._ensure_client()
        httpx_request = client.build_request(
            method=request.method,
            url=urljoin(str(request.url or client.base_url), request.path),
            json=request.body,
        )

        response = await client.send(httpx_request)
        if response.is_error:
            raise ClientError(f"There was an error. ERROR: {response.text}")

        return Response(
            request=request,
            status_code=response.status_code,
            headers={**response.headers},
            body=response.read(),
        )


def build_httpx_client(config: HttpxClientConfig) -> httpx.AsyncClient:
    headers = {"Content-Type": "application/json"}

    if config.api_key is not None:
        value = (
            f"{config.authorization_scheme} {config.api_key}"
            if config.authorization_scheme
            else config.api_key
        )

        headers[config.authorization_header] = value

    return httpx.AsyncClient(
        base_url=config.base_url,
        headers=headers,
        timeout=config.timeout,
    )
