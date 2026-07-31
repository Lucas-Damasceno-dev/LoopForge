package domain

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

// Severity representa o nível de severidade de um log.
type Severity string

const (
	// SeverityInfo é o nível mais baixo.
	SeverityInfo Severity = "INFO"
	// SeverityWarn é o nível intermediário.
	SeverityWarn Severity = "WARN"
	// SeverityError é o nível mais alto.
	SeverityError Severity = "ERROR"
)

var (
	// ErrServiceRequired indica que o campo service é obrigatório.
	ErrServiceRequired = errors.New("service is required")
	// ErrMessageRequired indica que o campo message é obrigatório.
	ErrMessageRequired = errors.New("message is required")
	// ErrTimestampInvalid indica que o timestamp está em formato inválido.
	ErrTimestampInvalid = errors.New("timestamp must be in RFC3339 format")
	// ErrSeverityInvalid indica que a severidade está fora dos valores aceitos.
	ErrSeverityInvalid = errors.New("severity must be one of INFO, WARN, ERROR")
)

// LogEntry representa um log já normalizado.
type LogEntry struct {
	ID        string         `json:"id,omitempty"`
	Timestamp time.Time      `json:"timestamp"`
	Service   string         `json:"service"`
	Severity  Severity       `json:"severity"`
	Message   string         `json:"message"`
	Metadata  map[string]any `json:"metadata,omitempty"`
}

// IngestRequest é o payload aceito pelo endpoint de ingestão.
type IngestRequest struct {
	Timestamp string         `json:"timestamp"`
	Service   string         `json:"service"`
	Message   string         `json:"message"`
	Severity  string         `json:"severity,omitempty"`
	Metadata  map[string]any `json:"metadata,omitempty"`
}

// Rank retorna um peso numérico para a severidade.
func (s Severity) Rank() int {
	switch s {
	case SeverityInfo:
		return 0
	case SeverityWarn:
		return 1
	case SeverityError:
		return 2
	default:
		return -1
	}
}

// Valid informa se a severidade é reconhecida.
func (s Severity) Valid() bool {
	return s.Rank() >= 0
}

// Allows informa se o nível mínimo s aceita a severidade candidata.
func (s Severity) Allows(candidate Severity) bool {
	return candidate.Rank() >= s.Rank()
}

// ParseSeverity converte uma string em Severity.
func ParseSeverity(value string) (Severity, error) {
	switch Severity(strings.ToUpper(strings.TrimSpace(value))) {
	case SeverityInfo:
		return SeverityInfo, nil
	case SeverityWarn:
		return SeverityWarn, nil
	case SeverityError:
		return SeverityError, nil
	default:
		return "", fmt.Errorf("%w: %q", ErrSeverityInvalid, value)
	}
}

// NewID gera um identificador aleatório para o log.
func NewID() (string, error) {
	raw := make([]byte, 16)
	if _, err := rand.Read(raw); err != nil {
		return "", fmt.Errorf("generate log id: %w", err)
	}
	return hex.EncodeToString(raw), nil
}