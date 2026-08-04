package br.com.company.csvimport.domain.port;

/**
 * Porta para consulta de existência de valores de referência.
 */
public interface ReferenceLookupPort {

    /**
     * Verifica se um valor existe para determinado tipo de referência.
     *
     * @param referenceType tipo da referência
     * @param value         valor a verificar
     * @return {@code true} se existir
     */
    boolean exists(String referenceType, String value);
}