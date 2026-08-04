# Sistema de Agendamento (Booking) em Go

Backend completo com autenticação JWT, SQLite, e regras de negócio.

## Como rodar
1. Copie `.env.example` para `.env` e defina `JWT_SECRET`.
2. Execute `go run ./cmd/server`.
3. A API estará em `http://localhost:8080`.

## Testes
`go test ./...`

## Estrutura
- `cmd/server`: ponto de entrada.
- `internal/api`: rotas HTTP e middlewares.
- `internal/config`: configuração via ambiente.
- `internal/db`: migrações e seed.
- `internal/models`: structs.
- `internal/repository`: acesso a dados SQLite.
- `internal/service`: lógica de negócio.
- `tests/`: testes unitários.