package httpapi

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/example/logingestor/internal/metrics"
)

// NewRouter monta as rotas HTTP do serviço.
func NewRouter(h *Handler, m *metrics.Metrics, apiKey string) http.Handler {
	mux := http.NewServeMux()

	ingestHandler := m.Measure("ingest", h.HandleIngest)
	mux.Handle("POST /api/v1/logs", withAPIKeyAuth(ingestHandler, apiKey))
	mux.HandleFunc("GET /healthz", h.HandleHealth)
	mux.Handle("GET /metrics", m.Handler())

	return mux
}

// withAPIKeyAuth aplica autenticação por API Key via header X-API-Key.
func withAPIKeyAuth(next http.Handler, apiKey string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if apiKey == "" {
			next.ServeHTTP(w, r)
			return
		}

		provided := strings.TrimSpace(r.Header.Get("X-API-Key"))
		if provided != apiKey {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "unauthorized"})
			return
		}

		next.ServeHTTP(w, r)
	})
}