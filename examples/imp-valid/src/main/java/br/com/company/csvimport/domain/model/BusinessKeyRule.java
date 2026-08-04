package br.com.company.csvimport.domain.model;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Define a chave de negócio usada para detectar duplicatas parciais.
 *
 * @param columnNames colunas que compõem a chave de negócio
 */
public record BusinessKeyRule(List<String> columnNames) {

    public BusinessKeyRule {
        Objects.requireNonNull(columnNames, "columnNames");
        columnNames = List.copyOf(columnNames);
        if (columnNames.isEmpty() || columnNames.stream().anyMatch(String::isBlank)) {
            throw new IllegalArgumentException("A chave de negócio deve ter ao menos uma coluna");
        }
    }

    /**
     * Extrai a chave de negócio de uma linha.
     *
     * @param row linha do CSV
     * @return chave composta, ou vazio se algum campo estiver vazio
     */
    public Optional<String> extractKey(CsvRow row) {
        for (String column : columnNames) {
            String value = row.value(column);
            if (value == null || value.isBlank()) {
                return Optional.empty();
            }
        }
        String key = columnNames.stream()
                .map(column -> row.value(column).trim())
                .collect(Collectors.joining("|"));
        return Optional.of(key);
    }

    public String describe() {
        return String.join(", ", columnNames);
    }
}