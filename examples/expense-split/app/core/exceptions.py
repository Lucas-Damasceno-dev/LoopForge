"""Exceções de domínio da aplicação."""

class DomainError(Exception):
    """Erro base de domínio."""

class NotFoundError(DomainError):
    """Erro lançado quando uma entidade não é encontrada."""

class ValidationError(DomainError, ValueError):
    """Erro lançado quando uma validação de domínio falha."""

class ExpenseValidationError(ValidationError):
    """Erro lançado quando uma despesa ou divisão é inválida."""

class BalanceMismatchError(ValidationError):
    """Erro lançado quando os saldos não são consistentes."""

class SettlementError(DomainError):
    """Erro lançado quando um plano de liquidação não pode ser gerado."""

class InviteExpiredError(DomainError):
    """Erro lançado quando um convite expirou."""

class PaymentError(DomainError):
    """Erro lançado quando uma operação de pagamento é inválida."""