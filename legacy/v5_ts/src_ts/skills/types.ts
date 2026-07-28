export interface Skill {
  name: string;
  description?: string;
  content: string;
  filePath: string;
}

export interface SkillLoadResult {
  loadedSkills: Skill[];
  missingSkills: string[];
}
