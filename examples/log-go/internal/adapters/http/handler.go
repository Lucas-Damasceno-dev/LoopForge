package httpapi

import (
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"

	"github.com/example/logingestor/internal/domain"
	"github.com/example/logingestor/internal/metrics"
	"github.com/example/logingestor/internal/usecase"
)

const maxBodyBytes = 1 << 20 // 1 MiB

// Handler contém os handlers HTTP do serviço.
type Handler struct {
	ingestor *usecase.IngestLogUseCase
	metrics  *metrics.Metrics
	logger   *slog.Logger
}

// NewHandler cria um Handler com dependências validadas.
func NewHandler(ingestor *usecase.IngestLogUseCase, metricCollector *metrics.Metrics, logger *slog.Logger) (*Handler, error) {
	if ingestor == nil {
		return nil, fmt.Errorf("ingestor is nil")
	}
	if metricCollector == nil {
		return nil, fmt.Errorf("metrics is nil")
	}
	if logger == nil {
		logger = slog.Default()
	}

	return &Handler{
		ingestor: ingestor,
		metrics:  metricCollector,
		logger:   logger,
	}, nil
}

// HandleIngest processa a ingestão de um log JSON.
func (h *Handler) HandleIngest(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)

	var req domain.IngestLogRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			h.writeError(w, http.StatusRequestEntityTooLarge, "request body too large")
			return
		}
		h.writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	h.metrics.IncLogsReceived()

	result, err := h.ingestor.Ingest(r.Context(), req)
	if err != nil {
		var validationErr *domain.ValidationError
		if errors.As(err, &validationErr) {
			h.metrics.IncLogsInvalid()
			h.writeError(w, http.StatusBadRequest, validationErr.Error())
			return
		}

		h.metrics.IncLogsInvalid()
		h.logger.Error("failed to ingest log", "error", err)
		h.writeError(w, http.StatusInternalServerError, "internal server error")
		return
	}

	if result.Stored {
		h.metrics.IncLogsStored()
	} else {
		h.metrics.IncLogsFiltered()
	}

	h.writeJSON(w, http.StatusAccepted, ingestResponse{
		ID:       result.Entry.ID,
		Stored:   result.Stored,
		Severity: result.Entry.Severity.String(),
	})
}

// HandleHealth responde o health check do serviço.
func (h *Handler) HandleHealth(w http.ResponseWriter, r *http.Request) {
	h.writeJSON(w, http.StatusOK, healthResponse{Status: "ok"})
}

type ingestResponse struct {
	ID       string `json:"id"`
	Stored   bool   `json:"stored"`
	Severity string `json:"severity"`
}

type healthResponse struct {
	Status string `json:"status"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func (h *Handler) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, errorResponse{Error: message})
}

func (h *Handler) writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		h.logger.Error("failed to write JSON response", "error", err)
	}
}