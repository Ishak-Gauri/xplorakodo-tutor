"""Cost-guard agent: a per-student daily token budget plus a global kill switch."""
from collections import defaultdict
from datetime import date

from .errors import BudgetExceeded


def estimate_tokens(*texts: str) -> int:
    """Rough estimate (about 4 characters per token) plus a fixed overhead for the prompt."""
    return sum(len(t) for t in texts) // 4 + 150


class CostGuard:
    def __init__(self, daily_budget: int):
        self.daily_budget = daily_budget
        self.killed = False
        self._used: dict[tuple[int, str], int] = defaultdict(int)

    def used_today(self, student_id: int) -> int:
        return self._used[(student_id, date.today().isoformat())]

    def check(self, student_id: int) -> None:
        if self.killed:
            raise BudgetExceeded("The tutor is paused by an administrator.")
        if self.used_today(student_id) >= self.daily_budget:
            raise BudgetExceeded("Daily practice budget reached. Please continue tomorrow.")

    def spend(self, student_id: int, tokens: int) -> None:
        self._used[(student_id, date.today().isoformat())] += tokens
