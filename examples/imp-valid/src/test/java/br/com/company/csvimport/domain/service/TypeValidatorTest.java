package br.com.company.csvimport.domain.service;

import br.com.company.csvimport.domain.model.Cell;
import br.com.company.csvimport.domain.model.CsvColumnSchema;
import br.com.company.csvimport.domain.model.CsvHeaderSchema;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ValidationIssue;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TypeValidatorTest {

    private final TypeValidator validator = new TypeValidator();

    @Test
    void givenNumericColumn_whenValueNonNumeric_thenErrorWithLineAndColumn() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.number("id", true)
        ));
        CsvRow row = new CsvRow(7, List.of(new Cell("id", "abc", 7)));

        List<ValidationIssue> issues = validator.validate(row, schema);

        ValidationIssue issue = issues.stream()
                .filter(i -> "id".equals(i.columnName()))
                .findFirst()
                .orElseThrow();

        assertEquals(ValidationIssue.Type.TYPE, issue.type());
        assertEquals(7, issue.lineNumber());
        assertTrue(issue.message().contains("coluna 'id'"));
    }

    @Test
    void givenDateColumn_whenInvalidDate_thenReportsActionableErrorWithFormat() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.date("dt", false, "yyyy-MM-dd")
        ));
        CsvRow row = new CsvRow(3, List.of(new Cell("dt", "31/01/2024", 3)));

        List<ValidationIssue> issues = validator.validate(row, schema);

        ValidationIssue issue = issues.stream()
                .filter(i -> "dt".equals(i.columnName()))
                .findFirst()
                .orElseThrow();

        assertTrue(issue.message().contains("yyyy-MM-dd"));
        assertTrue(issue.suggestion().toLowerCase().contains("formato"));
        assertTrue(issue.expectedValue() != null);
    }

    @Test
    void givenEmailColumn_whenMalformedEmail_thenErrorWithLineAndColumn() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.email("email", false)
        ));
        CsvRow row = new CsvRow(9, List.of(new Cell("email", "invalido", 9)));

        List<ValidationIssue> issues = validator.validate(row, schema);

        ValidationIssue issue = issues.stream()
                .filter(i -> "email".equals(i.columnName()))
                .findFirst()
                .orElseThrow();

        assertEquals(ValidationIssue.Type.TYPE, issue.type());
        assertEquals(9, issue.lineNumber());
        assertEquals("email", issue.columnName());
    }

    @Test
    void givenBooleanColumn_whenValueNotTrueFalse01_thenTypeError() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.bool("active", false)
        ));
        CsvRow row = new CsvRow(5, List.of(new Cell("active", "talvez", 5)));

        List<ValidationIssue> issues = validator.validate(row, schema);

        ValidationIssue issue = issues.stream()
                .filter(i -> "active".equals(i.columnName()))
                .findFirst()
                .orElseThrow();

        assertEquals(ValidationIssue.Type.TYPE, issue.type());
    }

    @Test
    void givenTextColumn_whenValuePresent_thenNoTypeError() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.text("name", false)
        ));
        CsvRow row = new CsvRow(2, List.of(new Cell("name", "João", 2)));

        List<ValidationIssue> issues = validator.validate(row, schema);

        assertTrue(issues.isEmpty());
    }
}