package application

import (
	"strings"

	"github.com/example/log-ingestor/internal/domain"
)

// SeverityClassifier define a regra de classificação automática de severidade.
type SeverityClassifier interface {
	Classify(message string, metadata map[string]any) domain.Severity
}

// KeywordClassifier classifica a severidade com base em palavras-chave configuráveis.
type KeywordClassifier struct {
	errorKeywords []string
	warnKeywords  []string
}

// NewKeywordClassifier cria um classificador por palavras-chave.
func NewKeywordClassifier(errorKeywords, warnKeywords []string) *KeywordClassifier {
	return &KeywordClassifier{
		errorKeywords: errorKeywords,
		warnKeywords:  warnKeywords,
	}
}

// Classify retorna ERROR, WARN ou INFO conforme as palavras encontradas na mensagem.
func (c *KeywordClassifier) Classify(message string, _ map[string]any) domain.Severity {
	msg := strings.ToLower(message)

	for _, keyword := range c.errorKeywords {
		if strings.Contains(msg, keyword) {
			return domain.SeverityError
		}
	}

	for _, keyword := range c.warnKeywords {
		if strings.Contains(msg, keyword) {
			return domain.SeverityWarn
		}
	}

	return domain.SeverityInfo
}