package usecase_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/example/logingestor/internal/domain"
	"github.com/example/logingestor/internal/repository/memory"
	"github.com/example/logingestor/internal/usecase"
)

var fixedTime = time.Date(2025, 3, 26, 12, 0, 0, 0, time.UTC)

func TestIngest_ValidInfoStored(t *testing.T) {
	repo := memory.New()
	classifier := usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
		DefaultSeverity: domain.SeverityInfo,
	})
	useCase := usecase.NewIngestLogUseCase(repo, classifier, domain.SeverityInfo,
		usecase.WithClock(func() time.Time { return fixedTime }),
	)

	result, err := useCase.Ingest(context.Background(), domain.IngestLogRequest{
		Service:  "orders",
		Message:  "request completed",
		Severity: "INFO",
		Metadata: map[string]any{"trace_id": "abc"},
	})
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if !result.Stored {
		t.Fatal("expected log to be stored")
	}
	if result.Entry.Severity != domain.SeverityInfo {
		t.Fatalf("expected severity INFO, got %v", result.Entry.Severity)
	}
	if !result.Entry.Timestamp.Equal(fixedTime) {
		t.Fatalf("expected timestamp %v, got %v", fixedTime, result.Entry.Timestamp)
	}
	if repo.Count() != 1 {
		t.Fatalf("expected 1 stored log, got %d", repo.Count())
	}
}

func TestIngest_ClassifiesErrorWhenNoSeverity(t *testing.T) {
	repo := memory.New()
	classifier := usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
		DefaultSeverity: domain.SeverityInfo,
		ErrorKeywords:   []string{"failed", "panic"},
	})
	useCase := usecase.NewIngestLogUseCase(repo, classifier, domain.SeverityInfo,
		usecase.WithClock(func() time.Time { return fixedTime }),
	)

	result, err := useCase.Ingest(context.Background(), domain.IngestLogRequest{
		Service: "checkout",
		Message: "payment failed after timeout",
	})
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if result.Entry.Severity != domain.SeverityError {
		t.Fatalf("expected severity ERROR, got %v", result.Entry.Severity)
	}
	if !result.Stored {
		t.Fatal("expected log to be stored")
	}
}

func TestIngest_FiltersBelowMinSeverity(t *testing.T) {
	repo := memory.New()
	classifier := usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
		DefaultSeverity: domain.SeverityInfo,
	})
	useCase := usecase.NewIngestLogUseCase(repo, classifier, domain.SeverityError,
		usecase.WithClock(func() time.Time { return fixedTime }),
	)

	result, err := useCase.Ingest(context.Background(), domain.IngestLogRequest{
		Service:  "orders",
		Message:  "something is slow",
		Severity: "WARN",
	})
	if err != nil {
		t.Fatalf("Ingest() error = %v", err)
	}
	if result.Stored {
		t.Fatal("expected WARN log to be filtered")
	}
	if repo.Count() != 0 {
		t.Fatalf("expected 0 stored logs, got %d", repo.Count())
	}
}

func TestIngest_InvalidSeverityReturnsValidationError(t *testing.T) {
	repo := memory.New()
	classifier := usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
		DefaultSeverity: domain.SeverityInfo,
	})
	useCase := usecase.NewIngestLogUseCase(repo, classifier, domain.SeverityInfo)

	_, err := useCase.Ingest(context.Background(), domain.IngestLogRequest{
		Service:  "orders",
		Message:  "hello",
		Severity: "DEBUG",
	})
	if err == nil {
		t.Fatal("expected error")
	}

	var validationErr *domain.ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("expected ValidationError, got %T", err)
	}
}

func TestIngest_MissingServiceReturnsValidationError(t *testing.T) {
	repo := memory.New()
	classifier := usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
		DefaultSeverity: domain.SeverityInfo,
	})
	useCase := usecase.NewIngestLogUseCase(repo, classifier, domain.SeverityInfo)

	_, err := useCase.Ingest(context.Background(), domain.IngestLogRequest{
		Message: "hello",
	})
	if err == nil {
		t.Fatal("expected error")
	}

	var validationErr *domain.ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("expected ValidationError, got %T", err)
	}
}