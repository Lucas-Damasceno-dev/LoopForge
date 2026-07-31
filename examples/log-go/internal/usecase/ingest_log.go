package usecase

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/example/logingestor/internal/domain"
)

// Option é uma função de configuração opcional para IngestLogUseCase.
type Option func(*IngestLogUseCase)

// IngestLogUseCase orquestra validação, normalização, classificação e persistência.
type IngestLogUseCase struct {
	repo        domain.LogRepository
	classifier  *ConfigurableClassifier
	minSeverity domain.Severity
	now         func() time.Time
}

// NewIngestLogUseCase cria um caso de uso de ingestão de logs.
func NewIngestLogUseCase(repo domain.LogRepository, classifier *ConfigurableClassifier, minSeverity domain.Severity, opts ...Option) *IngestLogUseCase {
	if classifier == nil {
		classifier = NewConfigurableClassifier(ClassifierConfig{DefaultSeverity: domain.SeverityInfo})
	}
	if minSeverity == domain.SeverityUnknown {
		minSeverity = domain.SeverityInfo
	}

	useCase := &IngestLogUseCase{
		repo:        repo,
		classifier:  classifier,
		minSeverity: minSeverity,
		now:         time.Now,
	}

	for _, opt := range opts {
		opt(useCase)
	}

	return useCase
}

// WithClock injeta uma função de relógio para testes.
func WithClock(now func() time.Time) Option {
	return func(useCase *IngestLogUseCase) {
		if now != nil {
			useCase.now = now
		}
	}
}

// Ingest valida, normaliza, classifica, filtra e persiste um log.
func (uc *IngestLogUseCase) Ingest(ctx context.Context, req domain.IngestLogRequest) (domain.IngestResult, error) {
	if err := ctx.Err(); err != nil {
		return domain.IngestResult{}, fmt.Errorf("ingest context: %w", err)
	}
	if err := uc.validate(req); err != nil {
		return domain.IngestResult{}, err
	}

	now := uc.now().UTC()
	timestamp := now
	if req.Timestamp != nil {
		timestamp = req.Timestamp.UTC()
	}

	id, err := domain.NewID()
	if err != nil {
		return domain.IngestResult{}, fmt.Errorf("generate log id: %w", err)
	}

	var severity domain.Severity
	if req.Severity != "" {
		severity, err = domain.ParseSeverity(req.Severity)
		if err != nil {
			return domain.IngestResult{}, domain.NewValidationError("severity", err.Error())
		}
	} else {
		severity = uc.classifier.Classify(req)
	}

	metadata := req.Metadata
	if metadata == nil {
		metadata = map[string]any{}
	}

	entry := domain.LogEntry{
		ID:         id,
		Timestamp:  timestamp,
		Service:    strings.TrimSpace(req.Service),
		Severity:   severity,
		Message:    strings.TrimSpace(req.Message),
		Metadata:   metadata,
		ReceivedAt: now,
	}

	if !severity.MeetsMinimum(uc.minSeverity) {
		return domain.IngestResult{Entry: entry, Stored: false}, nil
	}

	if err := uc.repo.Save(ctx, entry); err != nil {
		return domain.IngestResult{}, fmt.Errorf("persist log: %w", err)
	}

	return domain.IngestResult{Entry: entry, Stored: true}, nil
}

// validate aplica as regras de validação de campos essenciais.
func (uc *IngestLogUseCase) validate(req domain.IngestLogRequest) error {
	if strings.TrimSpace(req.Service) == "" {
		return domain.NewValidationError("service", "service is required")
	}
	if strings.TrimSpace(req.Message) == "" {
		return domain.NewValidationError("message", "message is required")
	}
	if req.Severity != "" {
		if _, err := domain.ParseSeverity(req.Severity); err != nil {
			return domain.NewValidationError("severity", err.Error())
		}
	}
	return nil
}