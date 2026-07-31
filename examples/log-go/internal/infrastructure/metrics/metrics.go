// Package metrics encapsula métricas Prometheus do serviço.
package metrics

import (
	"fmt"
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/example/log-ingestor/internal/domain"
)

// Metrics contém os coletores Prometheus do serviço.
type Metrics struct {
	registry         *prometheus.Registry
	received         prometheus.Counter
	accepted         *prometheus.CounterVec
	filtered         *prometheus.CounterVec
	validationErrors prometheus.Counter
	httpDuration     *prometheus.HistogramVec
}

// New cria e registra todos os coletores de métricas.
func New() (*Metrics, error) {
	m := &Metrics{
		registry: prometheus.NewRegistry(),
		received: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logs_received_total",
			Help: "Total de requisições de ingestão de logs recebidas.",
		}),
		accepted: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "logs_accepted_total",
			Help: "Total de logs aceitos para armazenamento.",
		}, []string{"severity"}),
		filtered: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "logs_filtered_total",
			Help: "Total de logs filtrados por severidade mínima.",
		}, []string{"severity"}),
		validationErrors: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logs_validation_errors_total",
			Help: "Total de logs rejeitados por validação.",
		}),
		httpDuration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Duração das requisições HTTP por rota e status.",
			Buckets: prometheus.DefBuckets,
		}, []string{"method", "path", "status"}),
	}

	if err := m.registry.Register(m.received); err != nil {
		return nil, fmt.Errorf("register logs_received_total: %w", err)
	}
	if err := m.registry.Register(m.accepted); err != nil {
		return nil, fmt.Errorf("register logs_accepted_total: %w", err)
	}
	if err := m.registry.Register(m.filtered); err != nil {
		return nil, fmt.Errorf("register logs_filtered_total: %w", err)
	}
	if err := m.registry.Register(m.validationErrors); err != nil {
		return nil, fmt.Errorf("register logs_validation_errors_total: %w", err)
	}
	if err := m.registry.Register(m.httpDuration); err != nil {
		return nil, fmt.Errorf("register http_request_duration_seconds: %w", err)
	}

	return m, nil
}

// Handler retorna o handler HTTP das métricas Prometheus.
func (m *Metrics) Handler() http.Handler {
	return promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{})
}

// ObserveReceived incrementa o total de requisições recebidas.
func (m *Metrics) ObserveReceived() {
	m.received.Inc()
}

// ObserveAccepted incrementa o total de logs aceitos por severidade.
func (m *Metrics) ObserveAccepted(severity domain.Severity) {
	m.accepted.WithLabelValues(severity.String()).Inc()
}

// ObserveFiltered incrementa o total de logs filtrados por severidade.
func (m *Metrics) ObserveFiltered(severity domain.Severity) {
	m.filtered.WithLabelValues(severity.String()).Inc()
}

// ObserveValidationError incrementa o total de erros de validação.
func (m *Metrics) ObserveValidationError() {
	m.validationErrors.Inc()
}

// ObserveHTTPRequest registra a duração de uma requisição HTTP.
func (m *Metrics) ObserveHTTPRequest(method, path, status string, durationSeconds float64) {
	m.httpDuration.WithLabelValues(method, path, status).Observe(durationSeconds)
}