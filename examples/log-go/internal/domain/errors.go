package domain

import "fmt"

// ValidationError representa uma falha de validação de domínio.
type ValidationError struct {
	Field  string
	Reason string
}

// Error implementa a interface error.
func (e *ValidationError) Error() string {
	return fmt.Sprintf("%s: %s", e.Field, e.Reason)
}

// NewValidationError cria um erro de validação estruturado.
func NewValidationError(field, reason string) error {
	return &ValidationError{Field: field, Reason: reason}
}