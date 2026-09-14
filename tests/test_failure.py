import pytest

from request_manager.exceptions import RequestManagerException
from request_manager.manager import IndependentCallback, RequestManager
from request_manager.types import (
    Client,
    ClientError,
    Request,
    RequestOptions,
    Response,
)


async def test_undefined_client_raises_error(manager: RequestManager) -> None:
    manager.set_client(None)  # type: ignore

    with pytest.raises(manager.error):
        await manager.arun()


async def test_expect_callback_raises_error(manager: RequestManager) -> None:
    ERROR_MSG = "Expected error"

    @manager.fetch()
    def request() -> Request:
        return Request(method="GET")

    @manager.expect(request)
    def will_raise(_: Response[bytes]) -> None:
        raise manager.error(ERROR_MSG)

    with pytest.raises(ExceptionGroup) as exc_info:
        await manager.arun()

    inner_exceptions = exc_info.value.exceptions
    assert len(inner_exceptions) == 1
    assert isinstance(inner_exceptions[0], manager.error)
    assert ERROR_MSG in str(inner_exceptions[0])


async def test_unresolved_dependency_raises(manager: RequestManager) -> None:
    # This dependency is referenced but deliberately never registered via
    # @manager.fetch(), so it can never appear in `responses`.
    orphan_dependency = IndependentCallback(
        fn=lambda: Request(method="GET", path="/never-registered")
    )

    @manager.fetch(depends_on=orphan_dependency, type_=bytes)
    def _(_: Response) -> Request:
        return Request(method="GET", path="/transcriptions")

    with pytest.raises(ExceptionGroup) as exc_info:
        await manager.arun()

    inner_exceptions = exc_info.value.exceptions
    assert len(inner_exceptions) == 1
    assert isinstance(inner_exceptions[0], RequestManagerException)
    assert "Unresolved fetch dependency" in str(inner_exceptions[0])


async def test_manager_run_from_async_context(manager: RequestManager) -> None:
    with pytest.raises(RuntimeError):
        manager.run()


def test_dependant_fetch_without_type_raises(manager: RequestManager) -> None:
    @manager.fetch()
    def sample(): ...

    with pytest.raises(RuntimeError):

        @manager.fetch(depends_on=sample, type_=None)
        def _(): ...


async def test_request_retry_attempts(
    manager: RequestManager,
    raising_client: Client,
) -> None:
    manager.set_client(raising_client)

    RETRIES = 5

    @manager.fetch()
    def _() -> Request:
        return Request(
            method="GET",
            options=RequestOptions(retries=RETRIES, retry_backoff=0),
        )

    with pytest.raises(ExceptionGroup) as exc_info:
        await manager.arun()

    inner_exceptions = exc_info.value.exceptions
    assert len(inner_exceptions) == 1
    assert isinstance(inner_exceptions[0], ClientError)
    assert (
        f"Response unsuccessful after {RETRIES + 1} attempt(s)"
        in inner_exceptions[0].msg
    )


async def test_request_retry_backoff(
    manager: RequestManager,
    raising_client: Client,
) -> None:
    manager.set_client(raising_client)

    @manager.fetch()
    def _() -> Request:
        return Request(
            method="GET",
            options=RequestOptions(retries=1, timeout=1, retry_backoff=0.00001),
        )

    with pytest.raises(ExceptionGroup) as exc_info:
        await manager.arun()

    inner_exceptions = exc_info.value.exceptions
    assert len(inner_exceptions) == 1
    assert isinstance(inner_exceptions[0], ClientError)
