/**
 * Renders text that may contain bullet points in the format:
 *   "Conclusion sentence.\n- Point 1\n- Point 2"
 *
 * Lead text renders as a paragraph; lines starting with "- " render as
 * a styled <ul>. Plain text without bullets renders identically to a <p>.
 */
export function BulletText({ text, className = "" }: { text: string; className?: string }) {
  const lines = text.split("\n");
  const lead: string[] = [];
  const bullets: string[] = [];
  let seenBullet = false;

  for (const line of lines) {
    if (line.startsWith("- ")) {
      seenBullet = true;
      bullets.push(line.slice(2));
    } else if (!seenBullet) {
      lead.push(line);
    } else {
      bullets.push(line);
    }
  }

  if (!seenBullet) {
    return <p className={className}>{text}</p>;
  }

  const leadText = lead.join("\n").trim();

  return (
    <div className={className}>
      {leadText && <p>{leadText}</p>}
      <ul className="mt-1.5 space-y-0.5 list-disc pl-4 marker:text-zinc-500">
        {bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
    </div>
  );
}
