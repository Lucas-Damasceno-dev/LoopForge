package memory_test

import (
	"context"
	"testing"
	"time"

	"github.com/example/logingestor/internal/domain"
	"github.com/example/logingestor/internal/repository/memory"
)

func TestRepositorySaveAndFind(t *testing.T) {
	repo := memory.New()
	entry := domain.LogEntry{
		ID:         "log-1",
		Timestamp:  time.Now().UTC(),
		Service:    "orders",
		Severity:   domain.SeverityInfo,
		Message:    "hello",
		Metadata:   map[string]any{},
		ReceivedAt: time.Now().UTC(),
	}

	if err := repo.Save(context.Background(), entry); err != nil {
		t.Fatalf("Save() error = %v", err)
	}

	got, err := repo.FindByID(context.Background(), "log-1")
	if err != nil {
		t.Fatalf("FindByID() error = %v", err)
	}
	if got.ID != entry.ID {
		t.Fatalf("expected ID %q, got %q", entry.ID, got.ID)
	}
	if repo.Count() != 1 {
		t.Fatalf("expected count 1, got %d", repo.Count())
	}
}