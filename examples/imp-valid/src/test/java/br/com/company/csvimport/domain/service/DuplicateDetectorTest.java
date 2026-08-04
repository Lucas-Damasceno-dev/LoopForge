package br.com.company.csvimport.domain.service;

import br.com.company.csvimport.domain.model.BusinessKeyRule;
import br.com.company.csvimport.domain.model.Cell;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ValidationIssue;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

class DuplicateDetectorTest {

    private final DuplicateDetector detector = new DuplicateDetector();

    @Test
    void givenTwoExactIdenticalRows_thenIdentifiesBothOccurrences() {
        List<CsvRow> rows = List.of(
                row(2, List.of("id", "name"), "1", "João"),
                row(3, List.of("id", "name"), "1", "João")
        );

        List<ValidationIssue> issues = detector.detectExactDuplicates(rows);

        ValidationIssue issue = issues.stream()
                .filter(i -> i.type() == ValidationIssue.Type.DUPLICATE_EXACT)
                .findFirst()
                .orElseThrow();

        assertTrue(issue.relatedLines().containsAll(List.of(2, 3)));
        assertTrue(issue.message().contains("2"));
        assertTrue(issue.message().contains("3"));
    }

    @Test
    void givenNoExactDuplicateRows_thenNoExactDuplicateWarning() {
        List<CsvRow> rows = List.of(
                row(2, List.of("id", "name"), "1", "João"),
                row(3, List.of("id", "name"), "2", "Maria")
        );

        List<ValidationIssue> issues = detector.detectExactDuplicates(rows);

        assertTrue(issues.isEmpty());
    }

    @Test
    void givenDuplicateRowsAndTypeErrors_thenDuplicateAndTypeIssuesAreSeparable() {
        List<CsvRow> rows = List.of(
                row(2, List.of("id", "name"), "abc", "João"),
                row(3, List.of("id", "name"), "abc", "João")
        );

        List<ValidationIssue> issues = new ArrayList<>();
        issues.addAll(detector.detectExactDuplicates(rows));

        ValidationIssue duplicate = issues.stream()
                .filter(i -> i.type() == ValidationIssue.Type.DUPLICATE_EXACT)
                .findFirst()
                .orElseThrow();

        ValidationIssue type = ValidationIssue.builder()
                .severity(ValidationIssue.Severity.CRITICAL)
                .type(ValidationIssue.Type.TYPE)
                .lineNumber(2)
                .columnName("id")
                .message("Linha 2, coluna 'id': valor 'abc' não é número válido.")
                .build();

        assertTrue(duplicate.relatedLines().containsAll(List.of(2, 3)));
        assertTrue(type.type() == ValidationIssue.Type.TYPE);
    }

    @Test
    void givenBusinessKeyConfigured_whenTwoRecordsHaveSameKey_thenPartialDuplicateWarning() {
        List<CsvRow> rows = List.of(
                row(2, List.of("id", "name"), "1", "João"),
                row(3, List.of("id", "name"), "2", "João")
        );

        List<ValidationIssue> issues = detector.detectPartialDuplicates(
                rows,
                new BusinessKeyRule(List.of("name"))
        );

        ValidationIssue issue = issues.stream()
                .filter(i -> i.type() == ValidationIssue.Type.DUPLICATE_PARTIAL)
                .findFirst()
                .orElseThrow();

        assertTrue(issue.relatedLines().containsAll(List.of(2, 3)));
        assertTrue(issue.message().contains("name"));
    }

    @Test
    void givenFileWithoutPartialDuplicates_thenNoPartialDuplicateWarning() {
        List<CsvRow> rows = List.of(
                row(2, List.of("id", "name"), "1", "João"),
                row(3, List.of("id", "name"), "2", "Maria")
        );

        List<ValidationIssue> issues = detector.detectPartialDuplicates(
                rows,
                new BusinessKeyRule(List.of("name"))
        );

        assertTrue(issues.isEmpty());
    }

    @Test
    void givenRecordWithEmptyBusinessKey_thenNotConsideredDuplicate() {
        List<CsvRow> rows = List.of(
                row(2, List.of("id", "name"), "1", ""),
                row(3, List.of("id", "name"), "2", "")
        );

        List<ValidationIssue> issues = detector.detectPartialDuplicates(
                rows,
                new BusinessKeyRule(List.of("name"))
        );

        assertTrue(issues.isEmpty());
    }

    private CsvRow row(int line, List<String> headers, String... values) {
        List<Cell> cells = new ArrayList<>();
        for (int i = 0; i < headers.size(); i++) {
            String value = i < values.length ? values[i] : "";
            cells.add(new Cell(headers.get(i), value, line));
        }
        return new CsvRow(line, cells);
    }
}