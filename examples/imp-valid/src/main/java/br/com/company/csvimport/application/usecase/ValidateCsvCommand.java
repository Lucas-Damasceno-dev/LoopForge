package br.com.company.csvimport.application.usecase;

/**
 * Comando para execução da validação de um CSV.
 *
 * @param fileName nome do arquivo original
 * @param content  conteúdo binário do arquivo
 */
public record ValidateCsvCommand(String fileName, byte[] content) {
}