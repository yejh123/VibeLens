import { useState } from "react";
import {
  AlertTriangle,
  Coins,
  Shield,
  X,
} from "lucide-react";
import {
  type OnboardingStep,
  ONBOARDING_STEPS,
  PRIVACY_POINTS,
  LLM_COST_POINTS,
  markOnboardingSeen,
} from "./onboarding-constants";

const GITHUB_URL = "https://github.com/yejh123/VibeLens";

interface OnboardingDialogProps {
  onClose: () => void;
}

export function OnboardingDialog({ onClose }: OnboardingDialogProps) {
  const [step, setStep] = useState<OnboardingStep>("privacy");

  const stepIndex = ONBOARDING_STEPS.indexOf(step);
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === ONBOARDING_STEPS.length - 1;

  const handleClose = () => {
    markOnboardingSeen();
    onClose();
  };

  const handleNext = () => {
    if (isLast) {
      handleClose();
    } else {
      setStep(ONBOARDING_STEPS[stepIndex + 1]);
    }
  };

  const handleBack = () => {
    if (!isFirst) {
      setStep(ONBOARDING_STEPS[stepIndex - 1]);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div className="relative bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              {ONBOARDING_STEPS.map((s, i) => (
                <div
                  key={s}
                  className={`w-2 h-2 rounded-full transition ${
                    i === stepIndex
                      ? "bg-cyan-400"
                      : i < stepIndex
                        ? "bg-cyan-600/50"
                        : "bg-zinc-600"
                  }`}
                />
              ))}
            </div>
            <h2 className="text-base font-semibold text-white">Welcome to VibeLens</h2>
          </div>
          <button
            onClick={handleClose}
            className="text-zinc-500 hover:text-zinc-300 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5">
          {step === "privacy" && <PrivacyStep />}
          {step === "llm-costs" && <LlmCostStep />}
        </div>

        {/* Footer */}
        <div className="flex justify-between px-5 py-3 border-t border-zinc-800">
          <div>
            {!isFirst && (
              <button
                onClick={handleBack}
                className="px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 border border-zinc-700 hover:border-zinc-600 rounded transition"
              >
                Back
              </button>
            )}
          </div>
          <button
            onClick={handleNext}
            className="px-4 py-1.5 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-500 rounded transition"
          >
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PrivacyStep() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Shield className="w-5 h-5 text-cyan-400" />
        <span className="text-sm font-semibold text-white">Your Data, Your Machine</span>
      </div>
      <div className="space-y-2">
        {PRIVACY_POINTS.map((point) => (
          <div
            key={point.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-3"
          >
            <p className="text-sm font-medium text-white">{point.label}</p>
            <p className="text-sm text-zinc-300 mt-0.5">{point.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function LlmCostStep() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Coins className="w-5 h-5 text-amber-400" />
        <span className="text-sm font-semibold text-white">LLM-Powered Analysis</span>
      </div>
      <div className="space-y-2">
        {LLM_COST_POINTS.map((point) => (
          <div
            key={point.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-3"
          >
            <p className="text-sm font-medium text-white">{point.label}</p>
            <p className="text-sm text-zinc-300 mt-0.5">{point.detail}</p>
          </div>
        ))}
      </div>
      <div className="flex items-start gap-2 p-3 bg-amber-900/20 border border-amber-700/30 rounded-lg">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <p className="text-sm text-amber-200">
          You will never be charged without explicitly clicking Analyze. All costs go
          directly to your chosen LLM provider.
        </p>
      </div>
      <p className="text-sm text-zinc-400 text-center">
        Questions or feedback?{" "}
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-400 hover:text-cyan-300 underline"
        >
          Visit us on GitHub
        </a>
      </p>
    </div>
  );
}
