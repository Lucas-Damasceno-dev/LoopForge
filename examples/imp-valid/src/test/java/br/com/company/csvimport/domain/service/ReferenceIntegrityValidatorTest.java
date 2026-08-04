package br.com.company.csvimport.domain.service;

import br.com.company.csvimport.domain.model.Cell;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ReferenceRule;
import br.com.company.csvimport.domain.model.ValidationIssue;
import br.com.company.csvimport.domain.port.ReferenceLookupPort;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReferenceIntegrityValidatorTest {

    @Test
    void givenReferencedIdDoesNotExist_thenReferenceErrorWithLineAndColumn() {
        ReferenceLookupPort lookup = (type, value) -> "1".equals(value);
        ReferenceIntegrityValidator validator = new ReferenceIntegrityValidator(lookup);
        CsvRow row = row(4, "999");

        List<ValidationIssue> issues = validator.validate(
                row,
                List.of(new ReferenceRule("parent_id", "PARENT", false))
        );

        ValidationIssue issue = issues.stream()
                .filter(i -> i.type() == ValidationIssue.Type.REFERENCE)
                .findFirst()
                .orElseThrow();

        assertEquals(4, issue.lineNumber());
        assertEquals("parent_id", issue.columnName());
    }

    @Test
    void givenAllReferencedIdsExist_thenNoReferenceError() {
        ReferenceLookupPort lookup = (type, value) -> true;
        ReferenceIntegrityValidator validator = new ReferenceIntegrityValidator(lookup);
        CsvRow row = row(4, "1");

        List<ValidationIssue> issues = validator.validate(
                row,
                List.of(new ReferenceRule("parent_id", "PARENT", false))
        );

        assertTrue(issues.isEmpty());
    }

    @Test
    void givenRequiredReferenceEmpty_thenCriticalReferenceError() {
        ReferenceLookupPort lookup = (type, value) -> false;
        ReferenceIntegrityValidator validator = new ReferenceIntegrityValidator(lookup);
        CsvRow row = row(4, "");

        List<ValidationIssue> issues = validator.validate(
                row,
                List.of(new ReferenceRule("parent_id", "PARENT", true))
        );

        ValidationIssue issue = issues.stream()
                .filter(i -> i.type() == ValidationIssue.Type.REFERENCE)
                .findFirst()
                .orElseThrow();

        assertEquals(ValidationIssue.Severity.CRITICAL, issue.severity());
        assertTrue(issue.message().contains("obrigatória"));
    }

    private CsvRow row(int line, String parentId) {
        return new CsvRow(line, List.of(new Cell("parent_id", parentId, line)));
    }
}