// Package usecase contém os casos de uso de processamento de logs.
package usecase

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/example/log-ingestor/internal/domain"
)

// MetricsRecorder é o contrato mínimo de métricas exigido pelo processador.
type MetricsRecorder interface {
	// ObserveAccepted incrementa o contador de logs aceitos.
	ObserveAccepted(severity domain.Severity)

	// ObserveFiltered incrementa o contador de logs filtrados.
	ObserveFiltered(severity domain.Severity)

	// ObserveValidationError incrementa o contador de erros de validação.
	ObserveValidationError()
}

// Processor implementa o caso de uso de ingestão de logs.
type Processor struct {
	repo     domain.LogRepository
	metrics  MetricsRecorder
	minLevel domain.Severity
	rules    map[string]domain.Severity
	keywords []string
}

// NewProcessor cria um Processor validando as dependências.
func NewProcessor(repo domain.LogRepository, metrics MetricsRecorder, minLevel domain.Severity, rules map[string]domain.Severity) (*Processor, error) {
	if repo == nil {
		return nil, errors.New("repository is nil")
	}
	if metrics == nil {
		return nil, errors.New("metrics is nil")
	}

	normalizedRules := make(map[string]domain.Severity, len(rules))
	for keyword, severity := range rules {
		normalizedRules[strings.ToLower(strings.TrimSpace(keyword))] = severity
	}

	keywords := make([]string, 0, len(normalizedRules))
	for keyword := range normalizedRules {
		keywords = append(keywords, keyword)
	}

	sort.Slice(keywords, func(i, j int) bool {
		return len(keywords[i]) > len(keywords[j])
	})

	return &Processor{
		repo:     repo,
		metrics:  metrics,
		minLevel: minLevel,
		rules:    normalizedRules,
		keywords: keywords,
	}, nil
}

// Ingest valida, normaliza, classifica e persiste um log recebido.
// O segundo retorno indica se o log foi aceito para armazenamento.
func (p *Processor) Ingest(ctx context.Context, raw domain.IncomingLog) (domain.LogEntry, bool, error) {
	if err := raw.Validate(); err != nil {
		p.metrics.ObserveValidationError()
		return domain.LogEntry{}, false, fmt.Errorf("validate log: %w", err)
	}

	timestamp, err := time.Parse(time.RFC3339, raw.Timestamp)
	if err != nil {
		p.metrics.ObserveValidationError()
		return domain.LogEntry{}, false, fmt.Errorf("parse timestamp: %w", err)
	}

	severity, err := p.classifySeverity(raw)
	if err != nil {
		p.metrics.ObserveValidationError()
		return domain.LogEntry{}, false, fmt.Errorf("classify severity: %w", err)
	}

	entry := domain.LogEntry{
		Timestamp: timestamp.UTC(),
		Service:   strings.ToLower(strings.TrimSpace(raw.Service)),
		Severity:  severity,
		Message:   strings.TrimSpace(raw.Message),
		TraceID:   strings.TrimSpace(raw.TraceID),
		UserID:    strings.TrimSpace(raw.UserID),
		Metadata:  normalizeMetadata(raw.Metadata),
	}

	if !severity.IsAtLeast(p.minLevel) {
		p.metrics.ObserveFiltered(severity)
		return entry, false, nil
	}

	if err := p.repo.Store(ctx, entry); err != nil {
		return domain.LogEntry{}, false, fmt.Errorf("store log: %w", err)
	}

	p.metrics.ObserveAccepted(severity)
	return entry, true, nil
}

func (p *Processor) classifySeverity(raw domain.IncomingLog) (domain.Severity, error) {
	if strings.TrimSpace(raw.Level) != "" {
		return domain.ParseSeverity(raw.Level)
	}
	return p.inferSeverity(raw.Message)
}

func (p *Processor) inferSeverity(message string) (domain.Severity, error) {
	lowerMessage := strings.ToLower(message)

	for _, keyword := range p.keywords {
		if strings.Contains(lowerMessage, keyword) {
			return p.rules[keyword], nil
		}
	}

	return domain.SeverityInfo, nil
}

func normalizeMetadata(metadata map[string]interface{}) map[string]interface{} {
	if metadata == nil {
		return nil
	}

	normalized := make(map[string]interface{}, len(metadata))
	for key, value := range metadata {
		normalized[key] = value
	}
	return normalized
}