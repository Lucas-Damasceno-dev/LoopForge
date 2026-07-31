package httpapi

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/example/log-ingestor/internal/application"
	"github.com/example/log-ingestor/internal/config"
	"github.com/example/log-ingestor/internal/domain"
	"github.com/example/log-ingestor/internal/metrics"
	"github.com/example/log-ingestor/internal/repository"
)

func newTestHandlerWithMinSeverity(t *testing.T, min domain.Severity) *Handler {
	t.Helper()

	repo := repository.NewMemoryRepository()
	classifier := application.NewKeywordClassifier([]string{"error"}, []string{"warn"})
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	svc := application.NewLogIngestionService(repo, classifier, min, logger)

	m, err := metrics.New()
	if err != nil {
		t.Fatalf("metrics.New() error = %v", err)
	}

	cfg := &config.Config{
		Auth: config.AuthConfig{APIKey: "test-secret"},
		Logs: config.LogsConfig{MaxBodyBytes: 1 << 20},
	}

	h, err := NewHandler(svc, m, cfg, logger)
	if err != nil {
		t.Fatalf("NewHandler() error = %v", err)
	}
	return h
}

func TestHandlerHealthz(t *testing.T) {
	h := newTestHandlerWithMinSeverity(t, domain.SeverityInfo)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rr := httptest.NewRecorder()

	h.Routes().ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rr.Code)
	}
}

func TestHandlerIngestSuccess(t *testing.T) {
	h := newTestHandlerWithMinSeverity(t, domain.SeverityInfo)

	body := `{"service":"payment","message":"ok","severity":"INFO","metadata":{"tx":"123"}}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-secret")
	rr := httptest.NewRecorder()

	h.Routes().ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200; body = %s", rr.Code, rr.Body.String())
	}

	var payload map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &payload); err != nil {
		t.Fatalf("json.Unmarshal() error = %v", err)
	}
	if payload["ingested"] != true {
		t.Errorf("ingested = %v, want true", payload["ingested"])
	}
}

func TestHandlerIngestUnauthorized(t *testing.T) {
	h := newTestHandlerWithMinSeverity(t, domain.SeverityInfo)

	body := `{"service":"payment","message":"ok","severity":"INFO"}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()

	h.Routes().ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", rr.Code)
	}
}

func TestHandlerIngestInvalidJSON(t *testing.T) {
	h := newTestHandlerWithMinSeverity(t, domain.SeverityInfo)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(`{invalid`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-secret")
	rr := httptest.NewRecorder()

	h.Routes().ServeHTTP(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400; body = %s", rr.Code, rr.Body.String())
	}
}

func TestHandlerIngestFiltered(t *testing.T) {
	h := newTestHandlerWithMinSeverity(t, domain.SeverityError)

	body := `{"service":"payment","message":"info message","severity":"INFO"}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-secret")
	rr := httptest.NewRecorder()

	h.Routes().ServeHTTP(rr, req)

	if rr.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202; body = %s", rr.Code, rr.Body.String())
	}

	var payload map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &payload); err != nil {
		t.Fatalf("json.Unmarshal() error = %v", err)
	}
	if payload["ingested"] != false {
		t.Errorf("ingested = %v, want false", payload["ingested"])
	}
}