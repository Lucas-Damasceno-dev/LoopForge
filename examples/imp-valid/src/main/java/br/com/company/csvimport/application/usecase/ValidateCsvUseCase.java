package br.com.company.csvimport.application.usecase;

import br.com.company.csvimport.application.dto.CsvData;
import br.com.company.csvimport.domain.model.CsvImportConfig;
import br.com.company.csvimport.domain.model.CsvParseException;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ValidationIssue;
import br.com.company.csvimport.domain.port.CsvParserPort;
import br.com.company.csvimport.domain.port.ReferenceLookupPort;
import br.com.company.csvimport.domain.service.DuplicateDetector;
import br.com.company.csvimport.domain.service.ReferenceIntegrityValidator;
import br.com.company.csvimport.domain.service.TypeValidator;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * Caso de uso orquestrador da validação de CSV.
 */
@Service
public class ValidateCsvUseCase {

    private final CsvParserPort csvParserPort;
    private final TypeValidator typeValidator;
    private final DuplicateDetector duplicateDetector;
    private final ReferenceIntegrityValidator referenceIntegrityValidator;
    private final CsvImportConfig config;

    public ValidateCsvUseCase(
            CsvParserPort csvParserPort,
            TypeValidator typeValidator,
            DuplicateDetector duplicateDetector,
            ReferenceIntegrityValidator referenceIntegrityValidator,
            CsvImportConfig config
    ) {
        this.csvParserPort = csvParserPort;
        this.typeValidator = typeValidator;
        this.duplicateDetector = duplicateDetector;
        this.referenceIntegrityValidator = referenceIntegrityValidator;
        this.config = config;
    }

    /**
     * Executa a validação completa de um arquivo CSV.
     *
     * @param command comando com nome e conteúdo do arquivo
     * @return resultado consolidado da validação
     */
    public CsvValidationResult execute(ValidateCsvCommand command) {
        if (command.content() == null || command.content().length == 0) {
            return CsvValidationResult.fatal(command.fileName(), ValidationIssue.builder()
                    .severity(ValidationIssue.Severity.CRITICAL)
                    .type(ValidationIssue.Type.EMPTY_FILE)
                    .message("O arquivo CSV está vazio.")
                    .suggestion("Envie um arquivo contendo cabeçalho e ao menos uma linha de dados.")
                    .build());
        }

        CsvData data;
        try {
            data = csvParserPort.parse(command.content());
        } catch (CsvParseException ex) {
            return handleParseException(command.fileName(), ex);
        }

        List<ValidationIssue> issues = new ArrayList<>();

        List<String> actualHeaders = normalizeHeaders(data.headers());
        List<String> expectedHeaders = config.schema().expectedHeaders();

        boolean hasAnyExpectedHeader = expectedHeaders.stream().anyMatch(actualHeaders::contains);
        if (!hasAnyExpectedHeader) {
            issues.add(structureIssue("Cabeçalho ausente ou incompatível. Cabeçalhos esperados: " + expectedHeaders));
            return result(command.fileName(), 0, issues);
        }

        List<String> missingRequired = config.schema().requiredHeaders().stream()
                .filter(header -> !actualHeaders.contains(header))
                .toList();
        if (!missingRequired.isEmpty()) {
            issues.add(structureIssue("Cabeçalho incompleto. Colunas obrigatórias ausentes: " + missingRequired
                    + ". Cabeçalhos esperados: " + expectedHeaders));
            return result(command.fileName(), 0, issues);
        }

        for (CsvRow row : data.rows()) {
            issues.addAll(typeValidator.validate(row, config.schema()));
        }

        if (config.businessKeyRule() != null) {
            issues.addAll(duplicateDetector.detectPartialDuplicates(data.rows(), config.businessKeyRule()));
        }
        issues.addAll(duplicateDetector.detectExactDuplicates(data.rows()));

        for (CsvRow row : data.rows()) {
            issues.addAll(referenceIntegrityValidator.validate(row, config.referenceRules()));
        }

        return result(command.fileName(), data.rows().size(), issues);
    }

    private CsvValidationResult result(String fileName, int rowCount, List<ValidationIssue> issues) {
        return CsvValidationResult.builder()
                .fileName(fileName)
                .rowCount(rowCount)
                .issues(issues)
                .build();
    }

    private CsvValidationResult handleParseException(String fileName, CsvParseException ex) {
        ValidationIssue.Type type = switch (ex.code()) {
            case EMPTY_FILE -> ValidationIssue.Type.EMPTY_FILE;
            case INVALID_ENCODING -> ValidationIssue.Type.INVALID_ENCODING;
            case MALFORMED_CSV, MISSING_HEADER -> ValidationIssue.Type.STRUCTURE;
        };

        String suggestion = switch (ex.code()) {
            case EMPTY_FILE -> "Envie um arquivo contendo cabeçalho e ao menos uma linha de dados.";
            case INVALID_ENCODING -> "Salve o arquivo como UTF-8.";
            case MALFORMED_CSV, MISSING_HEADER -> "Verifique a estrutura do CSV, incluindo cabeçalho e aspas.";
        };

        return CsvValidationResult.fatal(fileName, ValidationIssue.builder()
                .severity(ValidationIssue.Severity.CRITICAL)
                .type(type)
                .message(ex.getMessage())
                .suggestion(suggestion)
                .build());
    }

    private List<String> normalizeHeaders(List<String> headers) {
        if (headers == null) {
            return List.of();
        }
        return headers.stream().map(header -> header == null ? "" : header.trim()).toList();
    }

    private ValidationIssue structureIssue(String message) {
        return ValidationIssue.builder()
                .severity(ValidationIssue.Severity.CRITICAL)
                .type(ValidationIssue.Type.STRUCTURE)
                .message(message)
                .suggestion("Corrija o cabeçalho do arquivo usando os nomes esperados.")
                .build();
    }
}