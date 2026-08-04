package br.com.company.csvimport.infrastructure.config;

import br.com.company.csvimport.domain.model.BusinessKeyRule;
import br.com.company.csvimport.domain.model.CsvColumnSchema;
import br.com.company.csvimport.domain.model.CsvHeaderSchema;
import br.com.company.csvimport.domain.model.CsvImportConfig;
import br.com.company.csvimport.domain.model.ReferenceRule;
import br.com.company.csvimport.domain.port.ReferenceLookupPort;
import br.com.company.csvimport.domain.service.DuplicateDetector;
import br.com.company.csvimport.domain.service.ReferenceIntegrityValidator;
import br.com.company.csvimport.domain.service.TypeValidator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * Configuração dos beans de domínio e serviços da aplicação.
 */
@Configuration
public class CsvValidatorConfiguration {

    @Bean
    public TypeValidator typeValidator() {
        return new TypeValidator();
    }

    @Bean
    public DuplicateDetector duplicateDetector() {
        return new DuplicateDetector();
    }

    @Bean
    public ReferenceIntegrityValidator referenceIntegrityValidator(ReferenceLookupPort referenceLookupPort) {
        return new ReferenceIntegrityValidator(referenceLookupPort);
    }

    @Bean
    public CsvImportConfig csvImportConfig() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.number("id", true),
                CsvColumnSchema.text("name", true),
                CsvColumnSchema.email("email", false),
                CsvColumnSchema.date("birth_date", false, "yyyy-MM-dd"),
                CsvColumnSchema.bool("active", false),
                CsvColumnSchema.number("parent_id", false).withReferenceType("PARENT")
        ));

        return new CsvImportConfig(
                schema,
                List.of(new ReferenceRule("parent_id", "PARENT", false)),
                new BusinessKeyRule(List.of("name"))
        );
    }
}