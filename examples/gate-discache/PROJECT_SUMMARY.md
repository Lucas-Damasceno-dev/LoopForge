# 📊 Project Executive Summary: Gateway de API com rate limiting distribuído e cache
Gateway de API com rate limiting por cliente, cache em memória e roteamento para serviços de backend simulados.

Módulos e entidades:
- Clientes (consumidores de API): nome, chave de API (UUID), plano (free/pro/enterprise) com limites de requisições por minuto (free 10, pro 60, enterprise 300) e limites de concorrência.
- Chaves de API: autenticação por header X-API-Key; chave inválida ou revogada retorna 401. Cada chave pertence a um cliente.
- Rate limiting: janela deslizante por cliente+rota, em memória, thread-safe. Requisição acima do limite retorna 429 com header Retry-After. Limites por plano e por rota (rotas /admin mais restritas).
- Roteamento: tabela de rotas (prefixo, backend_alvo, método permitido, requer_auth, requer_admin). Backends simulados respondem com payload fixo e latência configurável; timeout de backend tratado (504).
- Cache em memória: GET em rotas marcadas como cacheable armazena resposta por TTL (segundos); hit de cache não conta para rate limit e não chama backend. Invalidação por chave explícita via endpoint.
- Circuit breaker por backend: após N falhas consecutivas (5) o backend entra em aberto por X segundos (30), durante o qual as chamadas falham rápido (503) sem tentar o backend; após o cooldown, meio-aberto com 1 tentativa de teste.
- Métricas de observabilidade: contadores por rota (total, 2xx, 4xx, 5xx, latência média), por cliente (requisições, bloqueadas), por backend (falhas, circuit state). Expostos via endpoint /metrics em formato texto simples.
- Logs de acesso: tabela de logs (timestamp, cliente, rota, status, latência_ms, cache_hit) com rotação (manter últimos 10.000).

API REST (do próprio gateway):
- POST /admin/clientes (cria cliente + chave), POST /admin/clientes/{id}/revogar-chave, GET /admin/clientes
- GET /admin/rotas, POST /admin/rotas (configura rota/backend/limites/cache)
- GET /admin/metrics, GET /admin/logs (filtro por cliente/status)
- POST /admin/cache/invalidate/{chave}
- Rotas de proxy: GET/POST /api/{rota} (aplica auth, rate limit, cache, roteamento, circuit breaker)

Persistência: SQLite para clientes, chaves, rotas e logs (estado durável); cache e rate limit em memória (não persistem). Seed: 2 clientes (free e pro), 4 rotas (2 cacheable, 1 admin, 1 pública), 2 backends simulados.

Testes: chave inválida 401; rate limit por plano (free 10/min → 11ª é 429 com Retry-After); janela deslizante thread-safe sob concorrência; cache hit não chama backend nem conta rate limit; TTL expira; circuit breaker abre após 5 falhas, falha rápido 503, meio-aberto testa e fecha; timeout de backend 504; métricas agregadas corretas; rota admin exige admin; logs com rotação. Cobertura mínima 80%.Gateway de API com rate limiting distribuído e cache
Gateway de API com rate limiting por cliente, cache em memória e roteamento para serviços de backend simulados.

Módulos e entidades:
- Clientes (consumidores de API): nome, chave de API (UUID), plano (free/pro/enterprise) com limites de requisições por minuto (free 10, pro 60, enterprise 300) e limites de concorrência.
- Chaves de API: autenticação por header X-API-Key; chave inválida ou revogada retorna 401. Cada chave pertence a um cliente.
- Rate limiting: janela deslizante por cliente+rota, em memória, thread-safe. Requisição acima do limite retorna 429 com header Retry-After. Limites por plano e por rota (rotas /admin mais restritas).
- Roteamento: tabela de rotas (prefixo, backend_alvo, método permitido, requer_auth, requer_admin). Backends simulados respondem com payload fixo e latência configurável; timeout de backend tratado (504).
- Cache em memória: GET em rotas marcadas como cacheable armazena resposta por TTL (segundos); hit de cache não conta para rate limit e não chama backend. Invalidação por chave explícita via endpoint.
- Circuit breaker por backend: após N falhas consecutivas (5) o backend entra em aberto por X segundos (30), durante o qual as chamadas falham rápido (503) sem tentar o backend; após o cooldown, meio-aberto com 1 tentativa de teste.
- Métricas de observabilidade: contadores por rota (total, 2xx, 4xx, 5xx, latência média), por cliente (requisições, bloqueadas), por backend (falhas, circuit state). Expostos via endpoint /metrics em formato texto simples.
- Logs de acesso: tabela de logs (timestamp, cliente, rota, status, latência_ms, cache_hit) com rotação (manter últimos 10.000).

API REST (do próprio gateway):
- POST /admin/clientes (cria cliente + chave), POST /admin/clientes/{id}/revogar-chave, GET /admin/clientes
- GET /admin/rotas, POST /admin/rotas (configura rota/backend/limites/cache)
- GET /admin/metrics, GET /admin/logs (filtro por cliente/status)
- POST /admin/cache/invalidate/{chave}
- Rotas de proxy: GET/POST /api/{rota} (aplica auth, rate limit, cache, roteamento, circuit breaker)

Persistência: SQLite para clientes, chaves, rotas e logs (estado durável); cache e rate limit em memória (não persistem). Seed: 2 clientes (free e pro), 4 rotas (2 cacheable, 1 admin, 1 pública), 2 backends simulados.

Testes: chave inválida 401; rate limit por plano (free 10/min → 11ª é 429 com Retry-After); janela deslizante thread-safe sob concorrência; cache hit não chama backend nem conta rate limit; TTL expira; circuit breaker abre após 5 falhas, falha rápido 503, meio-aberto testa e fecha; timeout de backend 504; métricas agregadas corretas; rota admin exige admin; logs com rotação. Cobertura mínima 80%.

![QA Status](https://img.shields.io/badge/QA-FAIL-red)
![Security Audit](https://img.shields.io/badge/AppSec-PASS-brightgreen)
![Stack](https://img.shields.io/badge/Stack-GO-blue)

> **Stack:** `go` | **Status QA:** `FAIL` (0/1) | **Data:** 2026-08-04 06:40:53 UTC

## 🏗️ Diagrama de Arquitetura do Projeto Gerado
```mermaid
graph TD
    Client[Client / User] --> API[API Service (GO)]
    API --> Logic[Business Logic Core]
    Logic --> Tests[QA Test Suite (FAIL)]
```

## 🌐 Endpoints & Interface
- **Base API URL:** `http://localhost:8000` (se aplicável para APIs)
- **Health Check:** `GET /health` ou `GET /`

## 🛡️ Auditoria & Segurança
- Nenhuma vulnerabilidade crítica detectada no escaneamento estático.

## 🚀 Instruções de Execução Rápida
```bash
go test ./...
go run main.go
```
