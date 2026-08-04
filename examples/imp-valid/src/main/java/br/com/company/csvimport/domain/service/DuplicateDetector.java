package br.com.company.csvimport.domain.service;

import br.com.company.csvimport.domain.model.BusinessKeyRule;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ValidationIssue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Detecta linhas duplicadas exatas e duplicatas parciais por chave de negócio.
 */
public class DuplicateDetector {

    /**
     * Detecta linhas exatamente idênticas.
     *
     * @param rows linhas do CSV
     * @return problemas de duplicidade exata
     */
    public List<ValidationIssue> detectExactDuplicates(List<CsvRow> rows) {
        List<ValidationIssue> issues = new ArrayList<>();
        Map<String, List<CsvRow>> groups = new LinkedHashMap<>();
        for (CsvRow row : rows) {
            groups.computeIfAbsent(row.exactKey(), key -> new ArrayList<>()).add(row);
        }

        for (Map.Entry<String, List<CsvRow>> entry : groups.entrySet()) {
            List<CsvRow> group = entry.getValue();
            if (group.size() < 2) {
                continue;
            }
            List<Integer> lines = group.stream()
                    .map(CsvRow::lineNumber)
                    .sorted()
                    .toList();

            issues.add(ValidationIssue.builder()
                    .severity(ValidationIssue.Severity.CRITICAL)
                    .type(ValidationIssue.Type.DUPLICATE_EXACT)
                    .lineNumber(lines.get(0))
                    .relatedLines(lines)
                    .message("Duplicidade exata encontrada nas linhas " + lines + ".")
                    .suggestion("Remova as linhas duplicadas exatas antes de importar: " + lines)
                    .build());
        }
        return issues;
    }

    /**
     * Detecta duplicatas parciais pela chave de negócio configurada.
     *
     * @param rows            linhas do CSV
     * @param businessKeyRule regra da chave de negócio
     * @return problemas de duplicidade parcial
     */
    public List<ValidationIssue> detectPartialDuplicates(List<CsvRow> rows, BusinessKeyRule businessKeyRule) {
        List<ValidationIssue> issues = new ArrayList<>();
        Map<String, List<CsvRow>> groups = new LinkedHashMap<>();

        for (CsvRow row : rows) {
            businessKeyRule.extractKey(row).ifPresent(key ->
                    groups.computeIfAbsent(key, k -> new ArrayList<>()).add(row));
        }

        for (Map.Entry<String, List<CsvRow>> entry : groups.entrySet()) {
            List<CsvRow> group = entry.getValue();
            if (group.size() < 2) {
                continue;
            }
            List<Integer> lines = group.stream()
                    .map(CsvRow::lineNumber)
                    .sorted()
                    .toList();

            issues.add(ValidationIssue.builder()
                    .severity(ValidationIssue.Severity.WARNING)
                    .type(ValidationIssue.Type.DUPLICATE_PARTIAL)
                    .lineNumber(lines.get(0))
                    .columnName(businessKeyRule.describe())
                    .relatedLines(lines)
                    .message("Duplicata parcial detectada nas linhas " + lines
                            + " para a chave de negócio [" + businessKeyRule.describe() + "].")
                    .expectedValue(entry.getKey())
                    .suggestion("Revise as duplicatas parciais apontadas pela chave de negócio.")
                    .build());
        }
        return issues;
    }
}