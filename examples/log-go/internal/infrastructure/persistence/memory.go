// Package persistence contém implementações de repositórios.
package persistence

import (
	"context"
	"sync"

	"github.com/example/log-ingestor/internal/domain"
)

// MemoryRepository é um repositório em memória para desenvolvimento e testes.
type MemoryRepository struct {
	mu   sync.RWMutex
	logs []domain.LogEntry
}

// NewMemoryRepository cria um repositório em memória vazio.
func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{
		logs: make([]domain.LogEntry, 0),
	}
}

// Store adiciona um log ao repositório.
func (r *MemoryRepository) Store(ctx context.Context, log domain.LogEntry) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}

	r.mu.Lock()
	defer r.mu.Unlock()
	r.logs = append(r.logs, log)
	return nil
}

// Close não possui recursos externos a liberar.
func (r *MemoryRepository) Close() error {
	return nil
}

// Len retorna a quantidade de logs armazenados.
func (r *MemoryRepository) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.logs)
}