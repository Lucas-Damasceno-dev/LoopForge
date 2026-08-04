package br.com.company.csvimport.domain.model;

/**
 * Tipos de dados suportados para colunas de um CSV de importação.
 */
public enum CellType {
    /** Texto livre. */
    TEXT,
    /** Valor numérico. */
    NUMBER,
    /** Data no formato configurado. */
    DATE,
    /** Endereço de e-mail. */
    EMAIL,
    /** Booleano true/false/0/1. */
    BOOLEAN
}