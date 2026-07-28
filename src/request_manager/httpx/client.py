from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Annotated, override
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from request_manager.types import BaseClient, Request, Response


@dataclass(frozen=True, slots=True)
class HttpxClient(BaseClient):
    client: httpx.AsyncClient
    """Base client to use in queries"""

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    @override
    async def fetch(
        self,
        request: Request,
    ) -> Response[bytes]:
        response = await self.client.send(
            httpx.Request(
                method=request.method,
                url=urljoin(str(self.client.base_url), request.path),
            ),
        )
        response.raise_for_status()

        return Response(
            request=request,
            status_code=response.status_code,
            headers={**response.headers},
            body=response.read(),
        )


class HttpxClientConfig(BaseModel):
    base_url: Annotated[
        str,
        Field(description="Base URL used for the requests"),
    ]

    api_scheme: Annotated[
        str,
        Field(description="API scheme to use", default="Bearer"),
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
    headers = (
        {"Authorization": f"{config.api_scheme} {config.api_key}"}
        if config.api_key
        else {}
    )
    return HttpxClient(
        client=httpx.AsyncClient(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout,
        )
    )
