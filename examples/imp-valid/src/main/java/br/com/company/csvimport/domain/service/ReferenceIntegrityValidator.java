package br.com.company.csvimport.domain.service;

import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ReferenceRule;
import br.com.company.csvimport.domain.model.ValidationIssue;
import br.com.company.csvimport.domain.port.ReferenceLookupPort;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * Valida a integridade referencial dos IDs existentes no CSV.
 */
public class ReferenceIntegrityValidator {

    private final ReferenceLookupPort referenceLookupPort;

    public ReferenceIntegrityValidator(ReferenceLookupPort referenceLookupPort) {
        this.referenceLookupPort = Objects.requireNonNull(referenceLookupPort, "referenceLookupPort");
    }

    /**
     * Valida todas as regras de referência de uma linha.
     *
     * @param row            linha do CSV
     * @param referenceRules regras de referência
     * @return problemas de integridade referencial
     */
    public List<ValidationIssue> validate(CsvRow row, List<ReferenceRule> referenceRules) {
        List<ValidationIssue> issues = new ArrayList<>();
        for (ReferenceRule rule : referenceRules) {
            String value = row.value(rule.columnName());
            if (value == null || value.isBlank()) {
                if (rule.required()) {
                    issues.add(ValidationIssue.builder()
                            .severity(ValidationIssue.Severity.CRITICAL)
                            .type(ValidationIssue.Type.REFERENCE)
                            .lineNumber(row.lineNumber())
                            .columnName(rule.columnName())
                            .message(String.format(
                                    "Linha %d, coluna '%s': referência obrigatória vazia.",
                                    row.lineNumber(), rule.columnName()))
                            .suggestion("Preencha a referência com um ID existente em " + rule.referenceType() + ".")
                            .build());
                }
                continue;
            }

            if (!referenceLookupPort.exists(rule.referenceType(), value.trim())) {
                issues.add(ValidationIssue.builder()
                        .severity(ValidationIssue.Severity.CRITICAL)
                        .type(ValidationIssue.Type.REFERENCE)
                        .lineNumber(row.lineNumber())
                        .columnName(rule.columnName())
                        .message(String.format(
                                "Linha %d, coluna '%s': valor '%s' não existe na referência '%s'.",
                                row.lineNumber(), rule.columnName(), value, rule.referenceType()))
                        .suggestion("Cadastre o registro referenciado ou corrija o valor na linha " + row.lineNumber() + ".")
                        .build());
            }
        }
        return issues;
    }
}