package br.com.company.csvimport.domain.model;

import java.util.List;
import java.util.Objects;

/**
 * Representa um problema encontrado durante a validação do CSV.
 */
public final class ValidationIssue {

    public enum Severity {
        CRITICAL,
        WARNING,
        INFO
    }

    public enum Type {
        STRUCTURE,
        TYPE,
        DUPLICATE_EXACT,
        DUPLICATE_PARTIAL,
        REFERENCE,
        REQUIRED_FIELD_MISSING,
        EMPTY_FILE,
        INVALID_ENCODING,
        MALFORMED_CSV
    }

    private final Severity severity;
    private final Type type;
    private final String message;
    private final int lineNumber;
    private final String columnName;
    private final List<Integer> relatedLines;
    private final String expectedValue;
    private final String suggestion;

    private ValidationIssue(Builder builder) {
        this.severity = Objects.requireNonNull(builder.severity, "severity");
        this.type = Objects.requireNonNull(builder.type, "type");
        this.message = Objects.requireNonNull(builder.message, "message");
        this.lineNumber = builder.lineNumber;
        this.columnName = builder.columnName;
        this.relatedLines = builder.relatedLines == null ? List.of() : List.copyOf(builder.relatedLines);
        this.expectedValue = builder.expectedValue;
        this.suggestion = builder.suggestion;
    }

    public static Builder builder() {
        return new Builder();
    }

    public Severity severity() {
        return severity;
    }

    public Type type() {
        return type;
    }

    public String message() {
        return message;
    }

    public int lineNumber() {
        return lineNumber;
    }

    public String columnName() {
        return columnName;
    }

    public List<Integer> relatedLines() {
        return relatedLines;
    }

    public String expectedValue() {
        return expectedValue;
    }

    public String suggestion() {
        return suggestion;
    }

    public static final class Builder {
        private Severity severity;
        private Type type;
        private String message;
        private int lineNumber = -1;
        private String columnName;
        private List<Integer> relatedLines;
        private String expectedValue;
        private String suggestion;

        public Builder severity(Severity severity) {
            this.severity = severity;
            return this;
        }

        public Builder type(Type type) {
            this.type = type;
            return this;
        }

        public Builder message(String message) {
            this.message = message;
            return this;
        }

        public Builder lineNumber(int lineNumber) {
            this.lineNumber = lineNumber;
            return this;
        }

        public Builder columnName(String columnName) {
            this.columnName = columnName;
            return this;
        }

        public Builder relatedLines(List<Integer> relatedLines) {
            this.relatedLines = relatedLines;
            return this;
        }

        public Builder expectedValue(String expectedValue) {
            this.expectedValue = expectedValue;
            return this;
        }

        public Builder suggestion(String suggestion) {
            this.suggestion = suggestion;
            return this;
        }

        public ValidationIssue build() {
            return new ValidationIssue(this);
        }
    }
}