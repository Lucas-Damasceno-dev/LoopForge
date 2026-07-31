package domain

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
)

// NewID gera um identificador hexadecimal aleatório de 128 bits.
func NewID() (string, error) {
	buffer := make([]byte, 16)
	if _, err := rand.Read(buffer); err != nil {
		return "", fmt.Errorf("generate id: %w", err)
	}
	return hex.EncodeToString(buffer), nil
}