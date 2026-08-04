package br.com.company.csvimport.infrastructure.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Propriedades de configuração da aplicação.
 *
 * @param encoding         encoding esperado para os arquivos CSV
 * @param dateFormat       formato de data padrão
 * @param maxFileSizeBytes tamanho máximo permitido do arquivo
 */
@ConfigurationProperties(prefix = "csvimport")
public record CsvImportProperties(
        String encoding,
        String dateFormat,
        long maxFileSizeBytes
) {

    public CsvImportProperties {
        encoding = encoding != null ? encoding : "UTF-8";
        dateFormat = dateFormat != null ? dateFormat : "yyyy-MM-dd";
        if (maxFileSizeBytes <= 0) {
            maxFileSizeBytes = 10 * 1024 * 1024;
        }
    }
}