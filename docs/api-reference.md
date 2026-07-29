# REST & WebSockets API Reference

## REST Endpoints

- `GET /health`: Healthcheck status.
- `GET /dashboard`: Modern Glassmorphic Web Dashboard.
- `POST /api/runs`: Create a new pipeline execution run.
- `GET /api/runs`: List pipeline execution runs.
- `GET /api/runs/{id}`: Get pipeline run details.
- `PATCH /api/runs/{id}`: Update pipeline run.
- `DELETE /api/runs/{id}`: Delete pipeline run.

## WebSockets Streaming

- `WS /ws/streaming`: Real-time node execution events broadcast stream.
- `WS /ws/runs/{run_id}`: Single run real-time event stream.
