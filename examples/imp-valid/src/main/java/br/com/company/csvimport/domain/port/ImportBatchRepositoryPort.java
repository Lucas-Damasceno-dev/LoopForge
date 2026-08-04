package br.com.company.csvimport.domain.port;

import br.com.company.csvimport.domain.model.ImportBatch;

/**
 * Porta para persistência de lotes de importação.
 */
public interface ImportBatchRepositoryPort {

    /**
     * Persiste um lote de importação.
     *
     * @param batch lote a persistir
     */
    void save(ImportBatch batch);
}