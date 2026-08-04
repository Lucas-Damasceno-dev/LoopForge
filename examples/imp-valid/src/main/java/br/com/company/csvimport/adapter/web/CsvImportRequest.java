package br.com.company.csvimport.adapter.web;

/**
 * Representa uma requisição de importação de CSV.
 *
 * @param fileName nome do arquivo
 * @param content  conteúdo do arquivo
 */
public record CsvImportRequest(String fileName, byte[] content) {
}