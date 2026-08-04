package br.com.company.csvimport.domain.model;

import java.time.Instant;

/**
 * Representa um lote de importação persistido ou bloqueado.
 *
 * @param fileName   nome do arquivo original
 * @param status     situação da importação
 * @param importedAt data/hora da tentativa
 * @param rowCount   quantidade de linhas processadas
 * @param issueCount quantidade de problemas encontrados
 */
public record ImportBatch(
        String fileName,
        ImportStatus status,
        Instant importedAt,
        int rowCount,
        int issueCount
) {

    public enum ImportStatus {
        IMPORTED,
        BLOCKED,
        CONFIRMATION_REQUIRED
    }
}