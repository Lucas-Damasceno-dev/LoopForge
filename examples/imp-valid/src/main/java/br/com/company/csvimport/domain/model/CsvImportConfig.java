package br.com.company.csvimport.domain.model;

import java.util.List;
import java.util.Objects;

/**
 * Configuração completa para uma operação de validação de CSV.
 *
 * @param schema          schema de colunas e cabeçalho
 * @param referenceRules  regras de integridade referencial
 * @param businessKeyRule chave de negócio para duplicidade parcial
 */
public record CsvImportConfig(
        CsvHeaderSchema schema,
        List<ReferenceRule> referenceRules,
        BusinessKeyRule businessKeyRule
) {

    public CsvImportConfig {
        Objects.requireNonNull(schema, "schema");
        referenceRules = referenceRules == null ? List.of() : List.copyOf(referenceRules);
    }
}