package httpapi_test

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/example/logingestor/internal/adapters/http"
	"github.com/example/logingestor/internal/domain"
	"github.com/example/logingestor/internal/metrics"
	"github.com/example/logingestor/internal/repository/memory"
	"github.com/example/logingestor/internal/usecase"
)

var fixedTime = time.Date(2025, 3, 26, 12, 0, 0, 0, time.UTC)

func newTestServer(t *testing.T, minSeverity domain.Severity, classifier *usecase.ConfigurableClassifier) (http.Handler, *memory.Repository) {
	t.Helper()

	repo := memory.New()
	if classifier == nil {
		classifier = usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
			DefaultSeverity: domain.SeverityInfo,
		})
	}

	useCase := usecase.NewIngestLogUseCase(repo, classifier, minSeverity,
		usecase.WithClock(func() time.Time { return fixedTime }),
	)

	metricCollector, err := metrics.New()
	if err != nil {
		t.Fatalf("metrics.New() error = %v", err)
	}

	handler, err := http.NewHandler(useCase, metricCollector, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatalf("http.NewHandler() error = %v", err)
	}

	router := http.NewRouter(handler, metricCollector, "test-api-key")
	return router, repo
}

func TestHandleIngest_ValidLog(t *testing.T) {
	router, repo := newTestServer(t, domain.SeverityInfo, nil)

	body := `{"service":"orders","message":"request completed","severity":"INFO","metadata":{"trace_id":"abc"}}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-api-key")

	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusAccepted {
		t.Fatalf("expected HTTP 202, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		ID       string `json:"id"`
		Stored   bool   `json:"stored"`
		Severity string `json:"severity"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if !resp.Stored {
		t.Fatal("expected stored=true")
	}
	if resp.Severity != "INFO" {
		t.Fatalf("expected severity INFO, got %q", resp.Severity)
	}
	if repo.Count() != 1 {
		t.Fatalf("expected 1 stored log, got %d", repo.Count())
	}
}

func TestHandleIngest_FilteredLog(t *testing.T) {
	router, repo := newTestServer(t, domain.SeverityError, nil)

	body := `{"service":"orders","message":"something is slow","severity":"WARN"}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-api-key")

	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusAccepted {
		t.Fatalf("expected HTTP 202, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		Stored bool `json:"stored"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if resp.Stored {
		t.Fatal("expected stored=false for WARN when minimum is ERROR")
	}
	if repo.Count() != 0 {
		t.Fatalf("expected 0 stored logs, got %d", repo.Count())
	}
}

func TestHandleIngest_Unauthorized(t *testing.T) {
	router, _ := newTestServer(t, domain.SeverityInfo, nil)

	body := `{"service":"orders","message":"hello"}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("expected HTTP 401, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestHandleIngest_InvalidBody(t *testing.T) {
	router, _ := newTestServer(t, domain.SeverityInfo, nil)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(`not-json`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-api-key")

	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected HTTP 400, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestHandleIngest_ValidationError(t *testing.T) {
	router, _ := newTestServer(t, domain.SeverityInfo, nil)

	body := `{"message":"hello"}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/logs", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "test-api-key")

	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected HTTP 400, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp map[string]string
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if !strings.Contains(resp["error"], "service") {
		t.Fatalf("expected error to mention service, got %q", resp["error"])
	}
}