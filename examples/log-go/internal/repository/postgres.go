package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/example/log-ingestor/internal/domain"
	_ "github.com/lib/pq"
)

// PostgresRepository implementa a persistência em PostgreSQL.
type PostgresRepository struct {
	db *sql.DB
}

// NewPostgresRepository cria e testa a conexão com o PostgreSQL.
func NewPostgresRepository(ctx context.Context, dsn string) (*PostgresRepository, error) {
	if dsn == "" {
		return nil, errors.New("database url is required")
	}

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("open postgres: %w", err)
	}

	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}

	return &PostgresRepository{db: db}, nil
}

// Insert persiste um log na tabela logs.
func (r *PostgresRepository) Insert(ctx context.Context, entry *domain.LogEntry) error {
	metadata, err := json.Marshal(entry.Metadata)
	if err != nil {
		return fmt.Errorf("marshal metadata: %w", err)
	}

	const query = `
		INSERT INTO logs (id, timestamp, service, severity, message, metadata)
		VALUES ($1, $2, $3, $4, $5, $6)
	`

	if _, err := r.db.ExecContext(ctx, query,
		entry.ID,
		entry.Timestamp,
		entry.Service,
		entry.Severity,
		entry.Message,
		metadata,
	); err != nil {
		return fmt.Errorf("insert log: %w", err)
	}

	return nil
}

// Ping verifica a conectividade com o banco.
func (r *PostgresRepository) Ping(ctx context.Context) error {
	if err := r.db.PingContext(ctx); err != nil {
		return fmt.Errorf("ping postgres: %w", err)
	}
	return nil
}

// Close encerra a conexão com o PostgreSQL.
func (r *PostgresRepository) Close() error {
	if err := r.db.Close(); err != nil {
		return fmt.Errorf("close postgres: %w", err)
	}
	return nil
}