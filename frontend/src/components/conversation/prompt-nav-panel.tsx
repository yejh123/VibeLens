import { useState } from "react";
import { Bot, MessageSquare, ScrollText, User } from "lucide-react";
import { extractMessageText, extractUserText, truncate } from "../../utils";
import { ResizeHandle } from "../resize-handle";
import type { Step, Trajectory } from "../../types";
import type { FlowPhaseGroup, FlowSection } from "./flow-layout";
import {
  TOGGLE_CONTAINER, TOGGLE_BUTTON_BASE, TOGGLE_ACTIVE, TOGGLE_INACTIVE,
  PHASE_STYLE, CATEGORY_LABELS, SESSION_ID_MEDIUM, PREVIEW_MEDIUM, PREVIEW_LONG,
} from "../../styles";

const MIN_PROMPTS_FOR_NAV = 1;

type NavMode = "prompts" | "sub-agents";

interface PromptEntry {
  turnNumber: number;
  stepId: string;
  preview: string;
  isPlan: boolean;
}

interface PromptNavPanelProps {
  steps: Step[];
  subAgents: Trajectory[];
  activeStepId: string | null;
  onNavigate: (stepId: string) => void;
  width: number;
  onResize: (delta: number) => void;
  viewMode: "timeline" | "concise" | "flow";
  flowPhases?: FlowPhaseGroup[];
  flowSections?: FlowSection[];
  activePhaseIdx?: number | null;
  onPhaseNavigate?: (phaseIdx: number) => void;
}

function buildPromptEntries(steps: Step[]): PromptEntry[] {
  const entries: PromptEntry[] = [];
  let turnNumber = 0;
  let planNumber = 0;

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (step.source !== "user") continue;
    if (step.extra?.is_skill_output) continue;

    if (step.extra?.is_auto_prompt) {
      const text = extractMessageText(step.message);
      if (!text) continue;
      planNumber++;
      entries.push({
        turnNumber: planNumber,
        stepId: step.step_id,
        preview: truncate(text.replace(/\n/g, " "), PREVIEW_LONG),
        isPlan: true,
      });
      continue;
    }

    const text = extractUserText(step);
    if (!text) continue;
    turnNumber++;
    entries.push({
      turnNumber,
      stepId: step.step_id,
      preview: truncate(text.replace(/\n/g, " "), PREVIEW_LONG),
      isPlan: false,
    });
  }

  return entries;
}

export function PromptNavPanel({
  steps,
  subAgents,
  activeStepId,
  onNavigate,
  width,
  onResize,
  viewMode,
  flowPhases,
  flowSections,
  activePhaseIdx,
  onPhaseNavigate,
}: PromptNavPanelProps) {
  const entries = buildPromptEntries(steps);
  const hasPrompts = entries.length >= MIN_PROMPTS_FOR_NAV;
  const hasSubAgents = subAgents.length > 0;
  const hasFlowPhases = viewMode === "flow" && flowPhases && flowPhases.length > 0;

  const [navMode, setNavMode] = useState<NavMode>("prompts");

  if (!hasPrompts && !hasSubAgents && !hasFlowPhases) return null;

  const handleSubAgentNavigate = (sessionId: string) => {
    const el = document.getElementById(`subagent-${sessionId}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Flow mode: interleaved user prompts + phases
  const hasFlowSections = viewMode === "flow" && flowSections && flowSections.length > 0;
  if (hasFlowPhases || hasFlowSections) {
    const sections = flowSections ?? [];
    let phaseIdx = 0;

    return (
      <div
        style={{ width }}
        className="hidden xl:flex relative shrink-0 h-full flex-col border-l border-zinc-800 bg-zinc-900/50"
      >
        <ResizeHandle side="right" onResize={onResize} />
        <div className="flex-1 overflow-y-auto px-3 py-3">
          <div className="space-y-1">
            {sections.map((section, i) => {
              if (section.type === "anchor") {
                const anchor = section.data;
                const isAuto = anchor.isAutoPrompt;
                const isActive = anchor.id === activeStepId;
                const activeClass = isAuto
                  ? "bg-amber-500/15 border border-amber-500/30"
                  : "bg-emerald-500/15 border border-emerald-500/30";
                const idleClass = isAuto
                  ? "bg-amber-950/20 hover:bg-amber-900/20 border border-amber-500/10 hover:border-amber-500/20"
                  : "bg-emerald-950/20 hover:bg-emerald-900/20 border border-emerald-500/10 hover:border-emerald-500/20";
                const iconColor = isAuto
                  ? (isActive ? "text-amber-400" : "text-amber-400/60")
                  : (isActive ? "text-emerald-400" : "text-emerald-400/60");
                const labelColor = isAuto
                  ? (isActive ? "text-amber-300" : "text-amber-400/70 group-hover:text-amber-300")
                  : (isActive ? "text-emerald-300" : "text-emerald-400/70 group-hover:text-emerald-300");
                const previewColor = isAuto
                  ? (isActive ? "text-amber-200/70" : "text-zinc-500 group-hover:text-zinc-400")
                  : (isActive ? "text-emerald-200/80" : "text-zinc-400 group-hover:text-zinc-300");

                return (
                  <button
                    key={`anchor-${anchor.id}`}
                    onClick={() => onNavigate(anchor.id)}
                    className={`w-full text-left px-2.5 py-2 rounded-md transition-colors text-sm group ${
                      isActive ? activeClass : idleClass
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <User className={`w-3.5 h-3.5 ${iconColor}`} />
                      <span className={`font-mono font-semibold text-xs ${labelColor}`}>
                        Prompt #{anchor.promptIndex}
                      </span>
                      {isAuto && (
                        <span className="text-[9px] uppercase tracking-wider text-amber-500/50 font-semibold">
                          auto
                        </span>
                      )}
                    </div>
                    <p className={`line-clamp-2 leading-snug pl-5 ${previewColor}`}>
                      {truncate(anchor.label, PREVIEW_LONG)}
                    </p>
                  </button>
                );
              }

              // Phase section
              const phase = section.data;
              const currentPhaseIdx = phaseIdx++;
              const isActive = activePhaseIdx === currentPhaseIdx;
              const style = PHASE_STYLE[phase.phase] || PHASE_STYLE.mixed;
              const catLabel = CATEGORY_LABELS[phase.dominantCategory] || phase.dominantCategory;
              return (
                <button
                  key={`phase-${i}`}
                  onClick={() => onPhaseNavigate?.(currentPhaseIdx)}
                  className={`w-full text-left px-2 py-2 rounded-md transition-colors text-sm group ${
                    isActive
                      ? "bg-cyan-500/15 border border-cyan-500/30"
                      : "hover:bg-zinc-800/60 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                    <span
                      className={`text-[11px] font-bold uppercase tracking-wider ${
                        isActive ? "text-cyan-300" : style.label
                      }`}
                    >
                      {phase.phase}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-zinc-400 pl-4">
                    <span>{phase.cards.length} step{phase.cards.length !== 1 ? "s" : ""}</span>
                    <span className="text-zinc-600">·</span>
                    <span>{phase.toolCount} tool{phase.toolCount !== 1 ? "s" : ""}</span>
                    {phase.toolCount > 0 && (
                      <>
                        <span className="text-zinc-600">·</span>
                        <span className="text-zinc-500">{catLabel}</span>
                      </>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{ width }}
      className="hidden xl:flex relative shrink-0 h-full flex-col border-l border-zinc-800 bg-zinc-900/50"
    >
      <ResizeHandle side="right" onResize={onResize} />

      {/* Mode Toggle */}
      {hasPrompts && hasSubAgents && (
        <div className="shrink-0 px-3 pt-3 pb-2">
          <div className={TOGGLE_CONTAINER}>
            <button
              onClick={() => setNavMode("prompts")}
              className={`${TOGGLE_BUTTON_BASE} ${
                navMode === "prompts" ? TOGGLE_ACTIVE : TOGGLE_INACTIVE
              }`}
            >
              <MessageSquare className="w-3 h-3" />
              Prompts
            </button>
            <button
              onClick={() => setNavMode("sub-agents")}
              className={`${TOGGLE_BUTTON_BASE} ${
                navMode === "sub-agents" ? TOGGLE_ACTIVE : TOGGLE_INACTIVE
              }`}
            >
              <Bot className="w-3 h-3" />
              Agents
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {/* Prompts view (default, or only view when no sub-agents) */}
        {(navMode === "prompts" || !hasSubAgents) && hasPrompts && (
          <div>
            {!hasSubAgents && (
              <div className="flex items-center gap-1.5 text-sm text-zinc-300 mb-3">
                <MessageSquare className="w-3.5 h-3.5" />
                <span className="font-medium">Prompts</span>
                <span className="text-zinc-500">({entries.length})</span>
              </div>
            )}
            <div className="space-y-1">
              {entries.map((entry) => {
                const isActive = entry.stepId === activeStepId;
                if (entry.isPlan) {
                  return (
                    <button
                      key={entry.stepId}
                      onClick={() => onNavigate(entry.stepId)}
                      className={`w-full text-left px-2 py-1.5 rounded-md transition-colors text-sm group ${
                        isActive
                          ? "bg-teal-500/15 border border-teal-500/30"
                          : "hover:bg-teal-900/20 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <ScrollText
                          className={`w-3.5 h-3.5 ${
                            isActive ? "text-teal-400" : "text-teal-500 group-hover:text-teal-400"
                          }`}
                        />
                        <span
                          className={`text-xs font-semibold ${
                            isActive ? "text-teal-300" : "text-teal-400/70 group-hover:text-teal-300"
                          }`}
                        >
                          Plan
                        </span>
                      </div>
                      <p
                        className={`line-clamp-2 leading-snug pl-5 ${
                          isActive ? "text-teal-200/80" : "text-zinc-500 group-hover:text-zinc-400"
                        }`}
                      >
                        {entry.preview}
                      </p>
                    </button>
                  );
                }
                return (
                  <button
                    key={entry.stepId}
                    onClick={() => onNavigate(entry.stepId)}
                    className={`w-full text-left px-2 py-1.5 rounded-md transition-colors text-sm group ${
                      isActive
                        ? "bg-cyan-500/15 border border-cyan-500/30"
                        : "hover:bg-zinc-800/60 border border-transparent"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span
                        className={`font-mono font-semibold ${
                          isActive ? "text-cyan-400" : "text-zinc-400 group-hover:text-zinc-300"
                        }`}
                      >
                        #{entry.turnNumber}
                      </span>
                    </div>
                    <p
                      className={`line-clamp-2 leading-snug ${
                        isActive ? "text-cyan-200/80" : "text-zinc-400 group-hover:text-zinc-300"
                      }`}
                    >
                      {entry.preview}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Sub-Agents view */}
        {navMode === "sub-agents" && hasSubAgents && (
          <div>
            <div className="space-y-1">
              {subAgents.map((sub, idx) => {
                const stepCount = sub.steps?.length ?? 0;
                const toolCount = sub.final_metrics?.tool_call_count ?? 0;
                return (
                  <button
                    key={sub.session_id}
                    onClick={() => handleSubAgentNavigate(sub.session_id)}
                    className="w-full text-left px-2 py-1.5 rounded-md transition-colors text-sm group hover:bg-zinc-800/60 border border-transparent"
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="font-mono font-semibold text-violet-400">
                        #{idx + 1}
                      </span>
                      <span className="text-zinc-400 truncate">
                        {sub.session_id.slice(0, SESSION_ID_MEDIUM)}
                      </span>
                    </div>
                    <p className="text-zinc-400 group-hover:text-zinc-300 leading-snug">
                      {stepCount} steps · {toolCount} tools
                    </p>
                    {sub.first_message && (
                      <p className="text-zinc-500 group-hover:text-zinc-400 line-clamp-1 leading-snug mt-0.5">
                        {truncate(sub.first_message, PREVIEW_MEDIUM)}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Only sub-agents, no prompts — show sub-agents directly without toggle */}
        {!hasPrompts && hasSubAgents && (
          <div>
            <div className="flex items-center gap-1.5 text-sm text-zinc-300 mb-3">
              <Bot className="w-3.5 h-3.5" />
              <span className="font-medium">Sub-Agents</span>
              <span className="text-zinc-500">({subAgents.length})</span>
            </div>
            <div className="space-y-1">
              {subAgents.map((sub, idx) => {
                const stepCount = sub.steps?.length ?? 0;
                const toolCount = sub.final_metrics?.tool_call_count ?? 0;
                return (
                  <button
                    key={sub.session_id}
                    onClick={() => handleSubAgentNavigate(sub.session_id)}
                    className="w-full text-left px-2 py-1.5 rounded-md transition-colors text-sm group hover:bg-zinc-800/60 border border-transparent"
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="font-mono font-semibold text-violet-400">
                        #{idx + 1}
                      </span>
                      <span className="text-zinc-400 truncate">
                        {sub.session_id.slice(0, SESSION_ID_MEDIUM)}
                      </span>
                    </div>
                    <p className="text-zinc-400 group-hover:text-zinc-300 leading-snug">
                      {stepCount} steps · {toolCount} tools
                    </p>
                    {sub.first_message && (
                      <p className="text-zinc-500 group-hover:text-zinc-400 line-clamp-1 leading-snug mt-0.5">
                        {truncate(sub.first_message, PREVIEW_MEDIUM)}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
