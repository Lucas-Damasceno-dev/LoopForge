# 📊 Project Executive Summary: 
Sistema de agendamento (booking) multi-usuário com FastAPI, SQLite e templates HTMX.

Módulos e entidades:
- Usuários com 3 papéis: cliente, profissional e admin. Autenticação por JWT (login, logout, proteção de rotas por papel).
- Profissionais: cada um tem uma lista de serviços oferecidos (nome, duração em minutos, preço).
- Agendamentos: cliente reserva um horário de um profissional para um serviço. Regras de domínio obrigatórias:
  (a) rejeitar conflito de horário — um profissional não pode ter dois agendamentos sobrepostos;
  (b) rejeitar agendamento no passado;
  (c) rejeitar agendamento fora do horário de trabalho do profissional (ex.: 08h-18h, seg-sex);
  (d) permitir cancelamento pelo cliente ou admin, com motivo registrado.
- Notificações: ao criar/cancelar um agendamento, registrar uma notificação para o profissional e o cliente (tabela de notificações, sem e-mail real).

API REST:
- POST /auth/login, POST /auth/logout
- CRUD /professionals, CRUD /services
- GET/POST /appointments, POST /appointments/{id}/cancel
- GET /notifications (por usuário logado)

Persistência: SQLite com migrations (tabelas users, professionals, services, appointments, notifications). Seed inicial com 2 profissionais, 4 serviços e 1 admin.

Frontend: páginas HTMX servidas pelo FastAPI (login, listagem de profissionais, criação de agendamento com validação de conflito, dashboard do profissional com seus agendamentos).

Testes: pytest cobrindo as regras de conflito, sobreposição, horário de trabalho, cancelamento, autenticação por papel e endpoints principais. Cobertura mínima 80%.


![QA Status](https://img.shields.io/badge/QA-FAIL-red)
![Security Audit](https://img.shields.io/badge/AppSec-PASS-brightgreen)
![Stack](https://img.shields.io/badge/Stack-PYTHON-blue)

> **Stack:** `python` | **Status QA:** `FAIL` (0/1) | **Data:** 2026-08-04 05:24:14 UTC

## 🏗️ Diagrama de Arquitetura do Projeto Gerado
```mermaid
graph TD
    Client[Client / User] --> API[API Service (PYTHON)]
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
pytest
python3 generated_code.py
```
