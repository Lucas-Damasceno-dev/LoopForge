# ==============================================================================
# LoopForge v6 - Production Dockerfile
# Autonomous Agent Governance and Pipeline Orchestrator
# ==============================================================================
FROM python:3.12-slim

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Prevent Python from writing .pyc files and enable stdout buffering
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LF_API_HOST=0.0.0.0 \
    LF_API_PORT=8000

# Copy project metadata and source code
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install LoopForge and its dependencies
RUN pip install --no-cache-dir .

# Expose API and Web Dashboard port
EXPOSE 8000

# Healthcheck endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command starts the REST API, WebSockets, and Web Dashboard
CMD ["lf", "serve", "--host", "0.0.0.0", "--port", "8000"]
