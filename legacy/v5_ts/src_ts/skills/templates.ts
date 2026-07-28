export interface PresetTemplate {
  name: string;
  description: string;
  skills: Record<string, string>;
}

export const PRESET_TEMPLATES: Record<string, PresetTemplate> = {
  "node-typescript": {
    name: "Node.js TypeScript",
    description: "Template para projetos TypeScript com Vitest/Jest, ESLint/Biome e regras de arquitetura limpa.",
    skills: {
      "clean-code.md": `# Diretrizes de Clean Code & TypeScript
- Mantenha funções pequenas e fortemente tipadas.
- Evite qualquer uso de 'any' implícito ou explícito.
- Garanta tratamento de erros assíncronos com try/catch ou Promises seguras.
- Sempre adicione testes unitários para novas funcionalidades.`,
      "testing-rules.md": `# Regras de Teste (Vitest / Jest)
- Testes devem ser determinísticos e independentes.
- Use mocks apenas para limites do sistema (I/O, rede).
- Garanta 100% de cobertura nos métodos exportados.`,
    },
  },

  "python-pytest": {
    name: "Python Pytest",
    description: "Template para projetos Python com Pytest, MyPy e Flake8.",
    skills: {
      "python-quality.md": `# Diretrizes Python & Type Hints
- Use Type Hints (PEP 484) em todas as assinaturas de funções.
- Siga estritamente o PEP 8 (lint via Flake8/Ruff).
- Garanta que todas as exceções sejam tratadas explicitamente.`,
    },
  },

  "rust-cargo": {
    name: "Rust Cargo",
    description: "Template para projetos Rust com Cargo Test, Clippy e rustfmt.",
    skills: {
      "rust-guidelines.md": `# Diretrizes Rust & Memory Safety
- Garanta zero warnings no 'cargo clippy'.
- Mantenha funções focadas e trate Result/Option sem unwrap em produção.
- Escreva testes unitários no próprio módulo.`,
    },
  },
};
