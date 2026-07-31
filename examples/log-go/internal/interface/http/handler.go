// Package httpapi fornece handlers HTTP para o microserviço de logs.
package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/example/log-ingestor/internal/domain"
)

// LogIngestor define o caso de uso de ingestão exigido pelo handler.
type LogIngestor interface {
	// Ingest processa um log recebido e retorna se ele foi aceito para armazenamento.
	Ingest(ctx context.Context, raw domain.IncomingLog) (domain.LogEntry, bool, error)
}

// MetricsRecorder define as métricas exigidas pelos handlers HTTP.
type MetricsRecorder interface {
	// ObserveReceived registra uma requisição de ingestão recebida.
	ObserveReceived()

	// ObserveValidationError registra um erro de validação.
	ObserveValidationError()

	// ObserveAccepted registra um log aceito.
	ObserveAccepted(severity domain.Severity)

	// ObserveFiltered registra um log filtrado.
	ObserveFiltered(severity domain.Severity)

	// ObserveHTTPRequest registra a duração de uma requisição HTTP.
	ObserveHTTPRequest(method, path, status string, duration float64)
}

// Handler contém as dependências dos handlers HTTP.
type Handler struct {
	ingestor     LogIngestor
	metrics      MetricsRecorder
	maxBodyBytes int64
}

// NewHandler cria um Handler validando as dependências.
func NewHandler(ingestor LogIngestor, metrics MetricsRecorder, maxBodyBytes int64) (*Handler, error) {
	if ingestor == nil {
		return nil, errors.New("ingestor is nil")
	}
	if metrics == nil {
		return nil, errors.New("metrics is nil")
	}
	if maxBodyBytes <= 0 {
		return nil, errors.New("maxBodyBytes must be positive")
	}

	return &Handler{
		ingestor:     ingestor,
		metrics:      metrics,
		maxBodyBytes: maxBodyBytes,
	}, nil
}

// Routes monta o roteador HTTP com autenticação por API key.
func (h *Handler) Routes(metricsHandler http.Handler, apiKey string) http.Handler {
	mux := http.NewServeMux()

	mux.Handle("POST /api/v1/logs", RequireAPIKey(apiKey, http.HandlerFunc(h.handleIngest)))
	mux.HandleFunc("GET /health", h.handleHealth)
	mux.Handle("GET /metrics", metricsHandler)

	return mux
}

func (h *Handler) handleIngest(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

	h.metrics.ObserveReceived()
	defer func() {
		h.metrics.ObserveHTTPRequest(r.Method, r.URL.Path, fmt.Sprintf("%d", rec.status), time.Since(start).Seconds())
	}()

	r.Body = http.MaxBytesReader(rec, r.Body, h.maxBodyBytes)

	var raw domain.IncomingLog
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			h.metrics.ObserveValidationError()
			writeError(rec, http.StatusRequestEntityTooLarge, "request body too large", err)
			return
		}

		h.metrics.ObserveValidationError()
		writeError(rec, http.StatusBadRequest, "invalid JSON payload", err)
		return
	}

	entry, accepted, err := h.ingestor.Ingest(r.Context(), raw)
	if err != nil {
		if isClientError(err) {
			h.metrics.ObserveValidationError()
			writeError(rec, http.StatusBadRequest, "invalid log entry", err)
			return
		}

		writeError(rec, http.StatusInternalServerError, "internal server error", err)
		return
	}

	if accepted {
		writeJSON(rec, http.StatusCreated, map[string]interface{}{
			"status":    "accepted",
			"severity":  entry.Severity.String(),
			"timestamp": entry.Timestamp.Format(time.RFC3339),
		})
		return
	}

	writeJSON(rec, http.StatusAccepted, map[string]interface{}{
		"status":   "filtered",
		"severity": entry.Severity.String(),
	})
}

func (h *Handler) handleHealth(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

	defer func() {
		h.metrics.ObserveHTTPRequest(r.Method, r.URL.Path, fmt.Sprintf("%d", rec.status), time.Since(start).Seconds())
	}()

	writeJSON(rec, http.StatusOK, map[string]string{"status": "ok"})
}

func isClientError(err error) bool {
	return errors.Is(err, domain.ErrEmptyService) ||
		errors.Is(err, domain.ErrEmptyMessage) ||
		errors.Is(err, domain.ErrInvalidTimestamp) ||
		errors.Is(err, domain.ErrInvalidSeverity)
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (sr *statusRecorder) WriteHeader(code int) {
	sr.status = code
	sr.ResponseWriter.WriteHeader(code)
}

func (sr *statusRecorder) Write(data []byte) (int, error) {
	if sr.status == 0 {
		sr.status = http.StatusOK
	}
	return sr.ResponseWriter.Write(data)
}