package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/example/logingestor/internal/domain"
)

// Config contém todas as configurações carregadas de variáveis de ambiente.
type Config struct {
	Port            int
	DatabaseURL     string
	MinSeverity     string
	APIKey          string
	ErrorKeywords   []string
	WarnKeywords    []string
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

// Load lê e valida as configurações do serviço.
func Load() (*Config, error) {
	port, err := getEnvInt("PORT", 8080)
	if err != nil {
		return nil, err
	}

	readTimeout, err := getEnvDurationSeconds("READ_TIMEOUT_SECONDS", 10)
	if err != nil {
		return nil, err
	}

	writeTimeout, err := getEnvDurationSeconds("WRITE_TIMEOUT_SECONDS", 10)
	if err != nil {
		return nil, err
	}

	shutdownTimeout, err := getEnvDurationSeconds("SHUTDOWN_TIMEOUT_SECONDS", 15)
	if err != nil {
		return nil, err
	}

	minSeverity := strings.ToUpper(strings.TrimSpace(os.Getenv("MIN_SEVERITY")))
	if minSeverity == "" {
		minSeverity = "INFO"
	}

	cfg := &Config{
		Port:            port,
		DatabaseURL:     strings.TrimSpace(os.Getenv("DATABASE_URL")),
		MinSeverity:     minSeverity,
		APIKey:          strings.TrimSpace(os.Getenv("API_KEY")),
		ErrorKeywords:   envList("ERROR_KEYWORDS"),
		WarnKeywords:    envList("WARN_KEYWORDS"),
		ReadTimeout:     readTimeout,
		WriteTimeout:    writeTimeout,
		ShutdownTimeout: shutdownTimeout,
	}

	if cfg.APIKey == "" {
		return nil, fmt.Errorf("API_KEY environment variable is required")
	}
	if cfg.Port <= 0 || cfg.Port > 65535 {
		return nil, fmt.Errorf("PORT must be between 1 and 65535")
	}
	if _, err := domain.ParseSeverity(cfg.MinSeverity); err != nil {
		return nil, fmt.Errorf("invalid MIN_SEVERITY: %w", err)
	}

	return cfg, nil
}

// envList converte uma variável separada por vírgulas em uma lista de strings.
func envList(key string) []string {
	raw := os.Getenv(key)
	if strings.TrimSpace(raw) == "" {
		return nil
	}

	parts := strings.Split(raw, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if value := strings.TrimSpace(part); value != "" {
			result = append(result, value)
		}
	}
	return result
}

// getEnvInt retorna um inteiro de ambiente ou o default quando ausente.
func getEnvInt(key string, def int) (int, error) {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return def, nil
	}

	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer: %w", key, err)
	}
	return value, nil
}

// getEnvDurationSeconds retorna uma duração em segundos de variável de ambiente.
func getEnvDurationSeconds(key string, def int) (time.Duration, error) {
	seconds, err := getEnvInt(key, def)
	if err != nil {
		return 0, err
	}
	return time.Duration(seconds) * time.Second, nil
}