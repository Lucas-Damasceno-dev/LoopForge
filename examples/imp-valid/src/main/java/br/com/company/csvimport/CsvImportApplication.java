package br.com.company.csvimport;

import br.com.company.csvimport.infrastructure.config.CsvImportProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

/**
 * Ponto de entrada da aplicação Spring Boot.
 */
@SpringBootApplication
@EnableConfigurationProperties(CsvImportProperties.class)
public class CsvImportApplication {

    /**
     * Método principal que inicializa a aplicação.
     *
     * @param args argumentos de linha de comando
     */
    public static void main(String[] args) {
        SpringApplication.run(CsvImportApplication.class, args);
    }
}