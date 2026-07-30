# 🧬 Codebase Genome

Perfil estrutural e semântico multidimensional de qualquer codebase para consumo por agentes de IA.

## Recursos
- **AST Scanner**: Parsing via Tree-sitter para Python e TypeScript
- **Symbol Resolvers**: Mapeamento e resolução semântica de imports, interfaces e tipos
- **Dependency Graph & Bus Factor**: Grafos de acoplamento com NetworkX e identificação de módulos de alto risco
- **Architecture & Rules**: Validação de camadas e limites declarados em `.genomerc`
- **Output para LLMs**: Dump otimizado em Markdown, Summary e JSON
- **Incremental Cache**: Cache baseado em SQLite e diff do Git
