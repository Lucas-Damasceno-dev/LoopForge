# Getting Started with LoopForge v6

## Instalação

```bash
# Clone o repositório
git clone https://github.com/Lucas-Damasceno-dev/LoopForge.git
cd LoopForge

# Instalar dependências e CLI em modo editável
pip install -e .
```

---

## Quick Start (CLI)

```bash
# 1. Executar o pipeline autônomo (Tech Lead decide a stack autonomamente)
lf run --idea "CLI em Rust que baixa cotação do dólar e salva em CSV"

# 2. Executar com wizard interativo (sem argumentos em TTY)
lf run --wizard

# 3. Executar com revisão humana (HITL) entre as fases
lf run --idea "Dashboard financeiro em Python" -i

# 4. Executar com review mode (pausa antes de salvar em disco)
lf run --idea "API REST" --review-mode --notify

# 5. Executar em modo rápido (bugfix, pula CPO/PM/Tech Lead)
lf run --idea "Corrigir bug no parser CSV" --stack rust --mock

# 6. Executar e abrir Pull Request no GitHub ao concluir
lf run --idea "API REST de Tarefas" --pr

# 7. Iniciar o Servidor REST API & Web Dashboard UI com WebSockets
lf serve --host 127.0.0.1 --port 8000

# 8. Avaliar a qualidade do pipeline com a suíte de Benchmark ELO
lf benchmark

# 9. Retomar pipeline interrompido a partir de checkpoint
lf resume --resume <session_id>
```

---

## Comandos Adicionais

```bash
# Inicializar projeto LoopForge
lf init

# Gerenciar planos de tarefas
lf plan --list

# Status da execução atual
lf status

# Geração automática de testes
lf generate-tests --dir ./meu-projeto

# Auditoria completa do pipeline
lf audit

# Exportar artefatos gerados
lf export --dir ./meu-projeto

# Interface web studio
lf studio --port 3000

# Gerar changelog e release
lf release --version 1.0.0

# Gerar shell completion (bash/zsh/fish)
lf completion bash > /etc/bash_completion.d/loopforge
```

---

## Implantação via Docker

```bash
cp .env.example .env
docker compose up -d
```

Acesse o Dashboard interativo no navegador: `http://localhost:8000/dashboard`.

---

## Integração GitHub Action

```yaml
- uses: Lucas-Damasceno-dev/LoopForge@v6
  with:
    idea: "API REST de tarefas em Java Spring Boot"
    stack: java
    routing_mode: full
    openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
```

---

## CI/CD Local

O pipeline de CI roda na seguinte ordem:

```bash
ruff check --select E,F,W,I,N,UP,SIM src/lf tests
mypy src/lf
pytest --cov=src/lf --cov-fail-under=75 tests/
```
