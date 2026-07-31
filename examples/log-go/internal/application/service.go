package application

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/example/log-ingestor/internal/domain"
)

// LogRepository abstrai a persistência de logs.
type LogRepository interface {
	Insert(ctx context.Context, entry *domain.LogEntry) error
}

// IngestResult é o resultado do processamento de um log.
type IngestResult struct {
	Entry     *domain.LogEntry
	Persisted bool
	Filtered  bool
	Reason    string
}

// LogIngestionService contém o caso de uso de ingestão de logs.
type LogIngestionService struct {
	repo        LogRepository
	classifier  SeverityClassifier
	minSeverity domain.Severity
	logger      *slog.Logger
}

// NewLogIngestionService cria um serviço de ingestão.
func NewLogIngestionService(
	repo LogRepository,
	classifier SeverityClassifier,
	minSeverity domain.Severity,
	logger *slog.Logger,
) *LogIngestionService {
	if logger == nil {
		logger = slog.Default()
	}
	return &LogIngestionService{
		repo:        repo,
		classifier:  classifier,
		minSeverity: minSeverity,
		logger:      logger,
	}
}

// Ingest valida, normaliza, classifica e persiste um log quando permitido.
func (s *LogIngestionService) Ingest(ctx context.Context, req domain.IngestRequest) (IngestResult, error) {
	service := strings.TrimSpace(req.Service)
	if service == "" {
		return IngestResult{}, fmt.Errorf("%w", domain.ErrServiceRequired)
	}

	message := strings.TrimSpace(req.Message)
	if message == "" {
		return IngestResult{}, fmt.Errorf("%w", domain.ErrMessageRequired)
	}

	timestamp, err := parseTimestamp(req.Timestamp)
	if err != nil {
		return IngestResult{}, err
	}

	var severity domain.Severity
	if req.Severity == "" {
		severity = s.classifier.Classify(message, req.Metadata)
	} else {
		severity, err = domain.ParseSeverity(req.Severity)
		if err != nil {
			return IngestResult{}, fmt.Errorf("invalid severity field: %w", err)
		}
	}

	id, err := domain.NewID()
	if err != nil {
		return IngestResult{}, err
	}

	metadata := req.Metadata
	if metadata == nil {
		metadata = make(map[string]any)
	}

	entry := &domain.LogEntry{
		ID:        id,
		Timestamp: timestamp.UTC(),
		Service:   service,
		Severity:  severity,
		Message:   message,
		Metadata:  metadata,
	}

	if !s.minSeverity.Allows(severity) {
		s.logger.Debug("log filtered by min severity",
			"severity", severity,
			"min_severity", s.minSeverity,
			"service", service,
		)
		return IngestResult{
			Entry:     entry,
			Persisted: false,
			Filtered:  true,
			Reason:    fmt.Sprintf("severity %s is below minimum %s", severity, s.minSeverity),
		}, nil
	}

	if err := s.repo.Insert(ctx, entry); err != nil {
		return IngestResult{}, fmt.Errorf("persist log: %w", err)
	}

	s.logger.Info("log ingested",
		"id", entry.ID,
		"service", entry.Service,
		"severity", entry.Severity,
	)

	return IngestResult{Entry: entry, Persisted: true, Filtered: false}, nil
}

func parseTimestamp(value string) (time.Time, error) {
	if value == "" {
		return time.Now(), nil
	}

	ts, err := time.Parse(time.RFC3339Nano, value)
	if err != nil {
		return time.Time{}, fmt.Errorf("%w: %q", domain.ErrTimestampInvalid, value)
	}
	return ts, nil
}