"""Regras de disponibilidade e jornada de trabalho."""
from __future__ import annotations

from datetime import datetime, time

from app.models.professional import Professional


def parse_working_days(working_days: str) -> set[int]:
    """Converte a string de dias de trabalho em um conjunto de inteiros.

    A convenção segue a spec: 0 = domingo, 6 = sábado.
    """
    if not working_days:
        return set()

    try:
        days = {int(item.strip()) for item in working_days.split(",") if item.strip()}
    except ValueError as exc:
        raise ValueError("Formato de working_days inválido. Use números separados por vírgula.") from exc

    if any(day < 0 or day > 6 for day in days):
        raise ValueError("Dias de trabalho devem estar entre 0 e 6 (0=Dom, 6=Sáb).")

    return days


def _iso_weekday_to_spec(iso_weekday: int) -> int:
    """Converte weekday do Python (0=segunda, 6=domingo) para a convenção da spec."""
    mapping = {6: 0, 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
    return mapping[iso_weekday]


def is_working_time(professional: Professional, start_time: datetime, end_time: datetime) -> bool:
    """Verifica se o intervalo [start_time, end_time] está dentro da jornada do profissional."""
    days = parse_working_days(professional.working_days)
    day_num = _iso_weekday_to_spec(start_time.weekday())
    if day_num not in days:
        return False

    try:
        start = time.fromisoformat(professional.start_hour)
        end = time.fromisoformat(professional.end_hour)
    except ValueError:
        return False

    return start <= start_time.time() and end_time.time() <= end