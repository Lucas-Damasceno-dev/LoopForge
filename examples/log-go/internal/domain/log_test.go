package domain

import "testing"

func TestParseSeverity(t *testing.T) {
	tests := []struct {
		input string
		want  Severity
	}{
		{"INFO", SeverityInfo},
		{"info", SeverityInfo},
		{"WARN", SeverityWarn},
		{"ERROR", SeverityError},
	}

	for _, tt := range tests {
		got, err := ParseSeverity(tt.input)
		if err != nil {
			t.Fatalf("ParseSeverity(%q) error = %v", tt.input, err)
		}
		if got != tt.want {
			t.Errorf("ParseSeverity(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
}

func TestParseSeverityInvalid(t *testing.T) {
	if _, err := ParseSeverity("DEBUG"); err == nil {
		t.Fatal("ParseSeverity(DEBUG) expected error")
	}
}

func TestSeverityRank(t *testing.T) {
	if SeverityError.Rank() <= SeverityWarn.Rank() {
		t.Error("expected ERROR rank > WARN rank")
	}
	if SeverityWarn.Rank() <= SeverityInfo.Rank() {
		t.Error("expected WARN rank > INFO rank")
	}
}

func TestSeverityAllows(t *testing.T) {
	if !SeverityInfo.Allows(SeverityError) {
		t.Error("INFO should allow ERROR")
	}
	if SeverityError.Allows(SeverityInfo) {
		t.Error("ERROR should not allow INFO")
	}
}