package br.com.company.csvimport.domain.port;

import br.com.company.csvimport.application.dto.CsvData;
import br.com.company.csvimport.domain.model.CsvParseException;

/**
 * Porta para leitura e interpretação de arquivos CSV.
 */
public interface CsvParserPort {

    /**
     * Converte o conteúdo binário em dados estruturados.
     *
     * @param contentBytes bytes do arquivo CSV
     * @return dados estruturados com cabeçalho e linhas
     * @throws CsvParseException se o arquivo estiver vazio, malformado ou com encoding inválido
     */
    CsvData parse(byte[] contentBytes) throws CsvParseException;
}