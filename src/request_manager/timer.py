import time
from dataclasses import InitVar, dataclass, field


@dataclass(frozen=True, slots=True)
class TimeManager:
    timeout: InitVar[float | None]

    deadline: float | None = field(init=False)
    start_time: float = field(init=False)

    def __post_init__(self, timeout: float | None):
        now = self.now()

        object.__setattr__(self, "deadline", now + timeout if timeout else None)
        object.__setattr__(self, "start_time", now)

    def calculate_backoff(self, retry_backoff: float, attempt: int = 1) -> float:
        backoff = retry_backoff * attempt

        if self.deadline is not None:
            backoff = min(backoff, self.deadline - self.now())

        return backoff

    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    def now(self) -> float:
        return time.monotonic()

    def is_timeout(self) -> bool:
        return self.deadline is not None and self.now() >= self.deadline
