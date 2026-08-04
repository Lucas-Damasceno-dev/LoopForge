package br.com.company.csvimport.domain.port;

import br.com.company.csvimport.domain.model.ValidationIssue;

import java.util.List;

/**
 * Porta para persistência de problemas de validação.
 */
public interface ValidationIssueRepositoryPort {

    /**
     * Persiste uma lista de problemas associada a um lote.
     *
     * @param batchId identificador do lote
     * @param issues  problemas encontrados
     */
    void saveAll(Long batchId, List<ValidationIssue> issues);
}