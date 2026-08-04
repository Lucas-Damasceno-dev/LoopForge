package br.com.company.csvimport.adapter.persistence.entity;

import br.com.company.csvimport.domain.model.ValidationIssue;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.util.ArrayList;
import java.util.List;

/**
 * Entidade JPA para problemas de validação.
 */
@Entity
@Table(name = "validation_issue")
public class ValidationIssueEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long batchId;

    @Column(nullable = false)
    private int lineNumber;

    private String columnName;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ValidationIssue.Severity severity;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ValidationIssue.Type type;

    @Column(length = 2000, nullable = false)
    private String message;

    @Column(length = 1000)
    private String suggestion;

    @ElementCollection(fetch = FetchType.EAGER)
    private List<Integer> relatedLines = new ArrayList<>();

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getBatchId() {
        return batchId;
    }

    public void setBatchId(Long batchId) {
        this.batchId = batchId;
    }

    public int getLineNumber() {
        return lineNumber;
    }

    public void setLineNumber(int lineNumber) {
        this.lineNumber = lineNumber;
    }

    public String getColumnName() {
        return columnName;
    }

    public void setColumnName(String columnName) {
        this.columnName = columnName;
    }

    public ValidationIssue.Severity getSeverity() {
        return severity;
    }

    public void setSeverity(ValidationIssue.Severity severity) {
        this.severity = severity;
    }

    public ValidationIssue.Type getType() {
        return type;
    }

    public void setType(ValidationIssue.Type type) {
        this.type = type;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getSuggestion() {
        return suggestion;
    }

    public void setSuggestion(String suggestion) {
        this.suggestion = suggestion;
    }

    public List<Integer> getRelatedLines() {
        return relatedLines;
    }

    public void setRelatedLines(List<Integer> relatedLines) {
        this.relatedLines = relatedLines;
    }
}