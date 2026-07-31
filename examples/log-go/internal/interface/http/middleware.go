package httpapi

import (
	"crypto/subtle"
	"net/http"
	"strings"
)

// RequireAPIKey protege um handler com autenticação por chave de API.
func RequireAPIKey(apiKey string, next http.Handler) http.Handler {
	expected := []byte(apiKey)

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		provided := []byte(strings.TrimSpace(r.Header.Get("X-API-Key")))

		if subtle.ConstantTimeCompare(provided, expected) != 1 {
			writeError(w, http.StatusUnauthorized, "invalid or missing API key", nil)
			return
		}

		next.ServeHTTP(w, r)
	})
}