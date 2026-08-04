package br.com.company.csvimport.adapter.csv;

import br.com.company.csvimport.application.dto.CsvData;
import br.com.company.csvimport.domain.model.Cell;
import br.com.company.csvimport.domain.model.CsvParseException;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.port.CsvParserPort;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.Reader;
import java.io.StringReader;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Implementação do parser de CSV usando Apache Commons CSV.
 */
@Component
public class ApacheCommonsCsvParserAdapter implements CsvParserPort {

    @Override
    public CsvData parse(byte[] contentBytes) throws CsvParseException {
        if (contentBytes == null || contentBytes.length == 0) {
            throw new CsvParseException(
                    CsvParseException.ErrorCode.EMPTY_FILE,
                    "O arquivo CSV está vazio."
            );
        }

        String decoded = decodeUtf8(contentBytes);

        try (Reader reader = new StringReader(decoded);
             CSVParser parser = CSVFormat.DEFAULT.builder()
                     .setTrim(true)
                     .get()
                     .parse(reader)) {

            List<CSVRecord> records = parser.getRecords();
            if (records.isEmpty()) {
                throw new CsvParseException(
                        CsvParseException.ErrorCode.EMPTY_FILE,
                        "O arquivo CSV está vazio."
                );
            }

            List<String> headers = normalizeHeaders(records.get(0).toList());
            if (headers.isEmpty() || headers.stream().allMatch(String::isBlank)) {
                throw new CsvParseException(
                        CsvParseException.ErrorCode.MISSING_HEADER,
                        "Cabeçalho ausente ou inválido."
                );
            }

            List<CsvRow> rows = new ArrayList<>();
            for (int i = 1; i < records.size(); i++) {
                CSVRecord record = records.get(i);
                int lineNumber = (int) record.getRecordNumber();
                List<Cell> cells = new ArrayList<>();
                for (int h = 0; h < headers.size(); h++) {
                    String value = h < record.size() ? record.get(h) : "";
                    cells.add(new Cell(headers.get(h), value, lineNumber));
                }
                rows.add(new CsvRow(lineNumber, cells));
            }

            return new CsvData(headers, rows);

        } catch (IOException ex) {
            throw new CsvParseException(
                    CsvParseException.ErrorCode.MALFORMED_CSV,
                    "Falha ao ler o CSV: " + ex.getMessage()
            );
        } catch (IllegalArgumentException ex) {
            throw new CsvParseException(
                    CsvParseException.ErrorCode.MALFORMED_CSV,
                    "CSV malformado: " + ex.getMessage()
            );
        }
    }

    private String decodeUtf8(byte[] contentBytes) {
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(contentBytes))
                    .toString();
        } catch (CharacterCodingException ex) {
            throw new CsvParseException(
                    CsvParseException.ErrorCode.INVALID_ENCODING,
                    "Encoding inválido. Salve o arquivo em UTF-8."
            );
        }
    }

    private List<String> normalizeHeaders(List<String> headers) {
        return headers.stream().map(header -> header == null ? "" : header.trim()).toList();
    }
}