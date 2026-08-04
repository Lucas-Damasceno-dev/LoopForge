package br.com.company.csvimport.application.usecase;

/**
 * Exceção lançada quando a importação requer confirmação explícita.
 */
public class ImportConfirmationRequiredException extends RuntimeException {

    public ImportConfirmationRequiredException(String message) {
        super(message);
    }
}