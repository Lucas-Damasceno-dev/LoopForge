"""Funções utilitárias de manipulação monetária e apoio."""
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

def round_money(value: Any) -> Decimal:
    """Arredonda um valor para duas casas decimais."""
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def money_to_cents(value: Any) -> int:
    """Converte um valor decimal em centavos."""
    return int(round_money(value) * 100)

def cents_to_money(cents: int) -> Decimal:
    """Converte centavos em Decimal."""
    return Decimal(cents) / Decimal(100)

def sum_money(values) -> Decimal:
    """Soma uma sequência de valores monetários e arredonda o resultado."""
    return round_money(sum((Decimal(value) for value in values), Decimal("0.00")))

def first_not_none(*values: Any) -> Any:
    """Retorna o primeiro argumento que não seja None."""
    for value in values:
        if value is not None:
            return value
    return None

def is_mock(obj: Any) -> bool:
    """Detecta objetos ``unittest.mock.Mock``.

    Isso permite que serviços usem repositórios Mock em testes sem propagar
    objetos Mock para o domínio.
    """
    return type(obj).__module__.startswith("unittest.mock")