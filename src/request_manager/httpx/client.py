import logging
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Annotated, override
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from request_manager.arguments import load_arguments
from request_manager.types import BaseClient, ClientError, Request, Response

logging.getLogger("httpx").setLevel(logging.WARN)


@dataclass(frozen=True, slots=True)
class HttpxClient(BaseClient):
    client: httpx.AsyncClient
    """Base client to use in queries"""

    @staticmethod
    def default() -> AbstractAsyncContextManager[BaseClient]:
        return build_httpx_client(load_arguments(HttpxClientConfig))

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    @override
    async def fetch(
        self,
        request: Request,
    ) -> Response[bytes]:
        httpx_request = self.client.build_request(
            method=request.method,
            url=urljoin(str(request.url or self.client.base_url), request.path),
            json=request.body,
        )

        response = await self.client.send(httpx_request)
        if response.is_error:
            raise ClientError(f"There was an error. ERROR: {response.text}")

        return Response(
            request=request,
            status_code=response.status_code,
            headers={**response.headers},
            body=response.read(),
        )


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


def build_httpx_client(
    config: HttpxClientConfig,
) -> AbstractAsyncContextManager[BaseClient]:
    headers = {"Content-Type": "application/json"}

    if config.api_key is not None:
        value = (
            f"{config.authorization_scheme} {config.api_key}"
            if config.authorization_scheme
            else config.api_key
        )

        headers[config.authorization_header] = value

    return HttpxClient(
        client=httpx.AsyncClient(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout,
        )
    )
