package br.com.company.csvimport.domain.model;

import java.util.Objects;

/**
 * Exceção lançada quando o parser não consegue interpretar o arquivo CSV.
 */
public class CsvParseException extends RuntimeException {

    public enum ErrorCode {
        EMPTY_FILE,
        INVALID_ENCODING,
        MALFORMED_CSV,
        MISSING_HEADER
    }

    private final ErrorCode code;

    public CsvParseException(ErrorCode code, String message) {
        super(message);
        this.code = Objects.requireNonNull(code, "code");
    }

    public ErrorCode code() {
        return code;
    }
}