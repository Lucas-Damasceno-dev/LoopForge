package br.com.company.csvimport.adapter.web;

import br.com.company.csvimport.application.usecase.CsvValidationResult;
import br.com.company.csvimport.application.usecase.ImportRecordsUseCase;
import br.com.company.csvimport.application.usecase.ValidateCsvCommand;
import br.com.company.csvimport.application.usecase.ValidateCsvUseCase;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;

/**
 * Controller HTTP para upload e validação de arquivos CSV.
 */
@RestController
@RequestMapping("/api/csv")
public class CsvImportController {

    private final ValidateCsvUseCase validateCsvUseCase;
    private final ImportRecordsUseCase importRecordsUseCase;

    public CsvImportController(
            ValidateCsvUseCase validateCsvUseCase,
            ImportRecordsUseCase importRecordsUseCase
    ) {
        this.validateCsvUseCase = validateCsvUseCase;
        this.importRecordsUseCase = importRecordsUseCase;
    }

    /**
     * Valida um arquivo CSV enviado como multipart.
     *
     * @param file arquivo CSV
     * @return resultado da validação
     */
    @PostMapping("/validate")
    public CsvValidationResult validate(@RequestParam("file") MultipartFile file) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "O arquivo CSV está vazio.");
        }
        return validateCsvUseCase.execute(
                new ValidateCsvCommand(file.getOriginalFilename(), file.getBytes())
        );
    }

    /**
     * Importa um CSV após validação.
     *
     * @param file         arquivo CSV
     * @param confirmation confirmação explícita para importação com avisos
     * @return status HTTP
     */
    @PostMapping("/import")
    public ResponseEntity<Void> importCsv(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "confirmation", defaultValue = "false") boolean confirmation
    ) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "O arquivo CSV está vazio.");
        }
        CsvValidationResult result = validateCsvUseCase.execute(
                new ValidateCsvCommand(file.getOriginalFilename(), file.getBytes())
        );
        importRecordsUseCase.execute(result, file.getOriginalFilename(), confirmation);
        return ResponseEntity.ok().build();
    }
}