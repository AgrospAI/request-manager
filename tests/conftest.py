from collections.abc import Generator

import pytest

from request_manager.manager import RequestManager
from request_manager.types import ClientContext
from tests.mocks.client import body, client, raising_client, status_code  # noqa: F401


@pytest.fixture
def manager(client: ClientContext) -> Generator[RequestManager]:  # noqa: F811
    yield RequestManager.create(client=client)
