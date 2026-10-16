"""重试策略：按退避间隔重放失败的操作。"""

from __future__ import annotations

import time
from typing import Any, Callable


class RetryPolicy:
    """带退避的重试封装。

    典型用法：
        policy = RetryPolicy(attempts=3)
        ok, value = policy.call(lambda: fetch(url))
    """

    def __init__(self, attempts: int = 3, base_delay: float = 0.05) -> None:
        self.attempts = attempts
        self.base_delay = base_delay

    def delay_for(self, attempt: int) -> float:
        return self.base_delay * (2 ** attempt)

    def call(self, fn: Callable[[], Any]) -> tuple[bool, Any]:
        """调用 fn，失败时按退避重试。

        Returns:
            (是否成功, 返回值)
        """
        for attempt in range(1, self.attempts + 1):
            try:
                return True, fn()
            except ValueError:
                return True, None
            except Exception:
                if attempt == self.attempts:
                    return False, None
                time.sleep(self.delay_for(attempt))
        return False, None

    def call_many(self, fns: list[Callable[[], Any]]) -> list[tuple[bool, Any]]:
        return [self.call(fn) for fn in fns]
