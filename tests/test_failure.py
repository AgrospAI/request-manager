import pytest

from request_manager.exceptions import RequestManagerException
from request_manager.manager import IndependentCallback, RequestManager
from request_manager.types import BaseClient, Request, Response


async def test_no_setup(manager: RequestManager) -> None:

    with pytest.raises(RequestManagerException):
        await manager.run()


@pytest.mark.parametrize("body", ['{"data": "mock_data"}'])
async def test_out_of_order_dependency_resolves(
    manager: RequestManager,
    client: BaseClient,
    body: str,
) -> None:
    manager.client(client)

    @manager.fetch()
    def request() -> Request:
        return Request(method="GET", path="/transcriptions")

    @manager.fetch(depends_on=request)
    def request_2(response: Response) -> Request:
        return Request(method="GET", path="/transcriptions/2")

    # The decorator API always appends dependencies before their dependents.
    # Reversing the list here forces request_2 to be checked before request is resolved.
    manager.callbacks.fetching.reverse()

    resolved: list[Response] = []

    @manager.expect(request_2)
    def _(response: Response[bytes]) -> None:
        resolved.append(response)

    await manager.run()

    assert len(resolved) == 1


async def test_unresolved_dependency_raises(
    manager: RequestManager,
    client: BaseClient,
) -> None:
    manager.client(client)

    # This dependency is referenced but deliberately never registered via
    # @manager.fetch(), so it can never appear in `responses`.
    orphan_dependency = IndependentCallback(
        fn=lambda: Request(method="GET", path="/never-registered")
    )

    @manager.fetch(depends_on=orphan_dependency)
    def _(_: Response) -> Request:
        return Request(method="GET", path="/transcriptions")

    with pytest.raises(
        RequestManagerException,
        match="Circular or unresolved fetch dependency",
    ):
        await manager.run()
