package httpapi_test

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/example/log-ingestor/internal/domain"
	httpapi "github.com/example/log-ingestor/internal/interface/http"
	"github.com/example/log-ingestor/internal/infrastructure/metrics"
	"github.com/example/log-ingestor/internal/infrastructure/persistence"
	"github.com/example/log-ingestor/internal/usecase"
)

const testAPIKey = "test-key"

type testApp struct {
	handler http.Handler
	metrics *metrics.Metrics
	repo    *persistence.MemoryRepository
}

func newTestApp(t *testing.T, minLevel domain.Severity, rules map[string]domain.Severity) *testApp {
	t.Helper()

	repo := persistence.NewMemoryRepository()
	m, err := metrics.New()
	if err != nil {
		t.Fatalf("metrics.New() error = %v", err)
	}

	processor, err := usecase.NewProcessor(repo, m, minLevel, rules)
	if err != nil {
		t.Fatalf("usecase.NewProcessor() error = %v", err)
	}

	handler, err := httpapi.NewHandler(processor, m, 1<<20)
	if err != nil {
		t.Fatalf("httpapi.NewHandler() error = %v", err)
	}

	return &testApp{
		handler: handler.Routes(m.Handler(), testAPIKey),
		metrics: m,
		repo:    repo,
	}
}

func (app *testApp) doRequest(t *testing.T, method, path, body, apiKey string) *httptest.ResponseRecorder {
	t.Helper()

	var reader io.Reader
	if body != "" {
		reader = strings.NewReader(body)
	}

	req := httptest.NewRequest(method, path, reader)
	req.Header.Set("Content-Type", "application/json")
	if apiKey != "" {
		req.Header.Set("X-API-Key", apiKey)
	}

	rr := httptest.NewRecorder()
	app.handler.ServeHTTP(rr, req)
	return rr
}

func decodeBody(t *testing.T, rr *httptest.ResponseRecorder) map[string]interface{} {
	t.Helper()

	var body map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatalf("json.Unmarshal() error = %v, body = %q", err, rr.Body.String())
	}
	return body
}

func TestHandler_IngestValidLog(t *testing.T) {
	app := newTestApp(t, domain.SeverityInfo, nil)

	payload := `{
		"timestamp":"2025-03-26T10:00:00Z",
		"service":"auth",
		"level":"INFO",
		"message":"user logged in"
	}`

	rr := app.doRequest(t, http.MethodPost, "/api/v1/logs", payload, testAPIKey)
	if rr.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d, body = %s", rr.Code, http.StatusCreated, rr.Body.String())
	}

	body := decodeBody(t, rr)
	if body["status"] != "accepted" {
		t.Fatalf("status body = %v, want accepted", body["status"])
	}
}

func TestHandler_IngestFiltered(t *testing.T) {
	app := newTestApp(t, domain.SeverityError, nil)

	payload := `{
		"timestamp":"2025-03-26T10:00:00Z",
		"service":"auth",
		"level":"INFO",
		"message":"user logged in"
	}`

	rr := app.doRequest(t, http.MethodPost, "/api/v1/logs", payload, testAPIKey)
	if rr.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want %d, body = %s", rr.Code, http.StatusAccepted, rr.Body.String())
	}

	body := decodeBody(t, rr)
	if body["status"] != "filtered" {
		t.Fatalf("status body = %v, want filtered", body["status"])
	}
}

func TestHandler_IngestInvalidJSON(t *testing.T) {
	app := newTestApp(t, domain.SeverityInfo, nil)

	rr := app.doRequest(t, http.MethodPost, "/api/v1/logs", `{"bad`, testAPIKey)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusBadRequest)
	}
}

func TestHandler_IngestMissingService(t *testing.T) {
	app := newTestApp(t, domain.SeverityInfo, nil)

	payload := `{
		"timestamp":"2025-03-26T10:00:00Z",
		"message":"user logged in"
	}`

	rr := app.doRequest(t, http.MethodPost, "/api/v1/logs", payload, testAPIKey)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusBadRequest)
	}
}

func TestHandler_RequiresAPIKey(t *testing.T) {
	app := newTestApp(t, domain.SeverityInfo, nil)

	payload := `{
		"timestamp":"2025-03-26T10:00:00Z",
		"service":"auth",
		"message":"user logged in"
	}`

	rr := app.doRequest(t, http.MethodPost, "/api/v1/logs", payload, "")
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusUnauthorized)
	}

	rr = app.doRequest(t, http.MethodPost, "/api/v1/logs", payload, "wrong-key")
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusUnauthorized)
	}
}

func TestHandler_Health(t *testing.T) {
	app := newTestApp(t, domain.SeverityInfo, nil)

	rr := app.doRequest(t, http.MethodGet, "/health", "", "")
	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusOK)
	}
}

func TestHandler_IngestInfersSeverity(t *testing.T) {
	rules := map[string]domain.Severity{"failed": domain.SeverityError}
	app := newTestApp(t, domain.SeverityInfo, rules)

	payload := `{
		"timestamp":"2025-03-26T10:00:00Z",
		"service":"auth",
		"message":"authentication failed"
	}`

	rr := app.doRequest(t, http.MethodPost, "/api/v1/logs", payload, testAPIKey)
	if rr.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d, body = %s", rr.Code, http.StatusCreated, rr.Body.String())
	}

	body := decodeBody(t, rr)
	if body["severity"] != "ERROR" {
		t.Fatalf("severity = %v, want ERROR", body["severity"])
	}
}