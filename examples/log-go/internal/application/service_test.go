package application

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"sync"
	"testing"

	"github.com/example/log-ingestor/internal/domain"
)

type fakeRepository struct {
	mu        sync.Mutex
	entries   []*domain.LogEntry
	insertErr error
}

func (f *fakeRepository) Insert(_ context.Context, entry *domain.LogEntry) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.insertErr != nil {
		return f.insertErr
	}
	if entry == nil {
		return errors.New("nil log entry")
	}
	f.entries = append(f.entries, entry)
	return nil
}

func (f *fakeRepository) Len() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.entries)
}

func newTestService(minSeverity domain.Severity, repo *fakeRepository) *LogIngestionService {
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	classifier := NewKeywordClassifier([]string{"error", "fatal"}, []string{"warn", "warning"})
	return NewLogIngestionService(repo, classifier, minSeverity, logger)
}

func TestIngestValidLogPersists(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityInfo, repo)

	result, err := svc.Ingest(context.Background(), domain.IngestRequest{
		Service:  "  payment  ",
		Message:  "  transaction processed  ",
		Severity: "INFO",
		Metadata: map[string]any{"tx": "123"},
	})
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if !result.Persisted || result.Filtered {
		t.Fatalf("expected persisted log, got %+v", result)
	}
	if repo.Len() != 1 {
		t.Fatalf("repo.Len() = %d, want 1", repo.Len())
	}

	entry := repo.entries[0]
	if entry.Service != "payment" {
		t.Errorf("Service = %q, want payment", entry.Service)
	}
	if entry.Message != "transaction processed" {
		t.Errorf("Message = %q, want transaction processed", entry.Message)
	}
	if entry.Severity != domain.SeverityInfo {
		t.Errorf("Severity = %q, want INFO", entry.Severity)
	}
	if entry.ID == "" {
		t.Error("expected generated ID")
	}
	if entry.Timestamp.IsZero() {
		t.Error("expected timestamp to be set")
	}
	if entry.Metadata["tx"] != "123" {
		t.Errorf("Metadata[tx] = %v, want 123", entry.Metadata["tx"])
	}
}

func TestIngestFiltersBelowMinimumSeverity(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityError, repo)

	result, err := svc.Ingest(context.Background(), domain.IngestRequest{
		Service:  "api",
		Message:  "something happened",
		Severity: "WARN",
	})
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if !result.Filtered || result.Persisted {
		t.Fatalf("expected filtered log, got %+v", result)
	}
	if repo.Len() != 0 {
		t.Fatalf("repo.Len() = %d, want 0", repo.Len())
	}
}

func TestIngestClassifiesSeverityByKeyword(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityInfo, repo)

	result, err := svc.Ingest(context.Background(), domain.IngestRequest{
		Service: "api",
		Message: "database connection error",
	})
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if result.Entry.Severity != domain.SeverityError {
		t.Errorf("Severity = %q, want ERROR", result.Entry.Severity)
	}
}

func TestIngestMissingService(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityInfo, repo)

	_, err := svc.Ingest(context.Background(), domain.IngestRequest{Message: "op"})
	if !errors.Is(err, domain.ErrServiceRequired) {
		t.Fatalf("expected ErrServiceRequired, got %v", err)
	}
}

func TestIngestMissingMessage(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityInfo, repo)

	_, err := svc.Ingest(context.Background(), domain.IngestRequest{Service: "api"})
	if !errors.Is(err, domain.ErrMessageRequired) {
		t.Fatalf("expected ErrMessageRequired, got %v", err)
	}
}

func TestIngestInvalidTimestamp(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityInfo, repo)

	_, err := svc.Ingest(context.Background(), domain.IngestRequest{
		Service:   "api",
		Message:   "op",
		Timestamp: "not-a-time",
	})
	if !errors.Is(err, domain.ErrTimestampInvalid) {
		t.Fatalf("expected ErrTimestampInvalid, got %v", err)
	}
}

func TestIngestInvalidSeverity(t *testing.T) {
	repo := &fakeRepository{}
	svc := newTestService(domain.SeverityInfo, repo)

	_, err := svc.Ingest(context.Background(), domain.IngestRequest{
		Service:  "api",
		Message:  "op",
		Severity: "DEBUG",
	})
	if !errors.Is(err, domain.ErrSeverityInvalid) {
		t.Fatalf("expected ErrSeverityInvalid, got %v", err)
	}
}