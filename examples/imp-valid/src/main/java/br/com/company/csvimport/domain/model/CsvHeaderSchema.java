package br.com.company.csvimport.domain.model;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Representa o cabeçalho esperado de um CSV.
 *
 * @param columns lista de colunas definidas pelo schema
 */
public record CsvHeaderSchema(List<CsvColumnSchema> columns) {

    /**
     * Construtor compacto que garante nomes únicos.
     */
    public CsvHeaderSchema {
        Objects.requireNonNull(columns, "columns");
        columns = List.copyOf(columns);
        long distinctNames = columns.stream().map(CsvColumnSchema::name).distinct().count();
        if (distinctNames != columns.size()) {
            throw new IllegalArgumentException("Column names must be unique");
        }
    }

    public List<String> expectedHeaders() {
        return columns.stream().map(CsvColumnSchema::name).toList();
    }

    public List<String> requiredHeaders() {
        return columns.stream().filter(CsvColumnSchema::required).map(CsvColumnSchema::name).toList();
    }

    public Optional<CsvColumnSchema> findColumn(String header) {
        return columns.stream().filter(c -> c.name().equals(header)).findFirst();
    }
}