export interface TourStep {
  id: string;
  target: string;
  title: string;
  content: string;
  placement: "right" | "bottom" | "left";
  icon: string;
  mode?: "demo";
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    target: "sidebar-header",
    title: "Welcome to VibeLens",
    content:
      "VibeLens helps you understand how your AI coding agents work. Browse past conversations from Claude Code, Codex, Gemini, and more.",
    placement: "right",
    icon: "eye",
  },
  {
    id: "sessions",
    target: "session-list",
    title: "Your Sessions",
    content:
      "All your agent sessions appear here. Search, filter by agent type, or group by project to find what you need.",
    placement: "right",
    icon: "list",
  },
  {
    id: "conversation",
    target: "conversation-tab",
    title: "Conversation",
    content:
      "Open any session to read it turn by turn. See what was asked, how the agent responded, and what tools it used.",
    placement: "bottom",
    icon: "message",
  },
  {
    id: "view-modes",
    target: "view-modes",
    title: "Three View Modes",
    content:
      "Concise shows just the key messages. Detail shows everything. Workflow maps out each phase of work visually.",
    placement: "bottom",
    icon: "layout",
  },
  {
    id: "dashboard",
    target: "dashboard-tab",
    title: "Dashboard",
    content:
      "See the big picture: activity over time, token usage, most-used tools, and cost breakdown across all sessions.",
    placement: "bottom",
    icon: "bar-chart",
  },
  {
    id: "personalization",
    target: "personalization-tab",
    title: "Personalization",
    content:
      "Create reusable skills from your coding patterns. These teach your agent how you prefer to work, so it gets better over time.",
    placement: "bottom",
    icon: "wand",
  },
  {
    id: "productivity-tips",
    target: "productivity-tips-tab",
    title: "Productivity Tips",
    content:
      "Find wasted effort and repeated mistakes in your sessions. Get practical tips to work more effectively with your agent.",
    placement: "bottom",
    icon: "lightbulb",
  },
  {
    id: "upload",
    target: "upload-button",
    title: "Upload Sessions",
    content:
      "Add your own sessions here. Pick your agent type, run a quick export command, and drag in the file.",
    placement: "right",
    icon: "upload",
    mode: "demo",
  },
];

export const TOUR_STORAGE_KEY = "vibelens-onboarding-seen";

export function getStepsForMode(appMode: string): TourStep[] {
  return TOUR_STEPS.filter((step) => !step.mode || step.mode === appMode);
}

export function hasSeenTour(): boolean {
  return localStorage.getItem(TOUR_STORAGE_KEY) === "true";
}

export function markTourSeen(): void {
  localStorage.setItem(TOUR_STORAGE_KEY, "true");
}
