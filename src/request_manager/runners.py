import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import cast

from pydantic import BaseModel

from request_manager.exceptions import RequestManagerException
from request_manager.logger import add_prefix, logger
from request_manager.timer import TimeManager
from request_manager.types import (
    Callbacks,
    Client,
    ClientError,
    DependentCallback,
    FetchCallback,
    IndependentCallback,
    RawExpectCallback,
    Request,
    Response,
    ResponseType,
    ValidatedExpectCallback,
)

type Responses = dict[FetchCallback, Response[ResponseType]]
type Futures = dict[FetchCallback[ResponseType], asyncio.Future[Response[ResponseType]]]


@dataclass(frozen=True, slots=True)
class DependantRunner:
    client: Client
    callbacks: Callbacks

    responses: Responses = field(default_factory=dict)
    futures: Futures = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "futures",
            {
                source: asyncio.get_event_loop().create_future()
                for source in self.callbacks.fetching
            },
        )

    async def build_request[T: ResponseType](self, source: FetchCallback[T]) -> Request:
        match source:
            case IndependentCallback(fn=fn):
                request = fn()
            case DependentCallback(fn=fn, dependency=dep, type_=type_):
                if dep not in self.futures:
                    raise RequestManagerException("Unresolved fetch dependency")

                dependency = await self.futures[dep]  # type: ignore
                request = fn(self.client.validate(dependency, type_=type_))  # type: ignore

        if inspect.isawaitable(request):
            request = await request

        return request

    async def send_request(self, request: Request) -> Response[bytes]:
        response = await self.client.fetch(request)

        if not request.is_successful(response):
            raise ClientError("Unsuccessful response")

        return response

    async def wait_backoff(
        self,
        time: TimeManager,
        retry_backoff: float,
        attempt: int,
        logger: logging.Logger,
    ) -> None:
        backoff = time.calculate_backoff(retry_backoff, attempt)

        logger.warning("Retrying after %f seconds ...", backoff)
        await asyncio.sleep(max(backoff, 0))

    async def fetch(
        self,
        request: Request,
        logger: logging.Logger,
    ) -> Response[bytes]:
        time = TimeManager(request.options.timeout)

        attempt = 0
        while True:
            attempt += 1
            is_exhausted_attempts = (
                request.options.retries != -1 and attempt > request.options.retries + 1
            )

            try:
                return await self.client.fetch(request)
            except ClientError as e:
                logger.debug("Attempt %d [%{:07.3f}fs]: %s", attempt, time.elapsed(), e)

                if is_exhausted_attempts or time.is_timeout():
                    raise ClientError(
                        f"Response unsuccessful after {attempt} attempt(s) in {request.options.timeout} seconds"
                    )

                await self.wait_backoff(
                    time,
                    request.options.retry_backoff,
                    attempt,
                    logger,
                )

    async def run[T: ResponseType](
        self,
        source: FetchCallback[T],
    ) -> None:
        request = await self.build_request(source)

        run_logger = add_prefix(logger, f"[{source.fn.__name__}] ")

        logger.info(
            "Will retry for %d attempts or %d seconds",
            request.options.retries,
            request.options.timeout,
        )

        response = await self.fetch(request, run_logger)

        for expected in self.callbacks.expecting[
            cast("FetchCallback[BaseModel | bytes]", source)
        ]:
            match expected:
                case ValidatedExpectCallback(fn=expect_fn, type_=type__):
                    expect_fn(self.client.validate(response, type_=type__))  # type: ignore
                case RawExpectCallback(fn=expect_fn):
                    expect_fn(response)

        self.responses[source] = response  # type: ignore
        self.futures[source].set_result(response)  # type: ignore
