package br.com.company.csvimport.adapter.reference;

import br.com.company.csvimport.domain.port.ReferenceLookupPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * Consulta de referências usando JDBC.
 */
@Component
public class JdbcReferenceLookupAdapter implements ReferenceLookupPort {

    private final JdbcTemplate jdbcTemplate;

    public JdbcReferenceLookupAdapter(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public boolean exists(String referenceType, String value) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM reference_registry WHERE reference_type = ? AND reference_value = ?",
                Integer.class,
                referenceType,
                value
        );
        return count != null && count > 0;
    }
}