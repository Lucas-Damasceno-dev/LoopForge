# Configuration

O LoopForge é configurado via arquivo `.loopforge.json`, `.loopforge.yml` ou `.loopforge.yaml` na raiz do projeto. O schema é validado com **Zod** em runtime.

---

## Schema Completo

```typescript
interface LoopForgeConfig {
  projectName: string;                  // Nome do projeto
  version?: string;                     // Versão do projeto
  harness: HarnessConfig;
  memory?: MemoryConfig;
  guardrails?: GuardrailsConfig;
  notifications?: NotificationConfig;
  llm?: LLMConfig;
}
```

---

## Campos e Sub-objetos

### `guardrails`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `maxConsecutiveFailures` | `number` | `3` | Falhas consecutivas antes do circuit breaker abrir |
| `maxTotalIterations` | `number` | `10` | Número máximo de iterações totais do loop |
| `maxBudgetUsd` | `number` | `5.0` | Orçamento total máximo em dólar |
| `maxCostPerIteration` | `number` | `2.0` | Teto financeiro máximo permitido para uma única iteração |
| `requireCleanGit` | `boolean` | `true` | Exige repositório limpo para iniciar |

---

### `notifications`

| Campo | Tipo | Descrição |
|---|---|---|
| `webhookUrl` | `string` | URL do Webhook (Slack, Discord, Teams) |
| `desktop.enabled` | `boolean` | Ativa/desativa notificações de desktop no sistema |
| `email.enabled` | `boolean` | Ativa/desativa envio de e-mails de alerta |
| `email.smtpHost` | `string` | Host do servidor SMTP |
| `email.smtpPort` | `number` | Porta SMTP (ex: 587 ou 465) |
| `email.to` | `string` | Endereço do destinatário do relatório |

**Exemplo:**
```json
"notifications": {
  "webhookUrl": "https://discord.com/api/webhooks/...",
  "desktop": { "enabled": true },
  "email": {
    "enabled": true,
    "smtpHost": "smtp.gmail.com",
    "smtpPort": 587,
    "to": "alerta@meudominio.com"
  }
}
```
