import pytest

from request_manager.arguments import load_arguments
from request_manager.httpx.client import HttpxClientConfig, build_httpx_client
from request_manager.manager import RequestManager
from request_manager.types import Request, Response


@pytest.fixture(autouse=True)
def httpx_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RM__BASE_URL", "https://dummyjson.com")
    monkeypatch.setenv("RM__API_KEY", "test-key")


async def test_httpx_client(manager: RequestManager) -> None:
    config = load_arguments(HttpxClientConfig)
    manager.set_client(build_httpx_client(config))

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
