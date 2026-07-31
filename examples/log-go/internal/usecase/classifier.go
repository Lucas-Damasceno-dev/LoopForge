package usecase

import (
	"fmt"
	"strings"

	"github.com/example/logingestor/internal/domain"
)

// ClassifierConfig define as regras configuráveis de classificação automática.
type ClassifierConfig struct {
	DefaultSeverity domain.Severity
	ErrorKeywords   []string
	WarnKeywords    []string
}

// ConfigurableClassifier classifica logs por palavras-chave em message e metadata.
type ConfigurableClassifier struct {
	defaultSeverity domain.Severity
	errorKeywords   []string
	warnKeywords    []string
}

// NewConfigurableClassifier cria um classificador com regras configuráveis.
func NewConfigurableClassifier(cfg ClassifierConfig) *ConfigurableClassifier {
	if cfg.DefaultSeverity == domain.SeverityUnknown {
		cfg.DefaultSeverity = domain.SeverityInfo
	}

	return &ConfigurableClassifier{
		defaultSeverity: cfg.DefaultSeverity,
		errorKeywords:   normalizeKeywords(cfg.ErrorKeywords),
		warnKeywords:    normalizeKeywords(cfg.WarnKeywords),
	}
}

// Classify inspeciona a mensagem e os metadados para determinar a severidade.
func (c *ConfigurableClassifier) Classify(input domain.IngestLogRequest) domain.Severity {
	parts := make([]string, 0, len(input.Metadata)+1)
	parts = append(parts, strings.ToLower(input.Message))

	for _, value := range input.Metadata {
		if value == nil {
			continue
		}
		if text, ok := value.(string); ok {
			parts = append(parts, strings.ToLower(text))
			continue
		}
		parts = append(parts, strings.ToLower(fmt.Sprintf("%v", value)))
	}

	haystack := strings.Join(parts, "\n")

	if containsAny(haystack, c.errorKeywords) {
		return domain.SeverityError
	}
	if containsAny(haystack, c.warnKeywords) {
		return domain.SeverityWarn
	}

	return c.defaultSeverity
}

// normalizeKeywords limpa e padroniza as palavras-chave para comparação.
func normalizeKeywords(keywords []string) []string {
	result := make([]string, 0, len(keywords))
	for _, keyword := range keywords {
		value := strings.ToLower(strings.TrimSpace(keyword))
		if value != "" {
			result = append(result, value)
		}
	}
	return result
}

// containsAny verifica se o texto contém alguma das palavras-chave.
func containsAny(haystack string, keywords []string) bool {
	for _, keyword := range keywords {
		if keyword != "" && strings.Contains(haystack, keyword) {
			return true
		}
	}
	return false
}