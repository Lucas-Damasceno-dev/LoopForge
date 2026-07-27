from lf.telemetry.store import TelemetryStore


class TelemetryRecorder:
    def __init__(self, store: TelemetryStore = None):
        self.store = store or TelemetryStore()

    def record_node_execution(self, session_id: str, task_id: str, node: str, status: str, duration: float = 0.0):
        self.store.log_event(
            session_id=session_id,
            task_id=task_id,
            node=node,
            status=status,
            duration=duration,
            cost=0.005,
        )
