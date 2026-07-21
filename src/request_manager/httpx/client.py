from dataclasses import dataclass
from typing import override
from urllib.parse import urljoin

import httpx

from request_manager.types import BaseClient, Request, Response


@dataclass(frozen=True, slots=True)
class HttpxClient(BaseClient):
    client: httpx.AsyncClient
    """Base client to use in queries"""

    async def __aenter__(self):
        async with self.client as client:
            yield client

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
            status_code=response.status_code,
            headers={**response.headers},
            body=response.read(),
        )
