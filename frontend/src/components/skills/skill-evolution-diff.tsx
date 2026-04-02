import { ArrowRight, FileText, Pencil, Plus, Wrench, Zap } from "lucide-react";
import type { SkillEdit } from "../../types";
import { Tooltip } from "../tooltip";
import {
  CONFLICT_TYPE_DESCRIPTIONS,
  CONFLICT_TYPE_LABELS,
  CONFLICT_TYPE_STYLES,
  EDIT_KIND_DESCRIPTIONS,
  EDIT_KIND_LABELS,
  EDIT_KIND_STYLES,
} from "./skill-constants";

const EDIT_KIND_ICONS: Record<string, React.ReactNode> = {
  add_instruction: <Plus className="w-2.5 h-2.5" />,
  remove_instruction: <Zap className="w-2.5 h-2.5" />,
  replace_instruction: <ArrowRight className="w-2.5 h-2.5" />,
  update_description: <Pencil className="w-2.5 h-2.5" />,
  add_tool: <Wrench className="w-2.5 h-2.5" />,
  remove_tool: <Wrench className="w-2.5 h-2.5" />,
};

const ADD_ONLY_KINDS = new Set(["add_instruction", "add_tool"]);
const REMOVE_ONLY_KINDS = new Set(["remove_instruction", "remove_tool"]);

/** Synthetic line gap between non-adjacent hunks. */
const HUNK_GAP = 4;

type DiffRow =
  | { type: "hunk-header"; edit: SkillEdit; index: number }
  | { type: "removed"; oldNum: number; text: string }
  | { type: "added"; newNum: number; text: string }
  | { type: "separator" }
  | { type: "rationale"; text: string };

export function EvolutionDiffView({ skillName, edits }: { skillName: string; edits: SkillEdit[] }) {
  const rows = buildDiffRows(edits);

  return (
    <div className="rounded-lg border border-zinc-700/60 overflow-hidden bg-zinc-900/60">
      <DiffFileHeader skillName={skillName} editCount={edits.length} />
      <div className="font-mono text-xs">
        {rows.map((row, i) => {
          switch (row.type) {
            case "hunk-header":
              return <HunkHeader key={i} edit={row.edit} index={row.index} />;
            case "removed":
              return <RemovedLine key={i} oldNum={row.oldNum} text={row.text} />;
            case "added":
              return <AddedLine key={i} newNum={row.newNum} text={row.text} />;
            case "separator":
              return <HunkSeparator key={i} />;
            case "rationale":
              return <HunkRationale key={i} text={row.text} />;
          }
        })}
      </div>
    </div>
  );
}

function DiffFileHeader({ skillName, editCount }: { skillName: string; editCount: number }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-zinc-800/80 border-b border-zinc-700/50 text-xs">
      <FileText className="w-3.5 h-3.5 text-zinc-400" />
      <span className="font-mono text-zinc-300">{skillName}/SKILL.md</span>
      <span className="text-zinc-500 ml-auto">
        {editCount} edit{editCount !== 1 ? "s" : ""}
      </span>
    </div>
  );
}

function HunkHeader({ edit, index }: { edit: SkillEdit; index: number }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 text-[10px] flex-wrap border-b border-zinc-800/40">
      <Tooltip text={EDIT_KIND_DESCRIPTIONS[edit.kind] || "A specific edit to the skill"}>
        <span
          className={`inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded-md cursor-help ${EDIT_KIND_STYLES[edit.kind] || "bg-zinc-700/80 text-zinc-300"}`}
        >
          {EDIT_KIND_ICONS[edit.kind] || <Pencil className="w-2.5 h-2.5" />}
          {EDIT_KIND_LABELS[edit.kind] || edit.kind}
        </span>
      </Tooltip>
      {edit.conflict_type && (
        <Tooltip text={CONFLICT_TYPE_DESCRIPTIONS[edit.conflict_type] || "Conflict detected"}>
          <span
            className={`inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded-md cursor-help ${CONFLICT_TYPE_STYLES[edit.conflict_type] || "bg-zinc-700/80 text-zinc-300"}`}
          >
            {CONFLICT_TYPE_LABELS[edit.conflict_type] || edit.conflict_type}
          </span>
        </Tooltip>
      )}
      <span className="text-zinc-600 ml-auto">hunk {index + 1}</span>
    </div>
  );
}

/** Removed line: old line number on left gutter, right gutter empty. */
function RemovedLine({ oldNum, text }: { oldNum: number; text: string }) {
  return (
    <div className="flex bg-red-950/30">
      <span className="w-10 shrink-0 text-right pr-1.5 text-[10px] leading-5 select-none bg-red-900/40 text-red-400/70">
        {oldNum}
      </span>
      <span className="w-10 shrink-0 leading-5 select-none bg-red-950/20" />
      <span className="w-5 shrink-0 text-center leading-5 select-none text-red-500/70">-</span>
      <span className="flex-1 px-2 leading-5 whitespace-pre-wrap break-words text-red-300/90">
        {text}
      </span>
    </div>
  );
}

/** Added line: left gutter empty, new line number on right gutter. */
function AddedLine({ newNum, text }: { newNum: number; text: string }) {
  return (
    <div className="flex bg-emerald-950/25">
      <span className="w-10 shrink-0 leading-5 select-none bg-emerald-950/10" />
      <span className="w-10 shrink-0 text-right pr-1.5 text-[10px] leading-5 select-none bg-emerald-900/35 text-emerald-400/70">
        {newNum}
      </span>
      <span className="w-5 shrink-0 text-center leading-5 select-none text-emerald-500/70">+</span>
      <span className="flex-1 px-2 leading-5 whitespace-pre-wrap break-words text-emerald-300/90">
        {text}
      </span>
    </div>
  );
}

function HunkSeparator() {
  return (
    <div className="flex items-center py-0.5 bg-zinc-800/30 text-zinc-600 text-[10px] select-none border-y border-zinc-800/40">
      <span className="w-10 shrink-0" />
      <span className="w-10 shrink-0" />
      <span className="px-2">···</span>
    </div>
  );
}

function HunkRationale({ text }: { text: string }) {
  return (
    <div className="px-3 py-1.5 bg-zinc-800/30 border-t border-zinc-800/40">
      <p className="text-[11px] text-zinc-500 italic font-sans pl-[5.25rem]">{text}</p>
    </div>
  );
}

/** Build a flat list of diff rows from all edits, with synthetic line numbers. */
function buildDiffRows(edits: SkillEdit[]): DiffRow[] {
  const rows: DiffRow[] = [];
  let oldCursor = 1;
  let newCursor = 1;

  edits.forEach((edit, idx) => {
    if (idx > 0) {
      rows.push({ type: "separator" });
      oldCursor += HUNK_GAP;
      newCursor += HUNK_GAP;
    }

    rows.push({ type: "hunk-header", edit, index: idx });

    const removed = getRemoved(edit);
    const added = getAdded(edit);

    for (const line of removed) {
      rows.push({ type: "removed", oldNum: oldCursor++, text: line });
    }
    for (const line of added) {
      rows.push({ type: "added", newNum: newCursor++, text: line });
    }

    // Sync cursors so the next hunk starts from the same baseline
    const maxCursor = Math.max(oldCursor, newCursor);
    oldCursor = maxCursor;
    newCursor = maxCursor;

    if (edit.rationale) {
      rows.push({ type: "rationale", text: edit.rationale });
    }
  });

  return rows;
}

function getRemoved(edit: SkillEdit): string[] {
  if (ADD_ONLY_KINDS.has(edit.kind)) return [];
  return splitText(edit.target);
}

function getAdded(edit: SkillEdit): string[] {
  if (REMOVE_ONLY_KINDS.has(edit.kind)) return [];
  return splitText(edit.replacement);
}

function splitText(text: string | null | undefined): string[] {
  if (!text || text.trim().length === 0) return [];
  return text.split("\n");
}
