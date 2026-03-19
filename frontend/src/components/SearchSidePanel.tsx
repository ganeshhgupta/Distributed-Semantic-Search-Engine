/**
 * SearchSidePanel
 *
 * Sticky right-side panel visible during and after a search.
 * Shows the distributed system internals in real time:
 *   - animated fan-out tree (SearchFlowAnimation)
 *   - per-worker latency breakdown
 *   - live cluster health (worker status dots)
 *   - request trace ID
 */
import { motion, AnimatePresence } from "framer-motion";
import type { SearchResponse, WorkerHealthResponse } from "../types";
import SearchFlowAnimation from "./SearchFlowAnimation";

const WORKER_COLORS: Record<string, { dot: string; bar: string; text: string }> = {
  "search-worker-0": { dot: "bg-blue-500",    bar: "bg-blue-400",    text: "text-blue-600"    },
  "search-worker-1": { dot: "bg-emerald-500", bar: "bg-emerald-400", text: "text-emerald-600" },
  "search-worker-2": { dot: "bg-orange-500",  bar: "bg-orange-400",  text: "text-orange-600"  },
  "worker-1":        { dot: "bg-blue-500",    bar: "bg-blue-400",    text: "text-blue-600"    },
  "worker-2":        { dot: "bg-emerald-500", bar: "bg-emerald-400", text: "text-emerald-600" },
  "worker-3":        { dot: "bg-orange-500",  bar: "bg-orange-400",  text: "text-orange-600"  },
};

const fallback = { dot: "bg-slate-400", bar: "bg-slate-300", text: "text-slate-500" };

interface Props {
  loading: boolean;
  response: SearchResponse | null;
  workers: WorkerHealthResponse[];
}

function LatencyRow({
  label,
  ms,
  maxMs,
  colorClass,
}: {
  label: string;
  ms: number;
  maxMs: number;
  colorClass: string;
}) {
  const pct = Math.min((ms / Math.max(maxMs, 1)) * 100, 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs text-slate-500">{label}</span>
        <span className="font-mono text-xs text-slate-700 font-medium">{ms.toFixed(0)}ms</span>
      </div>
      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <motion.div
          className={`h-1.5 rounded-full ${colorClass}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function SearchSidePanel({ loading, response, workers }: Props) {
  const hasData = loading || response;
  if (!hasData) return null;

  const maxMs = response
    ? Math.max(response.fanout_ms, response.coordinator_overhead_ms, response.merge_ms, 1)
    : 1;

  return (
    <motion.aside
      className="w-72 shrink-0 space-y-4"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Flow animation card — only shown after results arrive (done state) */}
      {!loading && response && (
        <div className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">
            Fan-out trace
          </p>
          <SearchFlowAnimation loading={false} response={response} />
        </div>
      )}

      {/* Loading placeholder */}
      {loading && (
        <div className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
            Fan-out trace
          </p>
          <div className="space-y-2">
            {["coordinator", "worker-0", "worker-1", "worker-2", "merge"].map((n) => (
              <div key={n} className="h-2 bg-slate-100 rounded-full animate-pulse" style={{ width: n === "coordinator" ? "60%" : n === "merge" ? "50%" : "80%" }} />
            ))}
          </div>
        </div>
      )}

      {/* Latency breakdown */}
      <AnimatePresence>
        {response && (
          <motion.div
            className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-4 space-y-3"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
              Latency breakdown
            </p>
            <LatencyRow
              label="Embedding"
              ms={response.coordinator_overhead_ms}
              maxMs={response.total_latency_ms}
              colorClass="bg-indigo-400"
            />
            <LatencyRow
              label="Fan-out (parallel)"
              ms={response.fanout_ms}
              maxMs={response.total_latency_ms}
              colorClass="bg-violet-400"
            />
            <LatencyRow
              label="Merge"
              ms={response.merge_ms}
              maxMs={response.total_latency_ms}
              colorClass="bg-purple-300"
            />
            <div className="pt-1 border-t border-slate-50 flex items-center justify-between">
              <span className="font-mono text-xs text-slate-400">Total</span>
              <span className="font-mono text-xs font-bold text-slate-800">
                {response.total_latency_ms.toFixed(0)}ms
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Per-worker shard results */}
      <AnimatePresence>
        {response && response.results.length > 0 && (
          <motion.div
            className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-4"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, delay: 0.05 }}
          >
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Results by shard
            </p>
            {(() => {
              const counts: Record<string, number> = {};
              response.results.forEach((r) => {
                counts[r.worker_id] = (counts[r.worker_id] ?? 0) + 1;
              });
              const total = response.results.length;
              return Object.entries(counts).map(([wid, count]) => {
                const c = WORKER_COLORS[wid] ?? fallback;
                const pct = (count / total) * 100;
                return (
                  <div key={wid} className="mb-2.5">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`font-mono text-xs ${c.text} flex items-center gap-1`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
                        {wid}
                      </span>
                      <span className="font-mono text-xs text-slate-500">{count} results</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <motion.div
                        className={`h-1.5 rounded-full ${c.bar}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 0.4, ease: "easeOut" }}
                      />
                    </div>
                  </div>
                );
              });
            })()}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Cluster health */}
      {workers.length > 0 && (
        <div className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
            Cluster health
          </p>
          <div className="space-y-2">
            {workers.map((w) => {
              const healthy = w.status === "healthy" || w.status === "degraded";
              const c = WORKER_COLORS[w.worker_id] ?? fallback;
              return (
                <div key={w.worker_id} className="flex items-center justify-between">
                  <span className={`font-mono text-xs flex items-center gap-1.5 ${c.text}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${healthy ? c.dot : "bg-red-400"}`} />
                    {w.worker_id}
                  </span>
                  <span className="font-mono text-xs text-slate-400">
                    {w.document_count.toLocaleString()} docs
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Trace ID */}
      <AnimatePresence>
        {response && (
          <motion.div
            className="bg-slate-50 rounded-[10px] border border-slate-100 px-3 py-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <p className="text-xs text-slate-400 mb-0.5">trace_id</p>
            <p className="font-mono text-xs text-slate-500 break-all">{response.trace_id}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.aside>
  );
}
