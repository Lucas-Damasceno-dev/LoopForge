"""
Circuit Breaker com budget embutido (Oracle rec: budget_controller absorvido aqui).
Três guardas: falhas consecutivas, iterações máximas, custo máximo ($).
"""

from __future__ import annotations

import time


class CircuitBreaker:
    """Protege contra loops infinitos e estouro de budget."""

    STATE_CLOSED = "closed"  # Tudo ok
    STATE_OPEN = "open"  # Circuito aberto (parou)
    STATE_HALF_OPEN = "half-open"  # Tentando recuperar

    def __init__(
        self,
        max_consecutive_failures: int = 5,
        max_iterations: int = 20,
        max_total_cost: float = 50.0,  # USD
        cost_per_iteration: float = 0.05,  # USD estimado (modelo gratuito ~$0)
        reset_timeout: float = 300.0,  # segundos para half-open
    ):
        self.max_consecutive_failures = max_consecutive_failures
        self.max_iterations = max_iterations
        self.max_total_cost = max_total_cost
        self.cost_per_iteration = cost_per_iteration
        self.reset_timeout = reset_timeout

        self.state = self.STATE_CLOSED
        self.consecutive_failures = 0
        self.total_iterations = 0
        self.total_cost = 0.0
        self.last_failure_time: float | None = None

    def record_success(self):
        """Registra sucesso e reseta falhas consecutivas."""
        self.consecutive_failures = 0
        self.state = self.STATE_CLOSED

    def record_failure(self):
        """Registra falha e verifica se abre circuito."""
        self.consecutive_failures += 1
        self.total_iterations += 1
        self.total_cost += self.cost_per_iteration
        self.last_failure_time = time.time()

        if self.consecutive_failures >= self.max_consecutive_failures or self.total_cost >= self.max_total_cost:
            self.state = self.STATE_OPEN

    def record_iteration(self):
        """Registra iteração (independente de sucesso/falha)."""
        self.total_iterations += 1
        self.total_cost += self.cost_per_iteration

        if self.total_iterations >= self.max_iterations or self.total_cost >= self.max_total_cost:
            self.state = self.STATE_OPEN

    def can_proceed(self) -> bool:
        """Verifica se pode executar próxima iteração."""
        if self.state == self.STATE_CLOSED:
            return True

        if self.state == self.STATE_OPEN:
            # Tenta half-open após timeout
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.reset_timeout:
                self.state = self.STATE_HALF_OPEN
                return True
            return False

        # half-open: permite 1 tentativa
        return True

    def __getstate__(self) -> dict:
        """Serializa para msgpack (SqliteSaver do LangGraph exige tipos primitivos)."""
        return {
            "max_consecutive_failures": self.max_consecutive_failures,
            "max_iterations": self.max_iterations,
            "max_total_cost": self.max_total_cost,
            "cost_per_iteration": self.cost_per_iteration,
            "reset_timeout": self.reset_timeout,
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "total_iterations": self.total_iterations,
            "total_cost": self.total_cost,
            "last_failure_time": self.last_failure_time,
        }

    def __setstate__(self, data: dict) -> None:
        """Reconstrói o objeto a partir do estado serializado."""
        self.max_consecutive_failures = data["max_consecutive_failures"]
        self.max_iterations = data["max_iterations"]
        self.max_total_cost = data["max_total_cost"]
        self.cost_per_iteration = data["cost_per_iteration"]
        self.reset_timeout = data["reset_timeout"]
        self.state = data["state"]
        self.consecutive_failures = data["consecutive_failures"]
        self.total_iterations = data["total_iterations"]
        self.total_cost = data["total_cost"]
        self.last_failure_time = data["last_failure_time"]

    def snapshot(self) -> dict:
        """Retorna estado serializável (msgpack-safe) do CircuitBreaker."""
        return self.__getstate__()

    @classmethod
    def from_snapshot(cls, data: dict) -> CircuitBreaker:
        """Reconstrói o objeto a partir de um snapshot (dict de primitivos)."""
        cb = cls.__new__(cls)
        cb.__setstate__(data)
        return cb

    def to_dict(self) -> dict:
        """Estado completo serializável — chaves idênticas às de snapshot()/__setstate__.

        Garante round-trip: ``CircuitBreaker.from_snapshot(cb.to_dict())``.
        """
        return self.__getstate__()

    @property
    def budget_exceeded(self) -> bool:
        return self.total_cost >= self.max_total_cost

    @property
    def iterations_exceeded(self) -> bool:
        return self.total_iterations >= self.max_iterations
