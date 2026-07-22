import * as crypto from "node:crypto";

export interface LoopLockCheckResult {
  isLocked: boolean;
  warningPrompt?: string;
}

export class CodeLoopLockDetector {
  private previousHashes: string[] = [];

  public registerResponse(content: string): LoopLockCheckResult {
    const hash = crypto.createHash("sha256").update(content.trim()).digest("hex");

    if (this.previousHashes.includes(hash)) {
      return {
        isLocked: true,
        warningPrompt:
          "⚠️ ATENÇÃO CRÍTICA: Você gerou uma resposta idêntica a uma iteração anterior! Mude sua estratégia de implementação imediatamente para evitar um loop infinito.",
      };
    }

    this.previousHashes.push(hash);
    if (this.previousHashes.length > 5) {
      this.previousHashes.shift();
    }

    return { isLocked: false };
  }

  public reset(): void {
    this.previousHashes = [];
  }
}
