package br.com.company.csvimport.domain.model;

import java.util.Objects;

/**
 * Define o esquema de uma coluna do CSV.
 *
 * @param name          nome do cabeçalho esperado
 * @param type          tipo de dado aceito
 * @param required      indica se a coluna é obrigatória
 * @param referenceType tipo de referência usada na validação de integridade, se houver
 * @param dateFormat    formato esperado para datas, se aplicável
 * @param example       exemplo de valor válido para mensagens acionáveis
 */
public record CsvColumnSchema(
        String name,
        CellType type,
        boolean required,
        String referenceType,
        String dateFormat,
        String example
) {
    /**
     * Construtor compacto com validações básicas.
     */
    public CsvColumnSchema {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(type, "type");
        if (name.isBlank()) {
            throw new IllegalArgumentException("name must not be blank");
        }
        if (referenceType != null && referenceType.isBlank()) {
            throw new IllegalArgumentException("referenceType must not be blank");
        }
        if (dateFormat != null && dateFormat.isBlank()) {
            throw new IllegalArgumentException("dateFormat must not be blank");
        }
    }

    public static CsvColumnSchema text(String name, boolean required) {
        return new CsvColumnSchema(name, CellType.TEXT, required, null, null, "texto");
    }

    public static CsvColumnSchema number(String name, boolean required) {
        return new CsvColumnSchema(name, CellType.NUMBER, required, null, null, "1234.56");
    }

    public static CsvColumnSchema date(String name, boolean required, String dateFormat) {
        return new CsvColumnSchema(name, CellType.DATE, required, null, dateFormat, "2024-01-31");
    }

    public static CsvColumnSchema email(String name, boolean required) {
        return new CsvColumnSchema(name, CellType.EMAIL, required, null, null, "usuario@empresa.com");
    }

    public static CsvColumnSchema bool(String name, boolean required) {
        return new CsvColumnSchema(name, CellType.BOOLEAN, required, null, null, "true/false/0/1");
    }

    public CsvColumnSchema withReferenceType(String referenceType) {
        return new CsvColumnSchema(name, type, required, referenceType, dateFormat, example);
    }
}