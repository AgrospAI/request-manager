from dataclasses import dataclass
from typing import override

import pytest
from pydantic import BaseModel

from request_manager.types import BaseClient, Request, Response


class MockData(BaseModel):
    data: str


@dataclass(slots=True)
class MockClient(BaseClient):
    body: str
    status_code: int = 200

    @override
    async def fetch(self, _: Request) -> Response[bytes]:
        return Response(
            status_code=self.status_code,
            body=self.body.encode(),
        )


@pytest.fixture
def status_code(request: pytest.FixtureRequest) -> int:
    return getattr(request, "param", 200)


@pytest.fixture
def body(request: pytest.FixtureRequest) -> MockData:
    data = getattr(request, "param", "mock data")
    return MockData(data=data)


@pytest.fixture
def client(
    status_code: int,
    body: str,
) -> MockClient:
    return MockClient(status_code=status_code, body=body)
