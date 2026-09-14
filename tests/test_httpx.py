import pytest

from request_manager.httpx.client import HttpxClient
from request_manager.manager import RequestManager
from request_manager.types import Client, Request, Response


@pytest.fixture(autouse=True)
def httpx_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RM__BASE_URL", "https://dummyjson.com")
    monkeypatch.setenv("RM__API_KEY", "test-key")


@pytest.fixture
def httpx_client() -> Client:
    return HttpxClient.default()


async def test_httpx_client(manager: RequestManager, httpx_client: Client) -> None:
    manager.set_client(httpx_client)

    @manager.fetch()
    def request() -> Request:
        return Request(
            method="GET",
            path="/todos",
            headers={"test-header": "present"},
        )

    @manager.expect(request)
    def expect(response: Response) -> None:
        if response.request.headers is None:
            raise manager.error("Empty headers")

        if "Authorization" in response.request.headers:
            raise manager.error(
                "Default headers shouldn't be present in Request headers"
            )

    await manager.arun()
