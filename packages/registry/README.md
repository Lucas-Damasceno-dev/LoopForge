# 🔗 Agentic Interface Registry

Registro central de contratos de interface pública entre agentes de IA para evitar quebras silenciosas no codebase.

## Recursos
- **Interface Tracking**: Extração de funções, tipos e assinaturas exportadas
- **Consumer Detection**: Identificação de arquivos/linhas que consomem cada interface
- **Breaking Change Detection**: Detecção automatizada de incompatibilidades em assinaturas
- **Notificações**: Terminal (stdout), Slack webhook e arquivos JSON
- **CLI & REST API**: Comandos `track`, `check`, `diff`, `watch` e `serve`
