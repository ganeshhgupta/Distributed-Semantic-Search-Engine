import type { WorkerHealthResponse } from "../types";

interface WorkerCardProps {
  worker: WorkerHealthResponse;
  queriesServed?: number;
  shardRange?: [number, number];
}

const WORKER_COLORS: Record<string, { ring: string; text: string }> = {
  "worker-1": { ring: "ring-blue-200", text: "text-blue-600" },
  "worker-2": { ring: "ring-emerald-200", text: "text-emerald-600" },
  "worker-3": { ring: "ring-orange-200", text: "text-orange-600" },
};

function fmt(n: number, unit: string) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M ${unit}`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K ${unit}`;
  return `${n} ${unit}`;
}

function fmtBytes(b: number) {
  if (b >= 1_073_741_824) return `${(b / 1_073_741_824).toFixed(2)} GB`;
  if (b >= 1_048_576) return `${(b / 1_048_576).toFixed(1)} MB`;
  if (b >= 1_024) return `${(b / 1_024).toFixed(1)} KB`;
  return `${b} B`;
}

function fmtUptime(s: number) {
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

export default function WorkerCard({ worker, queriesServed = 0, shardRange }: WorkerCardProps) {
  const isDown = worker.status === "down" || !["healthy", "degraded"].includes(worker.status);
  const colorStyle = WORKER_COLORS[worker.worker_id] ?? { ring: "ring-slate-200", text: "text-slate-600" };

  return (
    <div
      className={`bg-white rounded-[12px] border border-slate-100 shadow-sm p-5
        transition-all duration-500
        ${isDown ? "opacity-40 grayscale" : ""}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${isDown ? "bg-red-500" : "bg-emerald-500"}`}
          />
          <span className={`font-mono font-medium text-sm ${colorStyle.text}`}>
            {worker.worker_id}
          </span>
          <span className="text-slate-400 font-mono text-xs">
            shard {worker.shard_id}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isDown ? (
            <span className="text-xs font-medium text-red-600 bg-red-50 rounded-full px-2 py-0.5">
              Degraded
            </span>
          ) : (
            <span className="text-xs font-medium text-emerald-600 bg-emerald-50 rounded-full px-2 py-0.5">
              Online
            </span>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <p className="text-slate-400 text-xs mb-0.5">Documents</p>
          <p className="font-mono font-medium text-slate-800">
            {fmt(worker.document_count, "docs")}
          </p>
        </div>
        <div>
          <p className="text-slate-400 text-xs mb-0.5">Index size</p>
          <p className="font-mono font-medium text-slate-800">
            {fmtBytes(worker.index_size_bytes)}
          </p>
        </div>
        <div>
          <p className="text-slate-400 text-xs mb-0.5">Uptime</p>
          <p className="font-mono font-medium text-slate-800">
            {fmtUptime(worker.uptime_seconds)}
          </p>
        </div>
        <div>
          <p className="text-slate-400 text-xs mb-0.5">Queries served</p>
          <p className="font-mono font-medium text-slate-800">
            {queriesServed.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Shard range */}
      {shardRange && (
        <div className="mt-3 pt-3 border-t border-slate-50">
          <p className="text-slate-400 text-xs mb-0.5">Ring range</p>
          <p className="font-mono text-xs text-slate-600">
            {shardRange[0].toLocaleString()} – {shardRange[1].toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
