from dataclasses import dataclass


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    total_spend_usd: float = 0.0
    is_open: bool = False


class CircuitBreaker:
    def __init__(self, max_consecutive_failures: int = 3, budget_limit_usd: float = 10.0):
        self.max_failures = max_consecutive_failures
        self.budget_limit_usd = budget_limit_usd
        self.state = CircuitState()

    def record_success(self, estimated_cost_usd: float = 0.01):
        self.state.consecutive_failures = 0
        self.state.total_spend_usd += estimated_cost_usd
        self._check_budget()

    def record_failure(self, estimated_cost_usd: float = 0.01):
        self.state.consecutive_failures += 1
        self.state.total_spend_usd += estimated_cost_usd
        if self.state.consecutive_failures >= self.max_failures:
            self.state.is_open = True
        self._check_budget()

    def _check_budget(self):
        if self.state.total_spend_usd >= self.budget_limit_usd:
            self.state.is_open = True

    def can_proceed(self) -> bool:
        return not self.state.is_open
