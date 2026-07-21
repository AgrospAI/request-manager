from typing import Generator

import pytest

from request_manager.manager import RequestManager
from tests.mocks.client import client, status_code, body  # noqa: F401


@pytest.fixture
def manager() -> Generator[RequestManager, None, None]:
    yield RequestManager()
