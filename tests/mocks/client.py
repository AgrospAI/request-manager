from dataclasses import dataclass
from typing import override

import pytest
from pydantic import BaseModel

from request_manager.types import Client, ClientContext, ClientError, Request, Response


class MockData(BaseModel):
    data: str


@dataclass(slots=True)
class MockClient(Client):
    body: str = ""
    status_code: int = 200

    @override
    async def fetch(self, request: Request) -> Response[bytes]:
        return Response(
            request=request,
            status_code=self.status_code,
            body=self.body.encode(),
        )


@pytest.fixture
def status_code(request: pytest.FixtureRequest) -> int:
    return getattr(request, "param", 200)


@pytest.fixture
def body(request: pytest.FixtureRequest) -> str:
    return getattr(request, "param", "mock data")


@pytest.fixture
def client(
    status_code: int,
    body: str,
) -> ClientContext:
    return MockClient(status_code=status_code, body=body)


class RaisingClient(Client):
    @override
    async def fetch(self, request):
        raise ClientError("RaisingClient error")


@pytest.fixture
def raising_client() -> ClientContext:
    return RaisingClient()
