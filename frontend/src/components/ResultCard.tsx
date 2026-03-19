import type { SearchResultItem } from "../types";

interface ResultCardProps {
  result: SearchResultItem;
  query: string;
}

const WORKER_STYLES: Record<
  string,
  { bg: string; text: string; dot: string }
> = {
  "search-worker-0": { bg: "bg-blue-50", text: "text-blue-600", dot: "bg-blue-500" },
  "search-worker-1": { bg: "bg-emerald-50", text: "text-emerald-600", dot: "bg-emerald-500" },
  "search-worker-2": { bg: "bg-orange-50", text: "text-orange-600", dot: "bg-orange-500" },
  // legacy names (coordinator pre-fix)
  "worker-1": { bg: "bg-blue-50", text: "text-blue-600", dot: "bg-blue-500" },
  "worker-2": { bg: "bg-emerald-50", text: "text-emerald-600", dot: "bg-emerald-500" },
  "worker-3": { bg: "bg-orange-50", text: "text-orange-600", dot: "bg-orange-500" },
};

function getWorkerStyle(workerId: string) {
  return (
    WORKER_STYLES[workerId] ?? {
      bg: "bg-slate-50",
      text: "text-slate-600",
      dot: "bg-slate-400",
    }
  );
}

function highlightText(text: string, query: string): string {
  if (!query.trim()) return text;
  const terms = query.trim().split(/\s+/).filter(Boolean);
  const pattern = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  try {
    return text.replace(
      new RegExp(`(${pattern})`, "gi"),
      `<mark class="bg-yellow-100 text-slate-900 rounded px-0.5">$1</mark>`
    );
  } catch {
    return text;
  }
}

/** Strip the leading "Title: " prefix baked into chunk text at index time */
function extractSnippet(text: string): { title: string; body: string } {
  const colonIdx = text.indexOf(": ");
  if (colonIdx > 0 && colonIdx < 80) {
    return {
      title: text.slice(0, colonIdx).trim(),
      body: text.slice(colonIdx + 2).trim(),
    };
  }
  return { title: "", body: text };
}

/** Turn raw cosine similarity (0–1) into a human-readable relevance label */
function relevanceLabel(score: number): { label: string; color: string } {
  if (score >= 0.55) return { label: "Strong match", color: "text-emerald-600" };
  if (score >= 0.40) return { label: "Good match",   color: "text-indigo-500" };
  if (score >= 0.28) return { label: "Related",      color: "text-amber-500"  };
  return                     { label: "Weak match",  color: "text-slate-400"  };
}

export default function ResultCard({ result, query }: ResultCardProps) {
  const style = getWorkerStyle(result.worker_id);
  const { title, body } = extractSnippet(result.text);
  const displayTitle = title || result.doc_id;
  const snippet = body.slice(0, 300) + (body.length > 300 ? "…" : "");
  const highlighted = highlightText(snippet, query);
  const { label: relLabel, color: relColor } = relevanceLabel(result.score);

  return (
    <div className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-5
      hover:-translate-y-0.5 hover:shadow-md transition-all duration-200">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <span className="text-xs font-mono text-slate-400 mb-1 block">
            #{result.rank}
          </span>
          <p className="text-slate-900 font-semibold text-base leading-snug line-clamp-2">
            {displayTitle}
          </p>
        </div>

        {/* Worker badge */}
        <span
          className={`inline-flex items-center gap-1 text-xs font-mono rounded-full
            px-2 py-0.5 shrink-0 ${style.bg} ${style.text}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {result.worker_id}
        </span>
      </div>

      {/* Snippet */}
      <p
        className="text-slate-600 text-sm mt-2 leading-relaxed line-clamp-3"
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />

      {/* Score bar + relevance label */}
      <div className="mt-3 flex items-center gap-3">
        <div className="flex-1 h-1 bg-slate-100 rounded-full">
          <div
            className="h-1 bg-indigo-400 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(result.score * 180, 100).toFixed(1)}%` }}
          />
        </div>
        <span className={`text-xs font-mono shrink-0 ${relColor}`}>
          {relLabel}
        </span>
      </div>
    </div>
  );
}
