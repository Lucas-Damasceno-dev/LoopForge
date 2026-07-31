package metrics_test

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/example/logingestor/internal/metrics"
)

func TestMetrics_New(t *testing.T) {
	m, err := metrics.New()
	if err != nil {
		t.Fatalf("metrics.New() error = %v", err)
	}
	if m == nil {
		t.Fatal("expected non-nil metrics")
	}
}

func TestMetrics_Measure(t *testing.T) {
	m, err := metrics.New()
	if err != nil {
		t.Fatalf("metrics.New() error = %v", err)
	}

	handler := m.Measure("test", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected HTTP 200, got %d", rr.Code)
	}
}