package domain_test

import (
	"testing"

	"github.com/example/logingestor/internal/domain"
)

func TestParseSeverity(t *testing.T) {
	tests := []struct {
		input    string
		expected domain.Severity
		wantErr  bool
	}{
		{input: "INFO", expected: domain.SeverityInfo},
		{input: "info", expected: domain.SeverityInfo},
		{input: "WARN", expected: domain.SeverityWarn},
		{input: "WARNING", expected: domain.SeverityWarn},
		{input: "ERROR", expected: domain.SeverityError},
		{input: "FATAL", expected: domain.SeverityError},
		{input: "DEBUG", wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got, err := domain.ParseSeverity(tt.input)
			if tt.wantErr {
				if err == nil {
					t.Fatalf("expected error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tt.expected {
				t.Fatalf("expected %v, got %v", tt.expected, got)
			}
		})
	}
}

func TestSeverityMeetsMinimum(t *testing.T) {
	if !domain.SeverityError.MeetsMinimum(domain.SeverityInfo) {
		t.Fatal("ERROR should meet minimum INFO")
	}
	if domain.SeverityInfo.MeetsMinimum(domain.SeverityError) {
		t.Fatal("INFO should NOT meet minimum ERROR")
	}
}