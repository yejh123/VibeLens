import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { useCallback, useState } from "react";
import type {
  SkillAnalysisResult,
  SkillCreation,
  SkillEvolutionSuggestion,
  SkillMode,
  SkillRecommendation,
  WorkflowPattern,
} from "../../types";

export type SkillTab = "local" | "explore" | "retrieve" | "create" | "evolve";

export function AnalysisLoadingState({ mode, sessionCount }: { mode: SkillMode; sessionCount: number }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-10 h-10 text-violet-400 animate-spin" />
        <div className="text-center">
          <p className="text-sm font-medium text-zinc-200">
            Analyzing {sessionCount} session{sessionCount !== 1 ? "s" : ""}
          </p>
          <p className="text-xs text-zinc-500 mt-1">Mode: {mode} — detecting workflow patterns</p>
        </div>
      </div>
    </div>
  );
}

export function AnalysisEmptyState({
  mode,
  checkedCount,
  error,
  onRun,
}: {
  mode: SkillMode;
  checkedCount: number;
  error: string | null;
  onRun: () => void;
}) {
  const modeDescriptions: Record<SkillMode, { title: string; desc: string; icon: React.ReactNode }> = {
    retrieval: {
      title: "Skill Retrieval",
      desc: "Detect workflow patterns and recommend existing skills that match your coding style.",
      icon: <Search className="w-6 h-6 text-violet-400" />,
    },
    creation: {
      title: "Skill Creation",
      desc: "Generate new SKILL.md files from detected automation opportunities in your sessions.",
      icon: <Sparkles className="w-6 h-6 text-emerald-400" />,
    },
    evolution: {
      title: "Skill Evolution",
      desc: "Analyze installed skills against your usage data and suggest targeted improvements.",
      icon: <TrendingUp className="w-6 h-6 text-amber-400" />,
    },
  };
  const info = modeDescriptions[mode];

  return (
    <div className="flex items-center justify-center h-full">
      <div className="max-w-md text-center px-6">
        <div className="flex justify-center mb-4">{info.icon}</div>
        <h3 className="text-lg font-bold text-zinc-100 mb-2">{info.title}</h3>
        <p className="text-sm text-zinc-400 mb-6">{info.desc}</p>
        {error && (
          <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-red-900/20 border border-red-800/30 mb-4 text-left">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}
        <button
          onClick={onRun}
          disabled={checkedCount === 0}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-violet-600 hover:bg-violet-500 rounded-lg transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Play className="w-4 h-4" />
          {checkedCount > 0
            ? `Analyze ${checkedCount} session${checkedCount !== 1 ? "s" : ""}`
            : "Select sessions first"}
        </button>
        {checkedCount === 0 && (
          <p className="text-xs text-zinc-600 mt-3">
            Use the checkboxes in the session list to select sessions for analysis.
          </p>
        )}
      </div>
    </div>
  );
}

export function AnalysisResultView({
  result,
  activeTab,
  onRerun,
  onNew,
  fetchWithToken,
}: {
  result: SkillAnalysisResult;
  activeTab: SkillTab;
  onRerun: () => void;
  onNew: () => void;
  fetchWithToken: (url: string, init?: RequestInit) => Promise<Response>;
}) {
  return (
    <div className="max-w-4xl mx-auto px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100">
            {result.workflow_patterns.length} pattern{result.workflow_patterns.length !== 1 ? "s" : ""} detected
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            {result.session_ids.length} session{result.session_ids.length !== 1 ? "s" : ""} analyzed
            {result.sessions_skipped.length > 0 && ` · ${result.sessions_skipped.length} skipped`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onNew}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700/50 rounded-md transition"
          >
            <Plus className="w-3.5 h-3.5" /> New
          </button>
          <button
            onClick={onRerun}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white bg-violet-600 hover:bg-violet-500 rounded-md transition"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Re-run
          </button>
        </div>
      </div>

      <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700/30">
        <p className="text-sm text-zinc-300 leading-relaxed">{result.summary}</p>
        {result.user_profile && (
          <p className="text-xs text-zinc-500 mt-3 italic">{result.user_profile}</p>
        )}
      </div>

      {result.workflow_patterns.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-violet-400" />
            <h4 className="text-sm font-semibold text-zinc-200">Workflow Patterns</h4>
          </div>
          <div className="space-y-2">
            {result.workflow_patterns.map((p) => <PatternCard key={p.pattern_id} pattern={p} />)}
          </div>
        </div>
      )}

      {activeTab === "retrieve" && result.recommendations.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Search className="w-4 h-4 text-violet-400" />
            <h4 className="text-sm font-semibold text-zinc-200">Recommended Skills</h4>
          </div>
          <div className="space-y-2">
            {result.recommendations.map((rec) => <RecommendationCard key={rec.skill_name} rec={rec} />)}
          </div>
        </div>
      )}

      {activeTab === "create" && result.generated_skills.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <h4 className="text-sm font-semibold text-zinc-200">Generated Skills</h4>
          </div>
          <div className="space-y-3">
            {result.generated_skills.map((skill) => (
              <CreatedSkillCard key={skill.name} skill={skill} fetchWithToken={fetchWithToken} />
            ))}
          </div>
        </div>
      )}

      {activeTab === "evolve" && result.evolution_suggestions.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            <h4 className="text-sm font-semibold text-zinc-200">Evolution Suggestions</h4>
          </div>
          <div className="space-y-2">
            {result.evolution_suggestions.map((sug) => <EvolutionCard key={sug.skill_name} suggestion={sug} />)}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 text-[10px] text-zinc-600 pt-2 border-t border-zinc-800">
        <span>Backend: {result.backend_id}</span>
        <span>Model: {result.model}</span>
        {result.cost_usd != null && <span>Cost: ${result.cost_usd.toFixed(4)}</span>}
        <span>{new Date(result.computed_at).toLocaleString()}</span>
      </div>
    </div>
  );
}

function PatternCard({ pattern }: { pattern: WorkflowPattern }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-zinc-700/50 rounded-lg bg-zinc-800/30">
      <button onClick={() => setExpanded(!expanded)} className="w-full text-left px-4 py-3 flex items-start gap-3">
        <div className="shrink-0 mt-0.5">
          {expanded ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-900/30 text-violet-400 font-mono">{pattern.pattern_id}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">{pattern.frequency}x</span>
          </div>
          <p className="text-xs text-zinc-300">{pattern.description}</p>
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-3 pl-11 space-y-2">
          <div>
            <span className="text-[10px] text-zinc-500 block mb-1">Tool Sequence</span>
            <div className="flex items-center gap-1 flex-wrap">
              {pattern.tool_sequence.map((tool, i) => (
                <span key={i} className="flex items-center gap-1">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-900/30 text-violet-400 font-mono">{tool}</span>
                  {i < pattern.tool_sequence.length - 1 && <ArrowRight className="w-2.5 h-2.5 text-zinc-600" />}
                </span>
              ))}
            </div>
          </div>
          <div>
            <span className="text-[10px] text-zinc-500 block mb-1">Pain Point</span>
            <p className="text-xs text-amber-300/80">{pattern.pain_point}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ rec }: { rec: SkillRecommendation }) {
  const confidencePct = Math.round(rec.confidence * 100);
  const confidenceColor = rec.confidence >= 0.8 ? "text-emerald-400" : rec.confidence >= 0.5 ? "text-amber-400" : "text-zinc-500";
  return (
    <div className="border border-zinc-700/50 rounded-lg bg-zinc-800/30 px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-zinc-100">{rec.skill_name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">{rec.source}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${confidenceColor}`}>{confidencePct}% match</span>
          {rec.url && (
            <a href={rec.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-violet-400 hover:text-violet-300 underline">
              View
            </a>
          )}
        </div>
      </div>
      <p className="text-xs text-zinc-400">{rec.match_reason}</p>
      {rec.matched_patterns.length > 0 && (
        <div className="flex items-center gap-1 mt-2">
          <span className="text-[10px] text-zinc-600">Matches:</span>
          {rec.matched_patterns.map((pid) => (
            <span key={pid} className="text-[10px] px-1 py-0.5 rounded bg-violet-900/30 text-violet-400 font-mono">{pid}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function CreatedSkillCard({
  skill,
  fetchWithToken,
}: {
  skill: SkillCreation;
  fetchWithToken: (url: string, init?: RequestInit) => Promise<Response>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installed, setInstalled] = useState(false);

  const handleInstall = useCallback(async () => {
    setInstalling(true);
    try {
      const res = await fetchWithToken("/api/skills/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: skill.name, content: skill.skill_md_content }),
      });
      if (res.ok) setInstalled(true);
    } catch {
      /* ignore */
    } finally {
      setInstalling(false);
    }
  }, [fetchWithToken, skill]);

  return (
    <div className="border border-emerald-800/30 rounded-lg bg-emerald-900/10">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span className="font-mono text-sm font-semibold text-zinc-100">{skill.name}</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-zinc-500 hover:text-zinc-300 transition">
              {expanded ? "Hide" : "Preview"}
            </button>
            <button
              onClick={handleInstall}
              disabled={installing || installed}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded transition disabled:opacity-50"
            >
              {installed ? (<><Check className="w-3 h-3" /> Installed</>) : installing ? (<Loader2 className="w-3 h-3 animate-spin" />) : (<><Download className="w-3 h-3" /> Install</>)}
            </button>
          </div>
        </div>
        <p className="text-xs text-zinc-400">{skill.description}</p>
        <p className="text-xs text-zinc-500 mt-1 italic">{skill.rationale}</p>
      </div>
      {expanded && (
        <div className="border-t border-emerald-800/20 px-4 py-3">
          <pre className="text-[11px] text-zinc-300 font-mono bg-zinc-900/80 rounded p-3 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">
            {skill.skill_md_content}
          </pre>
        </div>
      )}
    </div>
  );
}

function EvolutionCard({ suggestion }: { suggestion: SkillEvolutionSuggestion }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-amber-800/30 rounded-lg bg-amber-900/10">
      <button onClick={() => setExpanded(!expanded)} className="w-full text-left px-4 py-3">
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp className="w-4 h-4 text-amber-400" />
          <span className="font-mono text-sm font-semibold text-zinc-100">{suggestion.skill_name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/30 text-amber-400">
            {suggestion.edits.length} edit{suggestion.edits.length !== 1 ? "s" : ""}
          </span>
        </div>
        <p className="text-xs text-zinc-400">{suggestion.rationale}</p>
      </button>
      {expanded && suggestion.edits.length > 0 && (
        <div className="border-t border-amber-800/20 px-4 py-3 space-y-2">
          {suggestion.edits.map((edit, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-[10px] px-1 py-0.5 rounded bg-zinc-700 text-zinc-400 shrink-0 mt-0.5">{edit.kind}</span>
              <div>
                <p className="text-zinc-300">{edit.target}</p>
                {edit.replacement && <p className="text-emerald-400 mt-0.5">→ {edit.replacement}</p>}
                <p className="text-zinc-500 italic mt-0.5">{edit.rationale}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
