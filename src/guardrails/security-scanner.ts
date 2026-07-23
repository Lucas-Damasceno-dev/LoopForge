import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface SecurityVulnerability {
  file: string;
  line: number;
  type: "hardcoded_secret" | "sql_injection" | "insecure_eval";
  snippet: string;
}

export interface FixResult {
  file: string;
  line: number;
  type: string;
  fixApplied: string;
}

export class SecurityScanner {
  public async scanDirectory(dir: string = "."): Promise<SecurityVulnerability[]> {
    const resolvedDir = path.resolve(dir);
    const files = await this.getFiles(resolvedDir);
    const vulnerabilities: SecurityVulnerability[] = [];

    for (const file of files) {
      try {
        const content = await fs.readFile(file, "utf-8");
        const relativePath = path.relative(resolvedDir, file);
        const lines = content.split("\n");

        lines.forEach((line, idx) => {
          if (/(sk-[A-Za-z0-9]{32}|AKIA[0-9A-Z]{16}|bearer\s+[A-Za-z0-9\-\._~\+\/]+=*)/i.test(line)) {
            vulnerabilities.push({
              file: relativePath,
              line: idx + 1,
              type: "hardcoded_secret",
              snippet: line.trim(),
            });
          }
          if (/eval\(|new Function\(/i.test(line) && !path.basename(file).includes("test")) {
            vulnerabilities.push({
              file: relativePath,
              line: idx + 1,
              type: "insecure_eval",
              snippet: line.trim(),
            });
          }
          if (/`(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\$\{/i.test(line) || /"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?"\s*\+/i.test(line)) {
            vulnerabilities.push({
              file: relativePath,
              line: idx + 1,
              type: "sql_injection",
              snippet: line.trim(),
            });
          }
        });
      } catch (err) {}
    }

    return vulnerabilities;
  }

  public async autoFixVulnerabilities(dir: string = ".", vulnerabilities?: SecurityVulnerability[]): Promise<{ fixedCount: number; fixes: FixResult[] }> {
    const resolvedDir = path.resolve(dir);
    const targetVulns = vulnerabilities || (await this.scanDirectory(resolvedDir));
    const fixes: FixResult[] = [];
    const envPath = path.join(resolvedDir, ".env");

    let envContent = "";
    try {
      envContent = await fs.readFile(envPath, "utf-8");
    } catch {}

    const envVarsToAdd: string[] = [];
    let secretCounter = 1;

    const fileGroups = new Map<string, SecurityVulnerability[]>();
    for (const v of targetVulns) {
      if (!fileGroups.has(v.file)) fileGroups.set(v.file, []);
      fileGroups.get(v.file)!.push(v);
    }

    for (const [relFile, vulns] of fileGroups.entries()) {
      const fullPath = path.join(resolvedDir, relFile);
      try {
        const raw = await fs.readFile(fullPath, "utf-8");
        const lines = raw.split("\n");

        for (const v of vulns) {
          const lineIdx = v.line - 1;
          if (lineIdx < 0 || lineIdx >= lines.length) continue;
          const origLine = lines[lineIdx];

          if (v.type === "hardcoded_secret") {
            const match = origLine.match(/(sk-[A-Za-z0-9]{32}|AKIA[0-9A-Z]{16}|bearer\s+[A-Za-z0-9\-\._~\+\/]+=*)/i);
            if (match) {
              const secretVal = match[1];
              const varName = `LOOPFORGE_SECRET_VAR_${secretCounter++}`;
              envVarsToAdd.push(`${varName}=${secretVal}`);
              
              // Handle quotes surrounding secret literal
              lines[lineIdx] = origLine.replace(new RegExp(`(["'])${secretVal.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&")}\\1`), `process.env.${varName}`)
                                      .replace(secretVal, `process.env.${varName}`);
              fixes.push({
                file: relFile,
                line: v.line,
                type: v.type,
                fixApplied: `Secret movido para .env como ${varName} e substituído por process.env.${varName}`,
              });
            }
          } else if (v.type === "insecure_eval") {
            lines[lineIdx] = origLine.replace(/eval\((.*?)\)/, "JSON.parse($1)").replace(/new Function\((.*?)\)/, "JSON.parse($1)");
            fixes.push({
              file: relFile,
              line: v.line,
              type: v.type,
              fixApplied: `eval()/new Function() substituído por versão segura JSON.parse()`,
            });
          }
        }

        await fs.writeFile(fullPath, lines.join("\n"), "utf-8");
      } catch {}
    }

    if (envVarsToAdd.length > 0) {
      const newEnvContent = envContent ? `${envContent.trim()}\n${envVarsToAdd.join("\n")}\n` : `${envVarsToAdd.join("\n")}\n`;
      await fs.writeFile(envPath, newEnvContent, "utf-8");
    }

    return { fixedCount: fixes.length, fixes };
  }

  private async getFiles(dir: string): Promise<string[]> {
    const results: string[] = [];
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "dist") continue;
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results.push(...(await this.getFiles(fullPath)));
      } else if (/\.(ts|js|py|go)$/.test(entry.name)) {
        results.push(fullPath);
      }
    }
    return results;
  }
}
