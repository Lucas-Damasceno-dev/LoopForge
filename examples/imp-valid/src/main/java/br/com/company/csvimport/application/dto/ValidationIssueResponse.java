package br.com.company.csvimport.application.dto;

import br.com.company.csvimport.domain.model.ValidationIssue;

import java.util.List;

/**
 * DTO de resposta para um problema de validação.
 */
public record ValidationIssueResponse(
        String severity,
        String type,
        String message,
        Integer lineNumber,
        String columnName,
        List<Integer> relatedLines,
        String expectedValue,
        String suggestion
) {

    public static ValidationIssueResponse from(ValidationIssue issue) {
        return new ValidationIssueResponse(
                issue.severity().name(),
                issue.type().name(),
                issue.message(),
                issue.lineNumber(),
                issue.columnName(),
                issue.relatedLines(),
                issue.expectedValue(),
                issue.suggestion()
        );
    }
}