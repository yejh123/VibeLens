import { Info } from "lucide-react";

export function DemoBanner() {
  return (
    <div className="px-3 py-2 rounded-lg bg-cyan-900/20 border border-cyan-700/30">
      <div className="flex items-start gap-2">
        <Info className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
        <p className="text-xs text-cyan-300/90">
          This is sample data for demonstration.{" "}
          Install VibeLens locally (<code className="px-1 py-0.5 bg-zinc-800 rounded text-[11px]">pip install vibelens</code>)
          to run real LLM-powered analysis on your own sessions.
        </p>
      </div>
    </div>
  );
}
