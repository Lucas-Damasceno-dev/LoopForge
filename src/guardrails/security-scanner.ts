import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface SecurityVulnerability {
  file: string;
  line: number;
  type: "hardcoded_secret" | "sql_injection" | "insecure_eval";
  snippet: string;
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
          if (/eval\(|new Function\(/i.test(line) && !file.includes("test")) {
            vulnerabilities.push({
              file: relativePath,
              line: idx + 1,
              type: "insecure_eval",
              snippet: line.trim(),
            });
          }
          // Precise regex for SQL template string interpolation or dynamic concatenation
          if (/`(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\$\{/i.test(line) || /"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?"\s*\+/i.test(line)) {
            vulnerabilities.push({
              file: relativePath,
              line: idx + 1,
              type: "sql_injection",
              snippet: line.trim(),
            });
          }
        });
      } catch (err) {
        // Skip unreadable binary files safely
      }
    }

    return vulnerabilities;
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
