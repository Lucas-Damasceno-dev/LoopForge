package br.com.company.csvimport.adapter.persistence;

import br.com.company.csvimport.adapter.persistence.entity.ImportBatchEntity;
import br.com.company.csvimport.domain.model.ImportBatch;
import br.com.company.csvimport.domain.port.ImportBatchRepositoryPort;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;

/**
 * Repository Spring Data que também atua como adaptador da porta de persistência.
 */
public interface JpaImportBatchRepository extends JpaRepository<ImportBatchEntity, Long>, ImportBatchRepositoryPort {

    @Override
    @Transactional
    default void save(ImportBatch batch) {
        ImportBatchEntity entity = new ImportBatchEntity();
        entity.setFileName(batch.fileName());
        entity.setStatus(batch.status());
        entity.setImportedAt(batch.importedAt());
        entity.setRowCount(batch.rowCount());
        entity.setIssueCount(batch.issueCount());
        save(entity);
    }
}