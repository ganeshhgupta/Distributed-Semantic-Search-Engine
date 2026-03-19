import type { WorkerHealthResponse } from "../types";

interface WorkerCardProps {
  worker: WorkerHealthResponse;
  queriesServed?: number;
  shardRange?: [number, number];
}

const WORKER_COLORS: Record<string, { text: string }> = {
  "search-worker-0": { text: "text-blue-600" },
  "search-worker-1": { text: "text-emerald-600" },
  "search-worker-2": { text: "text-orange-600" },
};

function fmtBytes(b: number) {
  if (b >= 1_048_576) return `${(b / 1_048_576).toFixed(1)} MB`;
  if (b >= 1_024)     return `${(b / 1_024).toFixed(1)} KB`;
  return `${b} B`;
}

function fmtUptime(s: number) {
  if (s < 60)   return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

export default function WorkerCard({ worker, queriesServed = 0, shardRange }: WorkerCardProps) {
  const isDown   = !["healthy", "degraded"].includes(worker.status);
  const colorCls = WORKER_COLORS[worker.worker_id]?.text ?? "text-slate-600";

  return (
    <div className="flex-1 min-w-0">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full ${isDown ? "bg-red-500" : "bg-emerald-500"}`} />
        <span className={`font-mono font-medium text-sm ${colorCls}`}>{worker.worker_id}</span>
        <span className="text-slate-400 font-mono text-xs">· shard {worker.shard_id}</span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <p className="text-slate-400 text-xs">Documents</p>
          <p className="font-mono font-medium text-slate-800">
            {worker.document_count.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-slate-400 text-xs">Index size</p>
          <p className="font-mono font-medium text-slate-800">
            {fmtBytes(worker.index_size_bytes)}
          </p>
        </div>
        <div>
          <p className="text-slate-400 text-xs">Uptime</p>
          <p className="font-mono font-medium text-slate-800">
            {fmtUptime(worker.uptime_seconds)}
          </p>
        </div>
        <div>
          <p className="text-slate-400 text-xs">Queries</p>
          <p className="font-mono font-medium text-slate-800">
            {queriesServed.toLocaleString()}
          </p>
        </div>
      </div>

      {shardRange && (
        <div className="mt-2 pt-2 border-t border-slate-50">
          <p className="text-xs font-mono text-slate-400">
            {shardRange[0].toLocaleString()} – {shardRange[1].toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
