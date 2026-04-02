/** Color classes for skill source badges (agent interfaces). */
export const SOURCE_COLORS: Record<string, string> = {
  claude_code: "bg-sky-900/30 text-sky-400 border-sky-700/30",
  codex: "bg-emerald-900/30 text-emerald-400 border-emerald-700/30",
  central: "bg-teal-900/30 text-teal-400 border-teal-700/30",
  gemini: "bg-amber-900/30 text-amber-400 border-amber-700/30",
};

/** Human-readable labels for agent interface source types. */
export const SOURCE_LABELS: Record<string, string> = {
  claude_code: "Claude Code",
  codex: "Codex",
  central: "Central",
  gemini: "Gemini",
};

/** Tooltip descriptions for agent interface source types. */
export const SOURCE_DESCRIPTIONS: Record<string, string> = {
  claude_code: "Skill is installed in ~/.claude/skills/ for Claude Code CLI",
  codex: "Skill is installed in ~/.codex/skills/ for OpenAI Codex CLI",
  central: "Managed copy in ~/.vibelens/skills/ central repository",
  gemini: "Skill is installed for Google Gemini CLI",
};

/** Tooltip descriptions for common skill tags. */
export const TAG_DESCRIPTIONS: Record<string, string> = {
  "agent-skills": "Official Anthropic skill from the skills hub registry",
  development: "Tools and workflows for software development",
  "ai-assistant": "AI-powered assistant capabilities and automation",
  automation: "Automates repetitive tasks and workflows",
  testing: "Test writing, running, and debugging utilities",
  documentation: "Documentation generation and maintenance",
  refactoring: "Code refactoring and restructuring patterns",
  debugging: "Systematic debugging and error resolution",
  deployment: "Build, deploy, and CI/CD pipeline management",
  security: "Security scanning, auditing, and best practices",
  database: "Database queries, migrations, and schema management",
  frontend: "Frontend development, UI components, and styling",
  backend: "Backend services, APIs, and server-side logic",
  devops: "Infrastructure, monitoring, and operations",
};

/** Display labels for skill subdirectories. */
export const SUBDIR_LABELS: Record<string, string> = {
  scripts: "scripts/",
  references: "references/",
  agents: "agents/",
  assets: "assets/",
};

/** Tooltip descriptions for skill subdirectories. */
export const SUBDIR_DESCRIPTIONS: Record<string, string> = {
  scripts: "Executable scripts bundled with the skill",
  references: "Reference documents and examples",
  agents: "Sub-agent definitions for complex workflows",
  assets: "Static assets like templates and configs",
};

/** Color classes for featured skill categories. */
export const CATEGORY_COLORS: Record<string, string> = {
  "ai-assistant": "bg-indigo-900/30 text-indigo-400 border-indigo-700/30",
  development: "bg-teal-900/30 text-teal-400 border-teal-700/30",
};

/** Human-readable labels for featured skill categories. */
export const CATEGORY_LABELS: Record<string, string> = {
  "ai-assistant": "AI Assistant",
  development: "Development",
};

/** Human-readable labels for skill edit kinds. */
export const EDIT_KIND_LABELS: Record<string, string> = {
  add_instruction: "Add",
  remove_instruction: "Remove",
  replace_instruction: "Replace",
  update_description: "Update",
  add_tool: "Add Tool",
  remove_tool: "Remove Tool",
};

/** Badge color classes for skill edit kinds. */
export const EDIT_KIND_STYLES: Record<string, string> = {
  add_instruction: "bg-emerald-900/30 text-emerald-400 border border-emerald-700/20",
  remove_instruction: "bg-red-900/30 text-red-400 border border-red-700/20",
  replace_instruction: "bg-sky-900/30 text-sky-400 border border-sky-700/20",
  update_description: "bg-amber-900/30 text-amber-400 border border-amber-700/20",
  add_tool: "bg-teal-900/30 text-teal-400 border border-teal-700/20",
  remove_tool: "bg-rose-900/30 text-rose-400 border border-rose-700/20",
};

/** Tooltip descriptions for skill edit kinds. */
export const EDIT_KIND_DESCRIPTIONS: Record<string, string> = {
  add_instruction: "Add a new step or instruction to the skill body",
  remove_instruction: "Remove an outdated or counterproductive instruction",
  replace_instruction: "Replace an existing instruction with an improved version",
  update_description: "Change the skill's trigger description for better activation",
  add_tool: "Add a tool to the skill's allowed tools list",
  remove_tool: "Remove an unnecessary tool from the allowed tools list",
};

/** Badge color classes for conflict types. */
export const CONFLICT_TYPE_STYLES: Record<string, string> = {
  skipped_step: "bg-orange-900/30 text-orange-400 border border-orange-700/20",
  added_step: "bg-blue-900/30 text-blue-400 border border-blue-700/20",
  wrong_tool: "bg-rose-900/30 text-rose-400 border border-rose-700/20",
  bad_trigger: "bg-purple-900/30 text-purple-400 border border-purple-700/20",
  outdated_instruction: "bg-amber-900/30 text-amber-400 border border-amber-700/20",
};

/** Human-readable labels for conflict types. */
export const CONFLICT_TYPE_LABELS: Record<string, string> = {
  skipped_step: "Skipped Step",
  added_step: "Added Step",
  wrong_tool: "Wrong Tool",
  bad_trigger: "Bad Trigger",
  outdated_instruction: "Outdated",
};

/** Tooltip descriptions for conflict types. */
export const CONFLICT_TYPE_DESCRIPTIONS: Record<string, string> = {
  skipped_step: "The agent skipped a step the skill prescribes",
  added_step: "The agent added a step not covered by the skill",
  wrong_tool: "The agent chose a different tool than the skill recommends",
  bad_trigger: "The skill's trigger description failed to activate when expected",
  outdated_instruction: "An instruction no longer matches how the agent behaves",
};
