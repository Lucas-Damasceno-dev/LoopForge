package postgres

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/example/logingestor/internal/domain"
	"github.com/jackc/pgx/v5/pgxpool"
)

const createTable = `
CREATE TABLE IF NOT EXISTS logs (
    id         VARCHAR(64) PRIMARY KEY,
    timestamp  TIMESTAMPTZ NOT NULL,
    service    VARCHAR(255) NOT NULL,
    severity   VARCHAR(16) NOT NULL,
    message    TEXT NOT NULL,
    metadata   JSONB NOT NULL DEFAULT '{}',
    received_at TIMESTAMPTZ NOT NULL
);
`

// Repository é a implementação PostgreSQL de domain.LogRepository.
type Repository struct {
	pool *pgxpool.Pool
}

// New conecta ao PostgreSQL, valida a conexão e garante o schema.
func New(ctx context.Context, databaseURL string) (*Repository, error) {
	databaseURL = strings.TrimSpace(databaseURL)
	if databaseURL == "" {
		return nil, fmt.Errorf("database URL is empty")
	}

	config, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		return nil, fmt.Errorf("parse database url: %w", err)
	}

	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}

	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	if err := pool.Ping(pingCtx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping database: %w", err)
	}

	if _, err := pool.Exec(ctx, createTable); err != nil {
		pool.Close()
		return nil, fmt.Errorf("create table: %w", err)
	}

	return &Repository{pool: pool}, nil
}

// Save insere um log estruturado na tabela logs.
func (r *Repository) Save(ctx context.Context, entry domain.LogEntry) error {
	if r == nil || r.pool == nil {
		return fmt.Errorf("postgres repository is not initialized")
	}

	metadata, err := json.Marshal(entry.Metadata)
	if err != nil {
		return fmt.Errorf("marshal metadata: %w", err)
	}
	if string(metadata) == "null" {
		metadata = []byte("{}")
	}

	query := `
		INSERT INTO logs (id, timestamp, service, severity, message, metadata, received_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	_, err = r.pool.Exec(ctx, query,
		entry.ID,
		entry.Timestamp,
		entry.Service,
		entry.Severity.String(),
		entry.Message,
		metadata,
		entry.ReceivedAt,
	)
	if err != nil {
		return fmt.Errorf("execute insert: %w", err)
	}

	return nil
}

// Close encerra o pool de conexões PostgreSQL.
func (r *Repository) Close() error {
	if r != nil && r.pool != nil {
		r.pool.Close()
	}
	return nil
}