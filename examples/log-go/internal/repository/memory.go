package repository

import (
	"context"
	"errors"
	"sync"

	"github.com/example/log-ingestor/internal/domain"
)

// MemoryRepository é um repositório em memória para desenvolvimento e testes.
type MemoryRepository struct {
	mu   sync.RWMutex
	logs []*domain.LogEntry
}

// NewMemoryRepository cria um repositório em memória.
func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{}
}

// Insert adiciona um log ao repositório.
func (r *MemoryRepository) Insert(_ context.Context, entry *domain.LogEntry) error {
	if entry == nil {
		return errors.New("nil log entry")
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.logs = append(r.logs, entry)
	return nil
}

// Len retorna a quantidade de logs armazenados.
func (r *MemoryRepository) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.logs)
}

// Close é no-op para o repositório em memória.
func (r *MemoryRepository) Close() error {
	return nil
}