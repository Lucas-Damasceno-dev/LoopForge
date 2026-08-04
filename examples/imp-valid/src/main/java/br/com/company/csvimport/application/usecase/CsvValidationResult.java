package br.com.company.csvimport.application.usecase;

import br.com.company.csvimport.domain.model.ValidationIssue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Resultado completo da validação de um CSV.
 */
public final class CsvValidationResult {

    private final String fileName;
    private final int rowCount;
    private final List<ValidationIssue> issues;
    private final boolean importAllowed;
    private final boolean requiresConfirmation;
    private final boolean readyForImport;
    private final List<String> suggestions;

    private CsvValidationResult(Builder builder) {
        this.fileName = builder.fileName;
        this.rowCount = builder.rowCount;
        this.issues = builder.issues == null ? List.of() : List.copyOf(builder.issues);

        boolean computedImportAllowed = this.issues.stream()
                .noneMatch(issue -> issue.severity() == ValidationIssue.Severity.CRITICAL);
        this.importAllowed = builder.importAllowed != null ? builder.importAllowed : computedImportAllowed;

        boolean computedRequiresConfirmation = this.importAllowed && this.issues.stream()
                .anyMatch(issue -> issue.severity() == ValidationIssue.Severity.WARNING);
        this.requiresConfirmation = builder.requiresConfirmation != null
                ? builder.requiresConfirmation
                : computedRequiresConfirmation;

        this.readyForImport = builder.readyForImport != null
                ? builder.readyForImport
                : (this.importAllowed && !this.requiresConfirmation);

        this.suggestions = builder.suggestions != null
                ? List.copyOf(builder.suggestions)
                : buildSuggestions();
    }

    public static Builder builder() {
        return new Builder();
    }

    public static CsvValidationResult fatal(String fileName, ValidationIssue issue) {
        return builder().fileName(fileName).rowCount(0).issues(List.of(issue)).build();
    }

    public String fileName() {
        return fileName;
    }

    public int rowCount() {
        return rowCount;
    }

    public List<ValidationIssue> issues() {
        return issues;
    }

    public boolean importAllowed() {
        return importAllowed;
    }

    public boolean requiresConfirmation() {
        return requiresConfirmation;
    }

    public boolean readyForImport() {
        return readyForImport;
    }

    public int criticalCount() {
        return (int) issues.stream()
                .filter(issue -> issue.severity() == ValidationIssue.Severity.CRITICAL)
                .count();
    }

    public int warningCount() {
        return (int) issues.stream()
                .filter(issue -> issue.severity() == ValidationIssue.Severity.WARNING)
                .count();
    }

    public int infoCount() {
        return (int) issues.stream()
                .filter(issue -> issue.severity() == ValidationIssue.Severity.INFO)
                .count();
    }

    public Map<ValidationIssue.Severity, Long> countsBySeverity() {
        return issues.stream().collect(Collectors.groupingBy(
                ValidationIssue::severity,
                LinkedHashMap::new,
                Collectors.counting()
        ));
    }

    /**
     * Retorna problemas associados a uma linha.
     *
     * @param line número da linha
     * @return problemas cuja linha principal ou linhas relacionadas incluam o valor informado
     */
    public List<ValidationIssue> issuesByLine(int line) {
        return issues.stream()
                .filter(issue -> issue.lineNumber() == line || issue.relatedLines().contains(line))
                .toList();
    }

    /**
     * Retorna problemas associados a uma coluna.
     *
     * @param column nome da coluna
     * @return problemas cuja coluna seja igual ao valor informado
     */
    public List<ValidationIssue> issuesByColumn(String column) {
        return issues.stream()
                .filter(issue -> column.equals(issue.columnName()))
                .toList();
    }

    public List<String> suggestions() {
        return suggestions;
    }

    private List<String> buildSuggestions() {
        Set<String> result = new LinkedHashSet<>();

        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.TYPE)) {
            result.add("Revise os valores nas colunas com erro de tipo. Use o formato esperado indicado em cada mensagem.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.REFERENCE)) {
            result.add("Atualize os IDs referenciados ou cadastre os registros correspondentes antes de importar.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.REQUIRED_FIELD_MISSING)) {
            result.add("Preencha todos os campos obrigatórios indicados.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.DUPLICATE_EXACT)) {
            result.add("Remova as linhas duplicadas exatas antes de importar.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.DUPLICATE_PARTIAL)) {
            result.add("Revise as duplicatas parciais apontadas pela chave de negócio.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.STRUCTURE)) {
            result.add("Corrija o cabeçalho do arquivo usando os nomes esperados.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.EMPTY_FILE)) {
            result.add("Envie um arquivo contendo cabeçalho e ao menos uma linha de dados.");
        }
        if (issues.stream().anyMatch(issue -> issue.type() == ValidationIssue.Type.INVALID_ENCODING)) {
            result.add("Salve o arquivo como UTF-8.");
        }
        return new ArrayList<>(result);
    }

    public static final class Builder {
        private String fileName;
        private int rowCount;
        private List<ValidationIssue> issues;
        private Boolean importAllowed;
        private Boolean requiresConfirmation;
        private Boolean readyForImport;
        private List<String> suggestions;

        public Builder fileName(String fileName) {
            this.fileName = fileName;
            return this;
        }

        public Builder rowCount(int rowCount) {
            this.rowCount = rowCount;
            return this;
        }

        public Builder issues(List<ValidationIssue> issues) {
            this.issues = issues;
            return this;
        }

        public Builder importAllowed(Boolean importAllowed) {
            this.importAllowed = importAllowed;
            return this;
        }

        public Builder requiresConfirmation(Boolean requiresConfirmation) {
            this.requiresConfirmation = requiresConfirmation;
            return this;
        }

        public Builder readyForImport(Boolean readyForImport) {
            this.readyForImport = readyForImport;
            return this;
        }

        public Builder suggestions(List<String> suggestions) {
            this.suggestions = suggestions;
            return this;
        }

        public CsvValidationResult build() {
            return new CsvValidationResult(this);
        }
    }
}