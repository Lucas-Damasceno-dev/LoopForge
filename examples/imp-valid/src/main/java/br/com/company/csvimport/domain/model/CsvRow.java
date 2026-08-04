package br.com.company.csvimport.domain.model;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Representa uma linha de dados de um arquivo CSV.
 */
public final class CsvRow {

    private final int lineNumber;
    private final List<Cell> cells;
    private final Map<String, Cell> cellsByName;

    /**
     * Cria uma linha de CSV.
     *
     * @param lineNumber número da linha original
     * @param cells      células na ordem das colunas
     */
    public CsvRow(int lineNumber, List<Cell> cells) {
        this.lineNumber = lineNumber;
        this.cells = List.copyOf(cells);
        Map<String, Cell> map = new LinkedHashMap<>();
        for (Cell cell : cells) {
            map.put(cell.columnName(), cell);
        }
        this.cellsByName = Map.copyOf(map);
    }

    public int lineNumber() {
        return lineNumber;
    }

    public List<Cell> cells() {
        return cells;
    }

    /**
     * Retorna o valor de uma coluna.
     *
     * @param columnName nome da coluna
     * @return valor, ou {@code null} se a coluna não existir na linha
     */
    public String value(String columnName) {
        Cell cell = cellsByName.get(columnName);
        return cell == null ? null : cell.value();
    }

    public boolean hasColumn(String columnName) {
        return cellsByName.containsKey(columnName);
    }

    /**
     * Chave canônica para detecção de duplicidade exata.
     *
     * @return string com todos os valores concatenados
     */
    public String exactKey() {
        return cells.stream()
                .map(Cell::value)
                .map(value -> value == null ? "" : value)
                .collect(Collectors.joining("\u0000"));
    }
}