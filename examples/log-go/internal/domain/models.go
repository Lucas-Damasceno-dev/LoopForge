package domain

import (
	"context"
	"time"
)

// Severity representa o nível de severidade de um log.
type Severity int

const (
	// SeverityUnknown indica severidade não reconhecida.
	SeverityUnknown Severity = iota
	// SeverityInfo representa logs informativos.
	SeverityInfo
	// SeverityWarn representa avisos.
	SeverityWarn
	// SeverityError representa erros.
	SeverityError
)

// IngestLogRequest é o payload aceito pelo endpoint de ingestão.
type IngestLogRequest struct {
	Timestamp *time.Time      `json:"timestamp,omitempty"`
	Service   string          `json:"service"`
	Severity  string          `json:"severity,omitempty"`
	Message   string          `json:"message"`
	Metadata  map[string]any  `json:"metadata,omitempty"`
}

// LogEntry é o log normalizado e persistido.
type LogEntry struct {
	ID         string         `json:"id"`
	Timestamp  time.Time      `json:"timestamp"`
	Service    string         `json:"service"`
	Severity   Severity       `json:"severity"`
	Message    string         `json:"message"`
	Metadata   map[string]any `json:"metadata,omitempty"`
	ReceivedAt time.Time      `json:"received_at"`
}

// IngestResult contém o resultado do caso de uso de ingestão.
type IngestResult struct {
	Entry  LogEntry
	Stored bool
}

// LogRepository define o contrato de persistência de logs.
type LogRepository interface {
	Save(ctx context.Context, entry LogEntry) error
	Close() error
}