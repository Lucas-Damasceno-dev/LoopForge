package br.com.company.csvimport.application.usecase;

/**
 * Exceção lançada quando a importação é bloqueada por erros críticos.
 */
public class ImportBlockedException extends RuntimeException {

    public ImportBlockedException(String message) {
        super(message);
    }
}