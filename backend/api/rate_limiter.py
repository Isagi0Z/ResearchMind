import time
import abc
from collections import OrderedDict
from typing import Optional


class CounterStore(abc.ABC):
    @abc.abstractmethod
    def get(self, key: str) -> int:
        ...

    @abc.abstractmethod
    def increment(self, key: str, ttl: int) -> int:
        ...

    @abc.abstractmethod
    def cleanup(self) -> None:
        ...


class MemoryCounterStore(CounterStore):
    def __init__(self, max_buckets: int = 10000):
        self._buckets: OrderedDict[str, tuple[int, float]] = OrderedDict()
        self._max_buckets = max_buckets

    def _current_window(self, window_seconds: int) -> float:
        return time.time() // window_seconds

    def get(self, key: str) -> int:
        count, _ = self._buckets.get(key, (0, 0.0))
        return count

    def increment(self, key: str, ttl: int) -> int:
        now_window = self._current_window(ttl)
        count, window = self._buckets.get(key, (0, now_window))

        if window != now_window:
            count = 0
            window = now_window

        count += 1
        self._buckets[key] = (count, window)
        if len(self._buckets) > self._max_buckets:
            self.cleanup()

        return count

    def cleanup(self) -> None:
        stale_threshold = self._current_window(1)
        stale_keys = [k for k, (_, w) in self._buckets.items() if w < stale_threshold]
        for k in stale_keys:
            del self._buckets[k]


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, store: Optional[CounterStore] = None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store = store or MemoryCounterStore()

    def is_allowed(self, key: str) -> bool:
        count = self._store.increment(key, self.window_seconds)
        return count <= self.max_requests
