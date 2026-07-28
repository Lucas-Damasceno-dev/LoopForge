export function compressPromptContext(fullContext: string, maxCharLength: number = 8000): { compressedContext: string; wasCompressed: boolean } {
  if (fullContext.length <= maxCharLength) {
    return { compressedContext: fullContext, wasCompressed: false };
  }

  const sections = fullContext.split("\n\n");
  const essentialSections: string[] = [];

  const keyPattern = /(Lições Aprendidas|Lessons Learned|Handoff|LoopForge Iter|LoopForge Iteration)/i;

  for (const sec of sections) {
    if (keyPattern.test(sec)) {
      essentialSections.push(sec);
    } else {
      // Sumarizar seções longas de maneira agnóstica de idioma
      essentialSections.push(sec.slice(0, 300) + "\n... [Seção sumarizada por otimização de contexto / Context summarized]");
    }
  }

  const compressedContext = essentialSections.join("\n\n");
  return {
    compressedContext: compressedContext.slice(0, maxCharLength),
    wasCompressed: true,
  };
}
