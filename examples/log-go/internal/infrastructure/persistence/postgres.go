package persistence

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/lib/pq"

	"github.com/example/log-ingestor/internal/domain"
)

// PostgresRepository persiste logs em PostgreSQL.
type PostgresRepository struct {
	db *sql.DB
}

// NewPostgresRepository abre uma conexão e verifica a disponibilidade do banco.
func NewPostgresRepository(databaseURL string) (*PostgresRepository, error) {
	db, err := sql.Open("postgres", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("open postgres connection: %w", err)
	}

	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}

	return &PostgresRepository{db: db}, nil
}

// Store insere um log na tabela logs.
func (r *PostgresRepository) Store(ctx context.Context, log domain.LogEntry) error {
	metadataJSON := []byte("{}")
	if log.Metadata != nil {
		var err error
		metadataJSON, err = json.Marshal(log.Metadata)
		if err != nil {
			return fmt.Errorf("marshal metadata: %w", err)
		}
	}

	_, err := r.db.ExecContext(ctx, `
		INSERT INTO logs (timestamp, service, severity, message, trace_id, user_id, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
	`,
		log.Timestamp.UTC(),
		log.Service,
		log.Severity.String(),
		log.Message,
		nullString(log.TraceID),
		nullString(log.UserID),
		string(metadataJSON),
	)
	if err != nil {
		return fmt.Errorf("insert log: %w", err)
	}

	return nil
}

// Close encerra o pool de conexões.
func (r *PostgresRepository) Close() error {
	if r.db == nil {
		return nil
	}
	return r.db.Close()
}

func nullString(value string) sql.NullString {
	if value == "" {
		return sql.NullString{}
	}
	return sql.NullString{String: value, Valid: true}
}