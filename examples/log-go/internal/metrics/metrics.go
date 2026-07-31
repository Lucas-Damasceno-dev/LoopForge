package metrics

import (
	"fmt"
	"net/http"
	"strconv"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Metrics agrega as métricas Prometheus do serviço.
type Metrics struct {
	registry      *prometheus.Registry
	logsReceived  prometheus.Counter
	logsStored    prometheus.Counter
	logsFiltered  prometheus.Counter
	logsInvalid   prometheus.Counter
	httpRequests  *prometheus.CounterVec
}

// New cria e registra todas as métricas do serviço.
func New() (*Metrics, error) {
	m := &Metrics{
		registry: prometheus.NewRegistry(),
		logsReceived: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logs_received_total",
			Help: "Total number of log entries received.",
		}),
		logsStored: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logs_stored_total",
			Help: "Total number of log entries persisted.",
		}),
		logsFiltered: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logs_filtered_total",
			Help: "Total number of log entries filtered by minimum severity.",
		}),
		logsInvalid: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logs_invalid_total",
			Help: "Total number of invalid log entries rejected.",
		}),
		httpRequests: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests by operation and status code.",
		}, []string{"operation", "status"}),
	}

	if err := m.registry.Register(m.logsReceived); err != nil {
		return nil, fmt.Errorf("register logs_received_total: %w", err)
	}
	if err := m.registry.Register(m.logsStored); err != nil {
		return nil, fmt.Errorf("register logs_stored_total: %w", err)
	}
	if err := m.registry.Register(m.logsFiltered); err != nil {
		return nil, fmt.Errorf("register logs_filtered_total: %w", err)
	}
	if err := m.registry.Register(m.logsInvalid); err != nil {
		return nil, fmt.Errorf("register logs_invalid_total: %w", err)
	}
	if err := m.registry.Register(m.httpRequests); err != nil {
		return nil, fmt.Errorf("register http_requests_total: %w", err)
	}

	return m, nil
}

// IncLogsReceived incrementa o contador de logs recebidos.
func (m *Metrics) IncLogsReceived() {
	m.logsReceived.Inc()
}

// IncLogsStored incrementa o contador de logs persistidos.
func (m *Metrics) IncLogsStored() {
	m.logsStored.Inc()
}

// IncLogsFiltered incrementa o contador de logs filtrados.
func (m *Metrics) IncLogsFiltered() {
	m.logsFiltered.Inc()
}

// IncLogsInvalid incrementa o contador de logs inválidos.
func (m *Metrics) IncLogsInvalid() {
	m.logsInvalid.Inc()
}

// Handler expõe as métricas no formato Prometheus.
func (m *Metrics) Handler() http.Handler {
	return promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{})
}

// Measure envolve um handler HTTP e registra requisições por status.
func (m *Metrics) Measure(operation string, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next(recorder, r)
		m.httpRequests.WithLabelValues(operation, strconv.Itoa(recorder.status)).Inc()
	}
}

// statusRecorder captura o código de status HTTP da resposta.
type statusRecorder struct {
	http.ResponseWriter
	status int
}

// WriteHeader armazena o status e delega a escrita.
func (w *statusRecorder) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}