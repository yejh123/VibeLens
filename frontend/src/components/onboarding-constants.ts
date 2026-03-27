export const ONBOARDING_STORAGE_KEY = "vibelens-onboarding-seen";

export type OnboardingStep = "privacy" | "llm-costs";

export const ONBOARDING_STEPS: OnboardingStep[] = ["privacy", "llm-costs"];

export const PRIVACY_POINTS = [
  {
    label: "Local reads only",
    detail: "VibeLens reads conversation history from your local disk. Nothing is uploaded unless you explicitly use Donate.",
  },
  {
    label: "No telemetry",
    detail: "No crash reports, no behavioral tracking, no analytics pings. Zero network calls on startup.",
  },
  {
    label: "You control LLM calls",
    detail: "Friction and Skill Analysis send data to an LLM only when you click Analyze, with your own API key.",
  },
];

export const LLM_COST_POINTS = [
  {
    label: "Bring your own key",
    detail: "API key is required for LLM-powered features.",
  },
  {
    label: "We don't see your key",
    detail: "Your API key is stored locally on your machine.",
  },
  {
    label: "Free tabs",
    detail: "Conversation and Dashboard tabs are entirely free. No API calls, pure local computation.",
  },
];

export function hasSeenOnboarding(): boolean {
  return localStorage.getItem(ONBOARDING_STORAGE_KEY) === "true";
}

export function markOnboardingSeen(): void {
  localStorage.setItem(ONBOARDING_STORAGE_KEY, "true");
}
