package br.com.company.csvimport.domain.service;

import br.com.company.csvimport.domain.model.Cell;
import br.com.company.csvimport.domain.model.CsvColumnSchema;
import br.com.company.csvimport.domain.model.CsvHeaderSchema;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ValidationIssue;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Valida os tipos de dados de cada coluna conforme o schema.
 */
public class TypeValidator {

    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");
    private static final Set<String> BOOLEAN_VALUES =
            Set.of("true", "false", "0", "1");

    /**
     * Valida uma linha contra o schema.
     *
     * @param row    linha do CSV
     * @param schema schema de colunas
     * @return lista de problemas encontrados
     */
    public List<ValidationIssue> validate(CsvRow row, CsvHeaderSchema schema) {
        List<ValidationIssue> issues = new ArrayList<>();
        for (CsvColumnSchema column : schema.columns()) {
            validateColumn(row, column).ifPresent(issues::add);
        }
        return issues;
    }

    private Optional<ValidationIssue> validateColumn(CsvRow row, CsvColumnSchema column) {
        String value = row.value(column.name());
        if (value == null || value.isBlank()) {
            if (column.required()) {
                return Optional.of(ValidationIssue.builder()
                        .severity(ValidationIssue.Severity.CRITICAL)
                        .type(ValidationIssue.Type.REQUIRED_FIELD_MISSING)
                        .lineNumber(row.lineNumber())
                        .columnName(column.name())
                        .message(String.format(
                                "Linha %d, coluna '%s': campo obrigatório ausente.",
                                row.lineNumber(), column.name()))
                        .suggestion(String.format(
                                "Preencha o campo obrigatório '%s'.", column.name()))
                        .expectedValue("valor obrigatório")
                        .build());
            }
            return Optional.empty();
        }

        return switch (column.type()) {
            case TEXT -> Optional.empty();
            case NUMBER -> validateNumber(row, column, value.trim());
            case DATE -> validateDate(row, column, value.trim());
            case EMAIL -> validateEmail(row, column, value.trim());
            case BOOLEAN -> validateBoolean(row, column, value.trim());
        };
    }

    private Optional<ValidationIssue> validateNumber(CsvRow row, CsvColumnSchema column, String value) {
        try {
            new BigDecimal(value);
            return Optional.empty();
        } catch (NumberFormatException ex) {
            return Optional.of(typeIssue(row, column, value, "número válido",
                    "Use apenas dígitos e separador decimal (ex.: 1234.56)"));
        }
    }

    private Optional<ValidationIssue> validateDate(CsvRow row, CsvColumnSchema column, String value) {
        String format = column.dateFormat() != null ? column.dateFormat() : "yyyy-MM-dd";
        try {
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern(format, Locale.ROOT);
            LocalDate.parse(value, formatter);
            return Optional.empty();
        } catch (DateTimeParseException ex) {
            return Optional.of(typeIssue(row, column, value,
                    "data no formato " + format,
                    "Use o formato " + format + " (ex.: " + column.example() + ")"));
        }
    }

    private Optional<ValidationIssue> validateEmail(CsvRow row, CsvColumnSchema column, String value) {
        if (EMAIL_PATTERN.matcher(value).matches()) {
            return Optional.empty();
        }
        return Optional.of(typeIssue(row, column, value, "e-mail válido",
                "Use o formato usuario@dominio.com"));
    }

    private Optional<ValidationIssue> validateBoolean(CsvRow row, CsvColumnSchema column, String value) {
        if (BOOLEAN_VALUES.contains(value.toLowerCase(Locale.ROOT))) {
            return Optional.empty();
        }
        return Optional.of(typeIssue(row, column, value, "booleano (true/false/0/1)",
                "Use apenas os valores true, false, 0 ou 1"));
    }

    private ValidationIssue typeIssue(CsvRow row, CsvColumnSchema column, String value, String expected, String suggestion) {
        return ValidationIssue.builder()
                .severity(ValidationIssue.Severity.CRITICAL)
                .type(ValidationIssue.Type.TYPE)
                .lineNumber(row.lineNumber())
                .columnName(column.name())
                .message(String.format(
                        "Linha %d, coluna '%s': valor '%s' não é %s.",
                        row.lineNumber(), column.name(), value, expected))
                .expectedValue(column.example())
                .suggestion(suggestion)
                .build();
    }
}