# Getting Started with LoopForge

## Installation

```bash
pip install -e .
```

## Quick Start (CLI)

```bash
# Initialize a new project context
lf init --name "My Project"

# Create a project specification plan
lf plan --idea "Build a REST API service"

# Run the 7-agent pipeline
lf run --idea "Build a REST API service" --stack python

# Start the REST API & Web Dashboard
lf serve --host 127.0.0.1 --port 8000
```

## Docker Deployment

```bash
cp .env.example .env
docker compose up -d
```
Access the Dashboard at `http://localhost:8000/dashboard`.
