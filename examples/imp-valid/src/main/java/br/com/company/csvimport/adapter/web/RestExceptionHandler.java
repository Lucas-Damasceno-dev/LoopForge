package br.com.company.csvimport.adapter.web;

import br.com.company.csvimport.application.usecase.ImportBlockedException;
import br.com.company.csvimport.application.usecase.ImportConfirmationRequiredException;
import br.com.company.csvimport.domain.model.CsvParseException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;

/**
 * Handler global de erros da API REST.
 */
@RestControllerAdvice
public class RestExceptionHandler {

    @ExceptionHandler(CsvParseException.class)
    public ResponseEntity<ApiError> handleCsvParse(CsvParseException ex) {
        return ResponseEntity.badRequest().body(new ApiError(ex.getMessage(), List.of()));
    }

    @ExceptionHandler(ImportBlockedException.class)
    public ResponseEntity<ApiError> handleImportBlocked(ImportBlockedException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(new ApiError(ex.getMessage(), List.of()));
    }

    @ExceptionHandler(ImportConfirmationRequiredException.class)
    public ResponseEntity<ApiError> handleImportConfirmation(ImportConfirmationRequiredException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(new ApiError(ex.getMessage(), List.of()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> handleValidation(MethodArgumentNotValidException ex) {
        return ResponseEntity.badRequest().body(new ApiError("Requisição inválida", List.of()));
    }

    /**
     * Estrutura de erro retornada pela API.
     */
    public record ApiError(String message, List<String> details) {
    }
}