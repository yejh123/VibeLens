import { AlertTriangle } from "lucide-react";

export function WarningsBanner({ warnings }: { warnings: string[] }) {
  return (
    <div className="px-3 py-2 rounded-lg bg-amber-900/20 border border-amber-700/30">
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-300/90 space-y-1">
          <p>Some analysis batches failed. Results below are partial.</p>
          <ul className="list-disc pl-4 text-amber-400/70">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
