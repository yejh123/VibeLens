import { FolderOpen, Tag, Wrench } from "lucide-react";
import { Tooltip } from "../tooltip";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  SOURCE_COLORS,
  SOURCE_DESCRIPTIONS,
  SOURCE_LABELS,
  SUBDIR_DESCRIPTIONS,
  SUBDIR_LABELS,
  TAG_DESCRIPTIONS,
} from "./skill-constants";

/** Colored pill showing which agent interface a skill comes from. */
export function SourceBadge({ sourceType, sourcePath }: { sourceType: string; sourcePath?: string }) {
  const colorClass = SOURCE_COLORS[sourceType] || "bg-zinc-700 text-zinc-400 border-zinc-600";
  const label = SOURCE_LABELS[sourceType] || sourceType;
  const description = SOURCE_DESCRIPTIONS[sourceType] || sourcePath || sourceType;

  return (
    <Tooltip text={description}>
      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${colorClass}`}>
        {label}
      </span>
    </Tooltip>
  );
}

/** Small pill for a skill tag with hover description. */
export function TagBadge({ tag }: { tag: string }) {
  return (
    <Tooltip text={TAG_DESCRIPTIONS[tag] || `Tag: ${tag}`}>
      <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/60 text-zinc-300 cursor-default">
        {tag}
      </span>
    </Tooltip>
  );
}

/** Rounded pill variant of TagBadge used in detail popups. */
export function TagPill({ tag }: { tag: string }) {
  return (
    <Tooltip text={TAG_DESCRIPTIONS[tag] || `Tag: ${tag}`}>
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-700/60 text-zinc-300 border border-zinc-600/30 cursor-default hover:bg-zinc-700 hover:text-zinc-200 transition">
        {tag}
      </span>
    </Tooltip>
  );
}

/** Mono-spaced pill showing an allowed tool name. */
export function ToolBadge({ tool }: { tool: string }) {
  return (
    <Tooltip text={`Allowed tool: ${tool}`}>
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-900/20 text-cyan-400/70 font-mono cursor-default">
        {tool}
      </span>
    </Tooltip>
  );
}

/** Mono-spaced pill showing a subdirectory name. */
export function SubdirBadge({ dir }: { dir: string }) {
  return (
    <Tooltip text={SUBDIR_DESCRIPTIONS[dir] || `Subdirectory: ${dir}`}>
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-300 font-mono cursor-default hover:bg-zinc-600/80 transition">
        {SUBDIR_LABELS[dir] || dir}
      </span>
    </Tooltip>
  );
}

/** Badge for a featured skill's category. */
export function CategoryBadge({ category }: { category: string }) {
  const colorClass = CATEGORY_COLORS[category] || "bg-zinc-700 text-zinc-400 border-zinc-600";
  const label = CATEGORY_LABELS[category] || category;
  const description = TAG_DESCRIPTIONS[category] || `Category: ${category}`;

  return (
    <Tooltip text={description}>
      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${colorClass}`}>
        {label}
      </span>
    </Tooltip>
  );
}

/** Row of tag badges with overflow count, prefixed by a Tag icon. */
export function TagList({ tags, max = 5 }: { tags: string[]; max?: number }) {
  if (tags.length === 0) return null;
  return (
    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
      <Tag className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
      {tags.slice(0, max).map((tag) => (
        <TagBadge key={tag} tag={tag} />
      ))}
      {tags.length > max && (
        <span className="text-xs text-zinc-500">+{tags.length - max}</span>
      )}
    </div>
  );
}

/** Row of tool badges with overflow count, prefixed by a Wrench icon. */
export function ToolList({ tools, max = 3 }: { tools: string[]; max?: number }) {
  if (tools.length === 0) return null;
  return (
    <div className="flex items-center gap-1 mt-1 flex-wrap">
      <Wrench className="w-3 h-3 text-zinc-600 shrink-0" />
      {tools.slice(0, max).map((tool) => (
        <ToolBadge key={tool} tool={tool} />
      ))}
      {tools.length > max && (
        <span className="text-[10px] text-zinc-600">+{tools.length - max}</span>
      )}
    </div>
  );
}

/** Row of subdirectory badges, prefixed by a FolderOpen icon. */
export function SubdirList({ dirs }: { dirs: string[] }) {
  if (dirs.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      <FolderOpen className="w-3 h-3 text-zinc-500 shrink-0 mt-0.5" />
      {dirs.map((dir) => (
        <SubdirBadge key={dir} dir={dir} />
      ))}
    </div>
  );
}
