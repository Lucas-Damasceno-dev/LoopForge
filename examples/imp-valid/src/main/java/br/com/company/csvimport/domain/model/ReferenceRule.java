package br.com.company.csvimport.domain.model;

import java.util.Objects;

/**
 * Regra de integridade referencial para uma coluna do CSV.
 *
 * @param columnName    coluna que contém o identificador referenciado
 * @param referenceType tipo/nome da referência validada
 * @param required      se a referência é obrigatória
 */
public record ReferenceRule(String columnName, String referenceType, boolean required) {

    public ReferenceRule {
        Objects.requireNonNull(columnName, "columnName");
        Objects.requireNonNull(referenceType, "referenceType");
        if (columnName.isBlank() || referenceType.isBlank()) {
            throw new IllegalArgumentException("columnName and referenceType must not be blank");
        }
    }
}