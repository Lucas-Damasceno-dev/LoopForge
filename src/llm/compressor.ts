export function compressPromptContext(fullContext: string, maxCharLength: number = 8000): { compressedContext: string; wasCompressed: boolean } {
  if (fullContext.length <= maxCharLength) {
    return { compressedContext: fullContext, wasCompressed: false };
  }

  const sections = fullContext.split("\n\n");
  const essentialSections: string[] = [];

  for (const sec of sections) {
    if (sec.includes("Lições Aprendidas") || sec.includes("Handoff") || sec.includes("LoopForge Iteração")) {
      essentialSections.push(sec);
    } else {
      // Sumarizar seções longas
      essentialSections.push(sec.slice(0, 300) + "\n... [Seção sumarizada por otimização de contexto]");
    }
  }

  const compressedContext = essentialSections.join("\n\n");
  return {
    compressedContext: compressedContext.slice(0, maxCharLength),
    wasCompressed: true,
  };
}
