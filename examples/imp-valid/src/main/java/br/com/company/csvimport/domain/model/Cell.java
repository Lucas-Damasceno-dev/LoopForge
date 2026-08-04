package br.com.company.csvimport.domain.model;

import java.util.Objects;

/**
 * Célula de uma linha do CSV.
 *
 * @param columnName nome da coluna
 * @param value      valor bruto lido do arquivo
 * @param lineNumber número da linha no arquivo original
 */
public record Cell(String columnName, String value, int lineNumber) {

    public Cell {
        Objects.requireNonNull(columnName, "columnName");
        Objects.requireNonNull(value, "value");
    }
}