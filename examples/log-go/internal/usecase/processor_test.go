package usecase

import (
	"context"
	"errors"
	"testing"

	"github.com/example/log-ingestor/internal/domain"
	"github.com/example/log-ingestor/internal/infrastructure/persistence"
)

type metricsStub struct {
	received         int
	validationErrors int
	accepted         map[domain.Severity]int
	filtered         map[domain.Severity]int
}

func newMetricsStub() *metricsStub {
	return &metricsStub{
		accepted: make(map[domain.Severity]int),
		filtered: make(map[domain.Severity]int),
	}
}

func (s *metricsStub) ObserveReceived()                        { s.received++ }
func (s *metricsStub) ObserveValidationError()                 { s.validationErrors++ }
func (s *metricsStub) ObserveAccepted(sev domain.Severity)     { s.accepted[sev]++ }
func (s *metricsStub) ObserveFiltered(sev domain.Severity)     { s.filtered[sev]++ }
func (s *metricsStub) ObserveHTTPRequest(string, string, string, float64) {}

type failingRepository struct{}

func (f *failingRepository) Store(context.Context, domain.LogEntry) error {
	return errors.New("store failed")
}

func (f *failingRepository) Close() error { return nil }

func TestProcessor_IngestAcceptsValidLog(t *testing.T) {
	repo := persistence.NewMemoryRepository()
	metrics := newMetricsStub()

	processor, err := NewProcessor(repo, metrics, domain.SeverityInfo, nil)
	if err != nil {
		t.Fatalf("NewProcessor() error = %v", err)
	}

	raw := domain.IncomingLog{
		Timestamp: "2025-03-26T10:00:00Z",
		Service:   "auth",
		Message:   "user logged in",
		Level:     "INFO",
	}

	entry, accepted, err := processor.Ingest(context.Background(), raw)
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if !accepted {
		t.Fatal("expected accepted log")
	}
	if entry.Severity != domain.SeverityInfo {
		t.Fatalf("Severity = %v, want INFO", entry.Severity)
	}
	if repo.Len() != 1 {
		t.Fatalf("repo.Len() = %d, want 1", repo.Len())
	}
	if metrics.accepted[domain.SeverityInfo] != 1 {
		t.Fatal("expected accepted metric")
	}
}

func TestProcessor_IngestFiltersBelowMinLevel(t *testing.T) {
	repo := persistence.NewMemoryRepository()
	metrics := newMetricsStub()

	processor, err := NewProcessor(repo, metrics, domain.SeverityError, nil)
	if err != nil {
		t.Fatalf("NewProcessor() error = %v", err)
	}

	raw := domain.IncomingLog{
		Timestamp: "2025-03-26T10:00:00Z",
		Service:   "auth",
		Message:   "user logged in",
		Level:     "INFO",
	}

	_, accepted, err := processor.Ingest(context.Background(), raw)
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if accepted {
		t.Fatal("expected filtered log")
	}
	if repo.Len() != 0 {
		t.Fatalf("repo.Len() = %d, want 0", repo.Len())
	}
	if metrics.filtered[domain.SeverityInfo] != 1 {
		t.Fatal("expected filtered metric")
	}
}

func TestProcessor_IngestInfersSeverityFromMessage(t *testing.T) {
	repo := persistence.NewMemoryRepository()
	metrics := newMetricsStub()
	rules := map[string]domain.Severity{
		"failed": domain.SeverityError,
		"warn":   domain.SeverityWarn,
	}

	processor, err := NewProcessor(repo, metrics, domain.SeverityInfo, rules)
	if err != nil {
		t.Fatalf("NewProcessor() error = %v", err)
	}

	raw := domain.IncomingLog{
		Timestamp: "2025-03-26T10:00:00Z",
		Service:   "auth",
		Message:   "authentication failed",
	}

	entry, accepted, err := processor.Ingest(context.Background(), raw)
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if !accepted {
		t.Fatal("expected accepted log")
	}
	if entry.Severity != domain.SeverityError {
		t.Fatalf("Severity = %v, want ERROR", entry.Severity)
	}
}

func TestProcessor_IngestValidationError(t *testing.T) {
	repo := persistence.NewMemoryRepository()
	metrics := newMetricsStub()

	processor, err := NewProcessor(repo, metrics, domain.SeverityInfo, nil)
	if err != nil {
		t.Fatalf("NewProcessor() error = %v", err)
	}

	raw := domain.IncomingLog{
		Timestamp: "2025-03-26T10:00:00Z",
		Message:   "missing service",
	}

	_, _, err = processor.Ingest(context.Background(), raw)
	if err == nil {
		t.Fatal("expected validation error")
	}
	if !errors.Is(err, domain.ErrEmptyService) {
		t.Fatalf("expected ErrEmptyService, got %v", err)
	}
	if metrics.validationErrors != 1 {
		t.Fatal("expected validation metric")
	}
}

func TestProcessor_IngestStoreError(t *testing.T) {
	metrics := newMetricsStub()

	processor, err := NewProcessor(&failingRepository{}, metrics, domain.SeverityInfo, nil)
	if err != nil {
		t.Fatalf("NewProcessor() error = %v", err)
	}

	raw := domain.IncomingLog{
		Timestamp: "2025-03-26T10:00:00Z",
		Service:   "auth",
		Message:   "hello",
		Level:     "INFO",
	}

	_, _, err = processor.Ingest(context.Background(), raw)
	if err == nil {
		t.Fatal("expected store error")
	}
}