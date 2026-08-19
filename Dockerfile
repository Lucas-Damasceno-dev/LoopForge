# Dockerfile otimizado de produção para LoopForge v6 Monorepo
FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY packages/genome ./packages/genome
COPY packages/registry ./packages/registry
COPY packages/retro ./packages/retro
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ./packages/genome -e ./packages/registry -e ./packages/retro -e .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/lf /usr/local/bin/lf
COPY . .

# QA harness (TestHarnessRunner) executa pytest no projeto gerado — sem ele,
# toda run real falha com "comando de teste não encontrado no PATH".
RUN pip install --no-cache-dir pytest pytest-asyncio

EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["lf", "serve", "--port", "8000", "--host", "0.0.0.0"]
