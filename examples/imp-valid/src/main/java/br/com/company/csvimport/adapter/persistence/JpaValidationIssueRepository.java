package br.com.company.csvimport.adapter.persistence;

import br.com.company.csvimport.adapter.persistence.entity.ValidationIssueEntity;
import br.com.company.csvimport.domain.model.ValidationIssue;
import br.com.company.csvimport.domain.port.ValidationIssueRepositoryPort;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Repository Spring Data que também atua como adaptador da porta de persistência de issues.
 */
public interface JpaValidationIssueRepository
        extends JpaRepository<ValidationIssueEntity, Long>, ValidationIssueRepositoryPort {

    @Override
    @Transactional
    default void saveAll(Long batchId, List<ValidationIssue> issues) {
        for (ValidationIssue issue : issues) {
            ValidationIssueEntity entity = new ValidationIssueEntity();
            entity.setBatchId(batchId);
            entity.setLineNumber(issue.lineNumber());
            entity.setColumnName(issue.columnName());
            entity.setSeverity(issue.severity());
            entity.setType(issue.type());
            entity.setMessage(issue.message());
            entity.setSuggestion(issue.suggestion());
            entity.setRelatedLines(issue.relatedLines());
            save(entity);
        }
    }
}