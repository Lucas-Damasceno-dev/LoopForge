# Log Ingestor

Microserviço em Go para ingestão em tempo real de logs estruturados em JSON, com:
- Validação e normalização de logs;
- Classificação automática de severidade por palavras-chave configuráveis;
- Filtragem por severidade mínima;
- Persistência seletiva em PostgreSQL;
- Métricas Prometheus;
- Autenticação via API Key.

## Execução