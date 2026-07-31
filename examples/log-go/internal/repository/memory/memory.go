package memory

import (
	"context"
	"fmt"
	"sync"

	"github.com/example/logingestor/internal/domain"
)

// Repository é uma implementação em memória de domain.LogRepository.
type Repository struct {
	mu   sync.RWMutex
	logs map[string]domain.LogEntry
}

// New cria um repositório em memória vazio.
func New() *Repository {
	return &Repository{
		logs: make(map[string]domain.LogEntry),
	}
}

// Save armazena uma entrada de log no mapa interno.
func (r *Repository) Save(ctx context.Context, entry domain.LogEntry) error {
	if r == nil {
		return fmt.Errorf("memory repository is nil")
	}
	if err := ctx.Err(); err != nil {
		return err
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	r.logs[entry.ID] = entry
	return nil
}

// FindByID busca uma entrada de log pelo identificador.
func (r *Repository) FindByID(ctx context.Context, id string) (domain.LogEntry, error) {
	if r == nil {
		return domain.LogEntry{}, fmt.Errorf("memory repository is nil")
	}
	if err := ctx.Err(); err != nil {
		return domain.LogEntry{}, err
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	entry, ok := r.logs[id]
	if !ok {
		return domain.LogEntry{}, fmt.Errorf("log %q not found", id)
	}
	return entry, nil
}

// Count retorna a quantidade de logs armazenados.
func (r *Repository) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return len(r.logs)
}

// Close libera recursos; implementação em memória não possui recursos externos.
func (r *Repository) Close() error {
	return nil
}