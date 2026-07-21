from __future__ import annotations

import pytest

from request_manager.manager import RequestManager
from request_manager.types import BaseClient, Request, Response
from tests.mocks.client import MockData


@pytest.mark.parametrize("status_code", [200, 400, 500])
@pytest.mark.parametrize(
    "body", ['{"data": "mock_data"}', '{"data": "1234"}', '{"data": "ok"}']
)
async def test_callback_setup(
    manager: RequestManager,
    client: BaseClient,
    status_code: int,
    body: str,
) -> None:

    manager.client(client)

    @manager.fetch()
    def request() -> Request:
        return Request(
            method="GET",
            path="/transcriptions",
        )

    @manager.expect(request, type_=MockData)
    def assert_result(response: Response[MockData]) -> None:
        assert response.status_code == status_code
        assert response.body == MockData.model_validate_json(body)

    @manager.fetch(depends_on=request)
    def request_2(response: Response) -> Request:
        return Request(
            method="GET",
            path="/transcriptions/2",
        )

    @manager.expect(request)
    def _(response: Response[bytes]) -> None:
        assert response.status_code == status_code

    @manager.fetch(depends_on=request_2)
    def _(_) -> Request:
        return Request(
            method="GET",
            path="/transcriptions/2",
        )

    await manager.run()
