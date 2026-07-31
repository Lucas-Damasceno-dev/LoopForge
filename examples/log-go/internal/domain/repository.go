package domain

import "context"

// LogRepository define o contrato de persistência de logs.
type LogRepository interface {
	// Store persiste um log já processado.
	Store(ctx context.Context, log LogEntry) error

	// Close libera recursos associados ao repositório.
	Close() error
}