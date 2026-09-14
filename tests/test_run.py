import pytest

from request_manager.manager import RequestManager
from request_manager.types import Request, RequestOptions, Response
from tests.mocks.client import MockData


@pytest.mark.parametrize(
    "status_code",
    [200],
)
@pytest.mark.parametrize(
    "body",
    ['{"data": "mock_data"}', '{"data": "1234"}', '{"data": "ok"}'],
)
async def test_callback_setup(
    manager: RequestManager,
    status_code: int,
    body: str,
) -> None:
    @manager.fetch()
    def request() -> Request:
        return Request(
            method="GET",
            path="/transcriptions",
        )

    @manager.expect(request, type_=MockData)
    def assert_result(response: Response[MockData]):
        assert response.status_code == status_code
        assert response.body == MockData.model_validate_json(body)

    @manager.fetch(depends_on=request, type_=bytes)
    def request_2(response: Response) -> Request:
        return Request(
            method="GET",
            path="/transcriptions/2",
        )

    @manager.expect(request)
    def _(response: Response[bytes]) -> None:
        assert response.status_code == status_code

    @manager.fetch(depends_on=request_2, type_=bytes)
    def _(_) -> Request:
        return Request(
            method="GET",
            path="/transcriptions/2",
        )

    await manager.arun()


def test_manager_run_from_sync_context(manager: RequestManager) -> None:
    manager.run()


async def test_async_request(manager: RequestManager) -> None:
    @manager.fetch()
    async def _() -> Request:
        return Request(method="GET")

    await manager.arun()


@pytest.mark.parametrize(
    "status_code",
    [200, 400],
)
@pytest.mark.parametrize(
    "body",
    ['{"data": "mock_data"}', '{"data": "1234"}'],
)
async def test_request_is_success(manager: RequestManager, status_code, body) -> None:
    @manager.fetch()
    def _() -> Request:
        return Request(
            method="GET",
            options=RequestOptions(is_success=lambda res: res.is_ok()),
        )

    if status_code == 200:
        await manager.arun()
    else:
        with pytest.raises(ExceptionGroup):
            await manager.arun()
