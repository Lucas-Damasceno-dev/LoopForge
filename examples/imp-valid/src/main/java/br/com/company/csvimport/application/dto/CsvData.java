package br.com.company.csvimport.application.dto;

import br.com.company.csvimport.domain.model.CsvRow;

import java.util.List;

/**
 * Dados estruturados de um CSV lido.
 *
 * @param headers cabeçalhos encontrados no arquivo
 * @param rows    linhas de dados
 */
public record CsvData(List<String> headers, List<CsvRow> rows) {

    public CsvData {
        headers = headers == null ? List.of() : List.copyOf(headers);
        rows = rows == null ? List.of() : List.copyOf(rows);
    }
}