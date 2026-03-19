import { motion } from "framer-motion";
import { useState } from "react";
import { Link } from "react-router-dom";
import LatencyChart from "../components/LatencyChart";
import WorkerCard from "../components/WorkerCard";
import { useClusterHealth } from "../hooks/useClusterHealth";
import { useMetrics } from "../hooks/useMetrics";

const WORKER_BAR_COLORS: Record<string, string> = {
  "worker-1": "bg-blue-500",
  "worker-2": "bg-emerald-500",
  "worker-3": "bg-orange-500",
};

function DarkModeToggle() {
  const [dark, setDark] = useState(false);
  const toggle = () => {
    setDark((d) => {
      const next = !d;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  };
  return (
    <button
      onClick={toggle}
      className="text-slate-500 hover:text-slate-800 transition-colors text-sm font-mono"
    >
      {dark ? "☀ Light" : "◐ Dark"}
    </button>
  );
}

const cardVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 },
};

export default function System() {
  const { health, loading: healthLoading } = useClusterHealth();
  const { current, history } = useMetrics();

  const workers = health?.workers ?? [];
  const totalQueries = current?.per_worker_queries
    ? Object.values(current.per_worker_queries).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <motion.div
      className="min-h-screen bg-slate-50 dark:bg-slate-900"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <header className="sticky top-0 z-20 h-16 bg-white/80 dark:bg-slate-800/80
        backdrop-blur border-b border-slate-100 dark:border-slate-700
        flex items-center px-6 gap-4">
        <Link
          to="/"
          className="font-sans font-bold text-lg text-slate-900 dark:text-white tracking-tight
            hover:text-indigo-600 transition-colors"
        >
          SearchOS
        </Link>
        <span className="text-slate-300 dark:text-slate-600 text-sm">·</span>
        <span className="text-slate-500 dark:text-slate-400 text-sm">System Dashboard</span>
        <div className="ml-auto flex items-center gap-4">
          {health?.degraded && (
            <span className="text-xs font-medium text-red-600 bg-red-50 rounded-full px-3 py-1">
              Degraded
            </span>
          )}
          <DarkModeToggle />
          <Link to="/search" className="text-slate-500 hover:text-slate-800 text-sm transition-colors">
            Search
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
        >
          {/* ----------------------------------------------------------------
              LEFT COLUMN — Cluster Health
          ---------------------------------------------------------------- */}
          <div className="space-y-4">
            <h2 className="text-slate-900 dark:text-white font-semibold text-base">
              Cluster Health
            </h2>

            {/* Coordinator card */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-sm font-medium text-slate-700 dark:text-slate-200">
                    coordinator
                  </span>
                  {healthLoading ? (
                    <span className="text-xs text-slate-400">Polling…</span>
                  ) : (
                    <span className={`text-xs font-medium rounded-full px-2 py-0.5
                      ${health?.degraded
                        ? "bg-amber-50 text-amber-600"
                        : "bg-emerald-50 text-emerald-600"}`}
                    >
                      {health?.status ?? "unknown"}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm mt-3">
                  <div>
                    <p className="text-slate-400 text-xs">Uptime</p>
                    <p className="font-mono font-medium text-slate-800 dark:text-white">
                      {health ? `${Math.floor(health.uptime_seconds)}s` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Workers up</p>
                    <p className="font-mono font-medium text-slate-800 dark:text-white">
                      {health ? `${health.healthy_worker_count}/${health.total_worker_count}` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Mode</p>
                    <p className="font-mono font-medium text-slate-800 dark:text-white">
                      {health?.degraded ? "degraded" : "normal"}
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Worker cards */}
            {workers.length === 0 && !healthLoading && (
              <p className="text-slate-400 text-sm text-center py-4">
                No worker data available.
              </p>
            )}
            {workers.map((worker) => (
              <motion.div
                key={worker.worker_id}
                variants={cardVariants}
                transition={{ duration: 0.2 }}
              >
                <WorkerCard
                  worker={worker}
                  queriesServed={current?.per_worker_queries?.[worker.worker_id] ?? 0}
                />
              </motion.div>
            ))}
          </div>

          {/* ----------------------------------------------------------------
              RIGHT COLUMN — Live Metrics
          ---------------------------------------------------------------- */}
          <div className="space-y-4">
            <h2 className="text-slate-900 dark:text-white font-semibold text-base">
              Live Metrics
            </h2>

            {/* Latency chart */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    Latency — p50 / p95 / p99
                  </p>
                  {current && (
                    <span className="font-mono text-xs text-slate-400">
                      last 60s
                    </span>
                  )}
                </div>
                {history.length > 1 ? (
                  <LatencyChart history={history} />
                ) : (
                  <div className="h-48 flex items-center justify-center text-slate-300 text-sm">
                    Waiting for data…
                  </div>
                )}
              </div>
            </motion.div>

            {/* QPS card */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <p className="text-xs text-slate-400 mb-1">Queries / sec</p>
                <p className="font-mono font-bold text-4xl text-slate-900 dark:text-white">
                  {current?.qps.toFixed(1) ?? "0.0"}
                </p>
                <div className="mt-2 flex gap-4 text-xs font-mono text-slate-400">
                  <span>total {current?.total_queries.toLocaleString() ?? 0}</span>
                  <span>errors {current?.error_count ?? 0}</span>
                  <span>degraded {current?.degraded_count ?? 0}</span>
                </div>
              </div>
            </motion.div>

            {/* Per-worker distribution */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-4">
                  Query Distribution
                </p>
                {totalQueries === 0 ? (
                  <p className="text-slate-300 text-sm">No queries yet.</p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(current?.per_worker_queries ?? {}).map(([wid, count]) => {
                      const pct = totalQueries > 0 ? (count / totalQueries) * 100 : 0;
                      const barColor = WORKER_BAR_COLORS[wid] ?? "bg-slate-400";
                      return (
                        <div key={wid}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-xs text-slate-600 dark:text-slate-300">
                              {wid}
                            </span>
                            <span className="font-mono text-xs text-slate-400">
                              {count.toLocaleString()} ({pct.toFixed(1)}%)
                            </span>
                          </div>
                          <div className="w-full h-2 bg-slate-100 rounded-full">
                            <div
                              className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </motion.div>

            {/* p50/p95/p99 at-a-glance */}
            {current && (
              <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
                <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                  dark:border-slate-700 shadow-sm p-5">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
                    Current Latency
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "p50", value: current.p50_ms, color: "text-indigo-500" },
                      { label: "p95", value: current.p95_ms, color: "text-amber-500" },
                      { label: "p99", value: current.p99_ms, color: "text-red-500" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="text-center">
                        <p className="text-slate-400 text-xs mb-1 font-mono">{label}</p>
                        <p className={`font-mono font-bold text-xl ${color}`}>
                          {value.toFixed(1)}
                          <span className="text-xs font-normal text-slate-400 ml-0.5">ms</span>
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      </main>
    </motion.div>
  );
}
