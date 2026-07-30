"""Parser de logs de sessão no formato AgDR (Agent Decision Records)."""

import json
import os
from typing import List, Union
from retro.store.models import AgDREvent, SessionRecord


class AgDRParser:
    def parse_file(self, file_path: str) -> SessionRecord:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo de log AgDR não encontrado: {file_path}")

        events: List[AgDREvent] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    try:
                        data = json.loads(line_str)
                        events.append(AgDREvent.model_validate(data))
                    except Exception:
                        pass

        return self.parse_events(events)

    def parse_events(self, events: List[AgDREvent]) -> SessionRecord:
        session_id = "unknown"
        goal = "N/A"
        status = "UNKNOWN"
        duration_ms = 0.0
        cost = 0.0
        retries = 0

        for ev in events:
            if ev.type == "session_start":
                if ev.session_id:
                    session_id = ev.session_id
                if ev.goal:
                    goal = ev.goal
            elif ev.type == "session_end":
                if ev.status:
                    status = ev.status
                if ev.duration_ms:
                    duration_ms = ev.duration_ms
                if ev.cost:
                    cost = ev.cost
            elif ev.type == "node_retry":
                retries += 1

        attempts = retries + 1

        return SessionRecord(
            session_id=session_id,
            goal=goal,
            status=status,
            duration_ms=duration_ms,
            cost=cost,
            attempts=attempts,
            events=events,
        )
