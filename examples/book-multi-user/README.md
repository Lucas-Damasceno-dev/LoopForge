# Booking System

Sistema de agendamento multi-usuário com FastAPI, SQLite e templates HTMX.

## Funcionalidades

- Autenticação JWT com papéis: cliente, profissional e admin.
- CRUD de profissionais e serviços.
- Criação de agendamentos com regras de negócio:
  - conflito de horários;
  - horário no passado;
  - jornada de trabalho do profissional;
  - sobreposição/disfponibilidade contínua.
- Cancelamento por cliente ou admin com motivo registrado.
- Notificações internas.
- Páginas HTMX básicas servidas pelo FastAPI.

## Execução