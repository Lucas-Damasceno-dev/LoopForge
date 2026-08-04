package br.com.company.csvimport.application.usecase;

import br.com.company.csvimport.application.dto.CsvData;
import br.com.company.csvimport.domain.model.BusinessKeyRule;
import br.com.company.csvimport.domain.model.Cell;
import br.com.company.csvimport.domain.model.CsvColumnSchema;
import br.com.company.csvimport.domain.model.CsvHeaderSchema;
import br.com.company.csvimport.domain.model.CsvImportConfig;
import br.com.company.csvimport.domain.model.CsvParseException;
import br.com.company.csvimport.domain.model.CsvRow;
import br.com.company.csvimport.domain.model.ReferenceRule;
import br.com.company.csvimport.domain.model.ValidationIssue;
import br.com.company.csvimport.domain.port.CsvParserPort;
import br.com.company.csvimport.domain.port.ReferenceLookupPort;
import br.com.company.csvimport.domain.service.DuplicateDetector;
import br.com.company.csvimport.domain.service.ReferenceIntegrityValidator;
import br.com.company.csvimport.domain.service.TypeValidator;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ValidateCsvUseCaseAcceptanceTest {

    @Test
    void givenFileWithCorrectHeaders_whenUpload_thenAcceptsAndStartsValidation() {
        CsvData data = data(
                List.of("id", "name", "email", "dt", "active", "parent_id"),
                List.of(List.of("1", "Maria", "maria@example.com", "1990-01-01", "true", ""))
        );
        ValidateCsvUseCase useCase = useCase(parserReturning(data), exists(), config());

        CsvValidationResult result = useCase.execute(command(data));

        assertTrue(result.importAllowed());
        assertTrue(result.issues().stream().noneMatch(i -> i.type() == ValidationIssue.Type.STRUCTURE));
    }

    @Test
    void givenCsvWithoutHeader_whenUpload_thenShowsStructureErrorAndBlocks() {
        CsvData data = data(List.of("1", "Maria"), List.of());
        ValidateCsvUseCase useCase = useCase(parserReturning(data), exists(), config());

        CsvValidationResult result = useCase.execute(command(data));

        assertTrue(result.issues().stream().anyMatch(i -> i.type() == ValidationIssue.Type.STRUCTURE));
        assertFalse(result.importAllowed());
    }

    @Test
    void givenMissingRequiredColumns_whenUpload_thenListsExpectedAndBlocks() {
        CsvData data = data(
                List.of("id", "email", "dt", "active", "parent_id"),
                List.of(List.of("1", "maria@example.com", "1990-01-01", "true", ""))
        );
        ValidateCsvUseCase useCase = useCase(parserReturning(data), exists(), config());

        CsvValidationResult result = useCase.execute(command(data));

        ValidationIssue structure = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.STRUCTURE)
                .findFirst()
                .orElseThrow();
        assertTrue(structure.message().contains("name"));
        assertTrue(structure.message().contains("id"));
        assertFalse(result.importAllowed());
    }

    @Test
    void givenEmptyFile_whenUpload_thenReportsEmptyAndDoesNotProceed() {
        CsvParserPort parser = content -> {
            throw new CsvParseException(
                    CsvParseException.ErrorCode.EMPTY_FILE,
                    "O arquivo CSV está vazio."
            );
        };
        CsvValidationResult result = useCase(parser, exists(), config())
                .execute(new ValidateCsvCommand("empty.csv", new byte[0]));

        assertTrue(result.issues().stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.EMPTY_FILE));
        assertFalse(result.importAllowed());
    }

    @Test
    void givenInvalidEncoding_whenUpload_thenSuggestsUtf8() {
        CsvParserPort parser = content -> {
            throw new CsvParseException(
                    CsvParseException.ErrorCode.INVALID_ENCODING,
                    "Encoding inválido. Salve o arquivo em UTF-8."
            );
        };
        CsvValidationResult result = useCase(parser, exists(), config())
                .execute(new ValidateCsvCommand("bad.csv", new byte[]{1, 2, 3}));

        assertTrue(result.issues().stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.INVALID_ENCODING));
        org.junit.jupiter.api.Assertions.assertTrue(
                result.suggestions().stream().anyMatch(s -> s.contains("UTF-8"))
        );
    }

    @Test
    void givenFileWithTwoExactDuplicateLines_thenIdentifiesBothOccurrences() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", "Maria"), List.of("1", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        ValidationIssue issue = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.DUPLICATE_EXACT)
                .findFirst()
                .orElseThrow();
        assertTrue(issue.relatedLines().containsAll(List.of(2, 3)));
    }

    @Test
    void givenFileWithoutExactDuplicateLines_thenNoExactDuplicateWarning() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", "Maria"), List.of("2", "João"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.issues().stream()
                .noneMatch(i -> i.type() == ValidationIssue.Type.DUPLICATE_EXACT));
    }

    @Test
    void givenDuplicateLinesAndTypeErrors_thenReportsDuplicateAndTypeSeparately() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("abc", "Maria"), List.of("abc", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.issues().stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.DUPLICATE_EXACT));
        assertTrue(result.issues().stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.TYPE));
    }

    @Test
    void givenBusinessKeyConfigured_whenTwoRecordsHaveSameKey_thenPartialDuplicateWarning() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", "Maria"), List.of("2", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        ValidationIssue issue = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.DUPLICATE_PARTIAL)
                .findFirst()
                .orElseThrow();
        assertTrue(issue.relatedLines().containsAll(List.of(2, 3)));
        assertTrue(issue.message().contains("name"));
    }

    @Test
    void givenFileWithoutPartialDuplicates_thenNoPartialDuplicateWarning() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", "Maria"), List.of("2", "João"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.issues().stream()
                .noneMatch(i -> i.type() == ValidationIssue.Type.DUPLICATE_PARTIAL));
    }

    @Test
    void givenRecordWithEmptyBusinessKey_thenNotDuplicateAndReportsMissingRequired() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", ""))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.issues().stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.REQUIRED_FIELD_MISSING));
        assertTrue(result.issues().stream()
                .noneMatch(i -> i.type() == ValidationIssue.Type.DUPLICATE_PARTIAL));
    }

    @Test
    void givenReferencedIdDoesNotExist_thenReferenceErrorWithLineAndColumn() {
        CsvData data = data(
                List.of("id", "name", "parent_id"),
                List.of(List.of("1", "Maria", "999"))
        );
        ReferenceLookupPort none = (type, value) -> false;
        CsvValidationResult result = useCase(parserReturning(data), none, config())
                .execute(command(data));

        ValidationIssue issue = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.REFERENCE)
                .findFirst()
                .orElseThrow();
        assertEquals(2, issue.lineNumber());
        assertEquals("parent_id", issue.columnName());
    }

    @Test
    void givenAllReferencedIdsExist_thenNoReferenceError() {
        CsvData data = data(
                List.of("id", "name", "parent_id"),
                List.of(List.of("1", "Maria", "10"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.issues().stream()
                .noneMatch(i -> i.type() == ValidationIssue.Type.REFERENCE));
    }

    @Test
    void givenRequiredReferenceEmpty_thenCriticalIntegrityError() {
        CsvImportConfig cfg = new CsvImportConfig(
                new CsvHeaderSchema(List.of(
                        CsvColumnSchema.number("id", true),
                        CsvColumnSchema.number("parent_id", false).withReferenceType("PARENT")
                )),
                List.of(new ReferenceRule("parent_id", "PARENT", true)),
                null
        );

        CsvData data = data(
                List.of("id", "parent_id"),
                List.of(List.of("1", ""))
        );
        ValidateCsvUseCase useCase = useCase(parserReturning(data), exists(), cfg);

        CsvValidationResult result = useCase.execute(command(data));

        ValidationIssue issue = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.REFERENCE)
                .findFirst()
                .orElseThrow();
        assertEquals(ValidationIssue.Severity.CRITICAL, issue.severity());
    }

    @Test
    void givenErrorsInMultipleRows_thenGroupedByLineAndColumn() {
        CsvData data = data(
                List.of("id", "name", "active"),
                List.of(
                        List.of("abc", "Maria", "true"),
                        List.of("2", "Maria", "talvez")
                )
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.issuesByLine(2).stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.TYPE && "id".equals(i.columnName())));
        assertTrue(result.issuesByLine(3).stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.TYPE && "active".equals(i.columnName())));
        assertTrue(result.issuesByColumn("id").stream()
                .anyMatch(i -> i.type() == ValidationIssue.Type.TYPE));
    }

    @Test
    void givenTypeError_whenViewError_thenShowsActionableDescriptionAndExample() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("abc", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        ValidationIssue issue = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.TYPE && "id".equals(i.columnName()))
                .findFirst()
                .orElseThrow();
        assertTrue(issue.suggestion() != null);
        assertTrue(issue.expectedValue() != null);
    }

    @Test
    void givenDuplicateError_whenViewError_thenIndicatesLinesAndKey() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", "Maria"), List.of("2", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        ValidationIssue issue = result.issues().stream()
                .filter(i -> i.type() == ValidationIssue.Type.DUPLICATE_PARTIAL)
                .findFirst()
                .orElseThrow();
        assertTrue(issue.relatedLines().containsAll(List.of(2, 3)));
        assertTrue(issue.message().contains("name"));
    }

    @Test
    void givenCompletedValidation_whenReportDisplayed_thenShowsTotals() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("abc", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        Map<ValidationIssue.Severity, Long> totals = result.countsBySeverity();
        assertTrue(totals.getOrDefault(ValidationIssue.Severity.CRITICAL, 0L) > 0);
    }

    @Test
    void givenReportWithSameErrorTypes_thenSuggestsCorrections() {
        CsvData data = data(
                List.of("id", "name", "parent_id"),
                List.of(List.of("abc", "Maria", "999"))
        );
        ReferenceLookupPort none = (type, value) -> false;
        CsvValidationResult result = useCase(parserReturning(data), none, config())
                .execute(command(data));

        assertFalse(result.suggestions().isEmpty());
        assertTrue(result.suggestions().stream()
                .anyMatch(s -> s.contains("valores")));
    }

    @Test
    void givenFileWithoutErrors_thenReportIndicatesReadyForImport() {
        CsvData data = data(
                List.of("id", "name"),
                List.of(List.of("1", "Maria"))
        );
        CsvValidationResult result = useCase(parserReturning(data), exists(), config())
                .execute(command(data));

        assertTrue(result.readyForImport());
        assertFalse(result.requiresConfirmation());
    }

    private ValidateCsvCommand command(CsvData data) {
        return new ValidateCsvCommand("test.csv", new byte[]{1});
    }

    private ValidateCsvUseCase useCase(CsvParserPort parser, ReferenceLookupPort lookup, CsvImportConfig cfg) {
        return new ValidateCsvUseCase(
                parser,
                new TypeValidator(),
                new DuplicateDetector(),
                new ReferenceIntegrityValidator(lookup),
                cfg
        );
    }

    private CsvParserPort parserReturning(CsvData data) {
        return content -> data;
    }

    private ReferenceLookupPort exists() {
        return (type, value) -> true;
    }

    private CsvImportConfig config() {
        CsvHeaderSchema schema = new CsvHeaderSchema(List.of(
                CsvColumnSchema.number("id", true),
                CsvColumnSchema.text("name", true),
                CsvColumnSchema.email("email", false),
                CsvColumnSchema.date("dt", false, "yyyy-MM-dd"),
                CsvColumnSchema.bool("active", false),
                CsvColumnSchema.number("parent_id", false).withReferenceType("PARENT")
        ));
        return new CsvImportConfig(
                schema,
                List.of(new ReferenceRule("parent_id", "PARENT", false)),
                new BusinessKeyRule(List.of("name"))
        );
    }

    private CsvData data(List<String> headers, List<List<String>> rows) {
        List<CsvRow> csvRows = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            int line = i + 2;
            List<Cell> cells = new ArrayList<>();
            for (int h = 0; h < headers.size(); h++) {
                String value = h < rows.get(i).size() ? rows.get(i).get(h) : "";
                cells.add(new Cell(headers.get(h), value, line));
            }
            csvRows.add(new CsvRow(line, cells));
        }
        return new CsvData(headers, csvRows);
    }
}