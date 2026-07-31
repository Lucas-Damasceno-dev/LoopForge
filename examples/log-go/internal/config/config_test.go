package config

import (
	"strings"
	"testing"
)

func TestLoad(t *testing.T) {
	t.Setenv("PORT", "9090")
	t.Setenv("API_KEY", "secret")
	t.Setenv("MIN_SEVERITY", "WARN")
	t.Setenv("DATABASE_URL", "postgres://localhost/db")
	t.Setenv("ERROR_KEYWORDS", "failed, panic")
	t.Setenv("WARN_KEYWORDS", "timeout")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if cfg.Port != 9090 {
		t.Fatalf("expected port 9090, got %d", cfg.Port)
	}
	if cfg.APIKey != "secret" {
		t.Fatalf("expected api key secret, got %q", cfg.APIKey)
	}
	if cfg.MinSeverity != "WARN" {
		t.Fatalf("expected min severity WARN, got %q", cfg.MinSeverity)
	}
	if len(cfg.ErrorKeywords) != 2 {
		t.Fatalf("expected 2 error keywords, got %v", cfg.ErrorKeywords)
	}
}

func TestLoadRequiresAPIKey(t *testing.T) {
	t.Setenv("PORT", "8080")
	t.Setenv("MIN_SEVERITY", "INFO")
	t.Setenv("API_KEY", "")

	_, err := Load()
	if err == nil {
		t.Fatal("expected error when API_KEY is empty")
	}
	if !strings.Contains(err.Error(), "API_KEY") {
		t.Fatalf("expected error mentioning API_KEY, got %v", err)
	}
}