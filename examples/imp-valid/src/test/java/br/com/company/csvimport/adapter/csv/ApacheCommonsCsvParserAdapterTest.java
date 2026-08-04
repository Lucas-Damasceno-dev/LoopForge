package br.com.company.csvimport.adapter.csv;

import br.com.company.csvimport.application.dto.CsvData;
import br.com.company.csvimport.domain.model.CsvParseException;
import br.com.company.csvimport.domain.port.CsvParserPort;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ApacheCommonsCsvParserAdapterTest {

    private final CsvParserPort parser = new ApacheCommonsCsvParserAdapter();

    @Test
    void givenEmptyCsvContent_thenThrowsEmptyFile() {
        CsvParseException ex = assertThrows(
                CsvParseException.class,
                () -> parser.parse(new byte[0])
        );
        assertEquals(CsvParseException.ErrorCode.EMPTY_FILE, ex.code());
    }

    @Test
    void givenInvalidUtf8Content_thenThrowsInvalidEncoding() {
        byte[] invalid = new byte[]{(byte) 0xC3, 0x28};
        CsvParseException ex = assertThrows(
                CsvParseException.class,
                () -> parser.parse(invalid)
        );
        assertEquals(CsvParseException.ErrorCode.INVALID_ENCODING, ex.code());
        org.junit.jupiter.api.Assertions.assertTrue(ex.getMessage().contains("UTF-8"));
    }

    @Test
    void givenValidCsvContent_thenParsesHeadersAndRows() throws Exception {
        String csv = "id,name\n1,João\n";
        byte[] content = csv.getBytes(StandardCharsets.UTF_8);

        CsvData data = parser.parse(content);

        assertEquals(java.util.List.of("id", "name"), data.headers());
        assertEquals(2, data.rows().get(0).lineNumber());
        assertEquals("João", data.rows().get(0).value("name"));
    }
}