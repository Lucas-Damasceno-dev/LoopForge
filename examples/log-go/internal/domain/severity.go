package domain

import (
	"fmt"
	"strings"
)

// String retorna a representação textual da severidade.
func (s Severity) String() string {
	switch s {
	case SeverityInfo:
		return "INFO"
	case SeverityWarn:
		return "WARN"
	case SeverityError:
		return "ERROR"
	default:
		return "UNKNOWN"
	}
}

// Valid informa se a severidade é conhecida.
func (s Severity) Valid() bool {
	return s >= SeverityInfo && s <= SeverityError
}

// MeetsMinimum informa se a severidade atende a um nível mínimo de filtro.
func (s Severity) MeetsMinimum(min Severity) bool {
	return s >= min
}

// ParseSeverity converte uma string em Severity.
func ParseSeverity(value string) (Severity, error) {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "INFO":
		return SeverityInfo, nil
	case "WARN", "WARNING":
		return SeverityWarn, nil
	case "ERROR", "FATAL":
		return SeverityError, nil
	default:
		return SeverityUnknown, fmt.Errorf("unsupported severity %q", value)
	}
}