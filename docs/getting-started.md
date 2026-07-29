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

# 2. Executar especificando uma stack via override manual
lf run --idea "API REST de tarefas" --stack java

# 3. Executar com revisão humana (HITL) entre as fases
lf run --idea "Dashboard financeiro em Python" --interactive

# 4. Executar e abrir Pull Request no GitHub ao concluir
lf run --idea "API REST de Tarefas" --pr

# 5. Iniciar o Servidor REST API & Web Dashboard UI com WebSockets
lf serve --host 127.0.0.1 --port 8000

# 6. Avaliar a qualidade do pipeline com a suíte de Benchmark ELO
lf benchmark

# 7. Retomar pipeline interrompido a partir de checkpoint
lf resume --resume <session_id>
```

---

## Implantação via Docker

```bash
cp .env.example .env
docker compose up -d
```

Acesse o Dashboard interativo no navegador: `http://localhost:8000/dashboard`.
