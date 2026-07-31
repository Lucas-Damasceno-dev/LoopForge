package httpapi

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/example/log-ingestor/internal/application"
	"github.com/example/log-ingestor/internal/config"
	"github.com/example/log-ingestor/internal/domain"
	"github.com/example/log-ingestor/internal/metrics"
)

// Handler encapsula os handlers HTTP do serviço.
type Handler struct {
	service      *application.LogIngestionService
	metrics      *metrics.Metrics
	apiKey       string
	logger       *slog.Logger
	maxBodyBytes int64
}

// NewHandler cria um Handler validando as dependências obrigatórias.
func NewHandler(
	service *application.LogIngestionService,
	m *metrics.Metrics,
	cfg *config.Config,
	logger *slog.Logger,
) (*Handler, error) {
	if service == nil {
		return nil, errors.New("service is required")
	}
	if m == nil {
		return nil, errors.New("metrics is required")
	}
	if cfg == nil {
		return nil, errors.New("config is required")
	}

	apiKey := strings.TrimSpace(cfg.Auth.APIKey)
	if apiKey == "" {
		return nil, errors.New("api key is required")
	}

	if logger == nil {
		logger = slog.Default()
	}

	maxBodyBytes := cfg.Logs.MaxBodyBytes
	if maxBodyBytes <= 0 {
		maxBodyBytes = 1 << 20
	}

	return &Handler{
		service:      service,
		metrics:      m,
		apiKey:       apiKey,
		logger:       logger,
		maxBodyBytes: maxBodyBytes,
	}, nil
}

// Routes constrói o mux com todas as rotas do serviço.
func (h *Handler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", h.healthz)
	mux.Handle("/api/v1/logs", h.authMiddleware(http.HandlerFunc(h.ingest)))
	mux.Handle("/metrics", h.metrics.Handler())
	return mux
}

func (h *Handler) healthz(w http.ResponseWriter, _ *http.Request) {
	h.writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

func (h *Handler) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := r.Header.Get("X-API-Key")
		if key == "" || subtle.ConstantTimeCompare([]byte(key), []byte(h.apiKey)) != 1 {
			h.logger.Warn("unauthorized request",
				"method", r.Method,
				"path", r.URL.Path,
				"remote", r.RemoteAddr,
			)
			h.writeError(w, http.StatusUnauthorized, "unauthorized")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (h *Handler) ingest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	if contentType := r.Header.Get("Content-Type"); contentType != "" {
		if !strings.HasPrefix(strings.ToLower(contentType), "application/json") {
			h.writeError(w, http.StatusUnsupportedMediaType, "content-type must be application/json")
			return
		}
	}

	r.Body = http.MaxBytesReader(w, r.Body, h.maxBodyBytes)
	decoder := json.NewDecoder(r.Body)

	var req domain.IngestRequest
	if err := decoder.Decode(&req); err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			h.writeError(w, http.StatusRequestEntityTooLarge, "request body too large")
		} else {
			h.writeError(w, http.StatusBadRequest, "invalid JSON body")
		}
		h.metrics.LogsErrorsTotal.Inc()
		return
	}

	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		h.writeError(w, http.StatusBadRequest, "request body must contain a single JSON object")
		h.metrics.LogsErrorsTotal.Inc()
		return
	}

	start := time.Now()
	result, err := h.service.Ingest(r.Context(), req)
	if err != nil {
		h.metrics.LogsErrorsTotal.Inc()
		switch {
		case errors.Is(err, domain.ErrServiceRequired),
			errors.Is(err, domain.ErrMessageRequired),
			errors.Is(err, domain.ErrTimestampInvalid),
			errors.Is(err, domain.ErrSeverityInvalid):
			h.writeError(w, http.StatusUnprocessableEntity, err.Error())
		default:
			h.logger.Error("failed to ingest log", "error", err)
			h.writeError(w, http.StatusInternalServerError, "internal server error")
		}
		return
	}

	h.metrics.IngestDuration.Observe(time.Since(start).Seconds())

	if result.Persisted {
		h.metrics.LogsIngestedTotal.Inc()
		h.writeJSON(w, http.StatusOK, map[string]any{
			"id":       result.Entry.ID,
			"ingested": true,
			"severity": result.Entry.Severity,
		})
		return
	}

	h.metrics.LogsFilteredTotal.Inc()
	h.writeJSON(w, http.StatusAccepted, map[string]any{
		"id":       result.Entry.ID,
		"ingested": false,
		"reason":   result.Reason,
		"severity": result.Entry.Severity,
	})
}

func (h *Handler) writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		h.logger.Error("failed to write JSON response", "error", err)
	}
}

func (h *Handler) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, map[string]any{"error": message})
}