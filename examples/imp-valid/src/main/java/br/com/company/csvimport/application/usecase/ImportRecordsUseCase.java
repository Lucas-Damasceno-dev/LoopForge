package br.com.company.csvimport.application.usecase;

import br.com.company.csvimport.domain.model.ImportBatch;
import br.com.company.csvimport.domain.port.ImportBatchRepositoryPort;
import org.springframework.stereotype.Service;

import java.time.Instant;

/**
 * Caso de uso responsável por executar ou bloquear a importação após a validação.
 */
@Service
public class ImportRecordsUseCase {

    private final ImportBatchRepositoryPort importBatchRepository;

    public ImportRecordsUseCase(ImportBatchRepositoryPort importBatchRepository) {
        this.importBatchRepository = importBatchRepository;
    }

    /**
     * Executa a importação respeitando o resultado da validação.
     *
     * @param result                resultado da validação
     * @param fileName              nome do arquivo original
     * @param confirmationConfirmed indica se o usuário confirmou a importação com avisos
     * @throws ImportBlockedException                se existirem erros críticos
     * @throws ImportConfirmationRequiredException   se houver avisos e não houver confirmação
     */
    public void execute(CsvValidationResult result, String fileName, boolean confirmationConfirmed) {
        if (!result.importAllowed()) {
            throw new ImportBlockedException(
                    "Importação bloqueada: " + result.criticalCount()
                            + " erro(s) crítico(s). Nenhum registro foi gravado.");
        }

        if (result.requiresConfirmation() && !confirmationConfirmed) {
            throw new ImportConfirmationRequiredException(
                    "Importação requer confirmação: há " + result.warningCount() + " aviso(s).");
        }

        importBatchRepository.save(new ImportBatch(
                fileName,
                ImportBatch.ImportStatus.IMPORTED,
                Instant.now(),
                result.rowCount(),
                result.issues().size()
        ));
    }
}