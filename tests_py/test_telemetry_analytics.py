import json

from lf.telemetry.analytics import export_analytics_json, render_analytics_summary
from lf.telemetry.recorder import TelemetryRecorder
from lf.telemetry.store import TelemetryStore


def test_telemetry_store_and_recorder(tmp_path):
    db_file = tmp_path / "telemetry.sqlite"
    store = TelemetryStore(db_path=db_file)
    store.log_event(
        session_id="s-001",
        task_id="T-001",
        node="developer",
        status="done",
        duration=1.25,
    )


    events = store.fetch_all()
    assert len(events) == 1
    assert events[0]["session_id"] == "s-001"
    assert events[0]["node"] == "developer"

    # Test TelemetryRecorder
    recorder = TelemetryRecorder(store=store)
    recorder.record_node_execution(
        session_id="s-002",
        task_id="T-002",
        node="qa",
        status="done",
        duration=0.5,
    )


    events_updated = store.fetch_all()
    assert len(events_updated) == 2


def test_render_analytics_summary(tmp_path):
    db_file = tmp_path / "telemetry.sqlite"
    store = TelemetryStore(db_path=db_file)
    store.log_event("s1", "T1", "cpo", "done", 2.0)

    # Render summary table to console
    render_analytics_summary(store=store)


def test_export_analytics_json(tmp_path):
    db_file = tmp_path / "telemetry.sqlite"
    store = TelemetryStore(db_path=db_file)
    store.log_event("s1", "T1", "cpo", "done", 2.0)

    out_file = tmp_path / "export.json"
    exported = export_analytics_json(output_path=out_file, store=store)

    assert exported.exists()
    data = json.loads(exported.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["task_id"] == "T1"
