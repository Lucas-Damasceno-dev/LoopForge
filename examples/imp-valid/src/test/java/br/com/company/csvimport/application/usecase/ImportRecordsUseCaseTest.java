package br.com.company.csvimport.application.usecase;

import br.com.company.csvimport.domain.model.ImportBatch;
import br.com.company.csvimport.domain.model.ValidationIssue;
import br.com.company.csvimport.domain.port.ImportBatchRepositoryPort;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ImportRecordsUseCaseTest {

    @Test
    void givenCriticalErrors_whenImport_thenBlockedAndNoRecordPersisted() {
        FakeRepository repository = new FakeRepository();
        ImportRecordsUseCase useCase = new ImportRecordsUseCase(repository);
        CsvValidationResult blocked = resultWith(criticalIssue());

        assertThrows(ImportBlockedException.class,
                () -> useCase.execute(blocked, "file.csv", false));

        assertTrue(repository.saved.isEmpty());
    }

    @Test
    void givenOnlyWarnings_whenImport_thenAllowedAfterExplicitConfirmation() {
        FakeRepository repository = new FakeRepository();
        ImportRecordsUseCase useCase = new ImportRecordsUseCase(repository);
        CsvValidationResult warningResult = resultWith(warningIssue());

        assertThrows(ImportConfirmationRequiredException.class,
                () -> useCase.execute(warningResult, "file.csv", false));

        useCase.execute(warningResult, "file.csv", true);

        assertEquals(1, repository.saved.size());
    }

    @Test
    void givenNoCriticalErrors_whenImport_thenImportExecutesNormally() {
        FakeRepository repository = new FakeRepository();
        ImportRecordsUseCase useCase = new ImportRecordsUseCase(repository);
        CsvValidationResult clean = CsvValidationResult.builder()
                .fileName("clean.csv")
                .rowCount(2)
                .issues(List.of())
                .build();

        useCase.execute(clean, "clean.csv", false);

        assertEquals(1, repository.saved.size());
        assertEquals(ImportBatch.ImportStatus.IMPORTED, repository.saved.get(0).status());
    }

    private CsvValidationResult resultWith(ValidationIssue issue) {
        return CsvValidationResult.builder()
                .fileName("file.csv")
                .rowCount(1)
                .issues(List.of(issue))
                .build();
    }

    private ValidationIssue criticalIssue() {
        return ValidationIssue.builder()
                .severity(ValidationIssue.Severity.CRITICAL)
                .type(ValidationIssue.Type.TYPE)
                .lineNumber(2)
                .columnName("id")
                .message("Erro crítico")
                .build();
    }

    private ValidationIssue warningIssue() {
        return ValidationIssue.builder()
                .severity(ValidationIssue.Severity.WARNING)
                .type(ValidationIssue.Type.DUPLICATE_PARTIAL)
                .lineNumber(2)
                .columnName("name")
                .message("Aviso de duplicidade parcial")
                .relatedLines(List.of(2, 3))
                .build();
    }

    private static final class FakeRepository implements ImportBatchRepositoryPort {
        private final List<ImportBatch> saved = new ArrayList<>();

        @Override
        public void save(ImportBatch batch) {
            saved.add(batch);
        }
    }
}