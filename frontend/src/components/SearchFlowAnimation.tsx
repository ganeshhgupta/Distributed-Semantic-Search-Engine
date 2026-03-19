/**
 * SearchFlowAnimation
 *
 * Renders an animated tree showing the distributed fan-out in real time:
 *
 *         [  Coordinator  ]
 *          /      |       \
 *    [W-0]     [W-1]     [W-2]
 *          \      |       /
 *           [ Merge top-K ]
 *
 * Stages driven by a simple timer while loading is true,
 * then shows real latency numbers from the response.
 */
import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import type { SearchResponse } from "../types";

// ─── Types ──────────────────────────────────────────────────────────────────

type Stage = "idle" | "embedding" | "fanout" | "searching" | "merging" | "done";

interface NodePos { x: number; y: number }

// ─── Layout constants (viewBox 600 × 320) ───────────────────────────────────

const COORD:   NodePos = { x: 300, y:  52 };
const WORKERS: NodePos[] = [
  { x: 100, y: 172 },
  { x: 300, y: 172 },
  { x: 500, y: 172 },
];
const MERGE: NodePos = { x: 300, y: 285 };

const WORKER_COLORS = ["#3b82f6", "#10b981", "#f97316"];   // blue, emerald, orange
const WORKER_BG     = ["#eff6ff", "#ecfdf5", "#fff7ed"];
const WORKER_BORDER = ["#bfdbfe", "#a7f3d0", "#fed7aa"];
const WORKER_LABELS = ["search-worker-0", "search-worker-1", "search-worker-2"];
const WORKER_SHARDS = ["Shard 0 · Science", "Shard 1 · History", "Shard 2 · Culture"];

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Animated SVG path that "draws" from start to end */
function AnimatedPath({
  x1, y1, x2, y2,
  color = "#6366f1",
  delay = 0,
  duration = 0.4,
  reverse = false,
}: {
  x1: number; y1: number; x2: number; y2: number;
  color?: string; delay?: number; duration?: number; reverse?: boolean;
}) {
  const id = `path-${x1}-${y1}-${x2}-${y2}`;
  // Compute path length roughly for dash animation
  const len = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);

  return (
    <g>
      {/* Static grey track */}
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#e2e8f0" strokeWidth="1.5" />
      {/* Animated coloured line */}
      <motion.line
        x1={reverse ? x2 : x1} y1={reverse ? y2 : y1}
        x2={reverse ? x2 : x1} y2={reverse ? y2 : y1}
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        animate={{ x2: reverse ? x1 : x2, y2: reverse ? y1 : y2 }}
        transition={{ delay, duration, ease: "easeInOut" }}
      />
      {/* Travelling dot */}
      <motion.circle
        cx={reverse ? x2 : x1}
        cy={reverse ? y2 : y1}
        r="3.5"
        fill={color}
        initial={{ opacity: 0 }}
        animate={{
          cx: [reverse ? x2 : x1, reverse ? x1 : x2],
          cy: [reverse ? y2 : y1, reverse ? y1 : y2],
          opacity: [0, 1, 1, 0],
        }}
        transition={{ delay, duration: duration + 0.1, ease: "easeInOut" }}
      />
    </g>
  );
}

/** Node box */
function Node({
  x, y, label, sublabel, color, bg, border,
  delay = 0, pulse = false, latency,
}: {
  x: number; y: number; label: string; sublabel?: string;
  color?: string; bg?: string; border?: string;
  delay?: number; pulse?: boolean; latency?: number;
}) {
  const W = 110; const H = pulse ? 52 : 48;
  return (
    <motion.g
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.25, ease: "backOut" }}
    >
      {/* Pulse ring when searching */}
      {pulse && (
        <motion.rect
          x={x - W / 2 - 4} y={y - H / 2 - 4}
          width={W + 8} height={H + 8}
          rx="10" fill="none"
          stroke={color ?? "#6366f1"}
          strokeWidth="1.5"
          strokeOpacity="0.4"
          animate={{ strokeOpacity: [0.4, 0, 0.4], scale: [1, 1.04, 1] }}
          transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
          style={{ transformOrigin: `${x}px ${y}px` }}
        />
      )}
      {/* Card */}
      <rect
        x={x - W / 2} y={y - H / 2}
        width={W} height={H}
        rx="8"
        fill={bg ?? "#ffffff"}
        stroke={border ?? "#e2e8f0"}
        strokeWidth="1.5"
      />
      {/* Label */}
      <text
        x={x} y={sublabel ? y - 7 : y + 5}
        textAnchor="middle"
        fontSize="11"
        fontWeight="600"
        fontFamily="JetBrains Mono, monospace"
        fill={color ?? "#1e293b"}
      >
        {label}
      </text>
      {/* Sublabel */}
      {sublabel && (
        <text
          x={x} y={y + 10}
          textAnchor="middle"
          fontSize="9"
          fontFamily="Inter, sans-serif"
          fill="#94a3b8"
        >
          {sublabel}
        </text>
      )}
      {/* Latency badge */}
      {latency !== undefined && (
        <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          <rect x={x + W / 2 - 30} y={y - H / 2 - 11} width={30} height={14} rx="4" fill={color ?? "#6366f1"} />
          <text
            x={x + W / 2 - 15} y={y - H / 2 - 1}
            textAnchor="middle" fontSize="8"
            fontFamily="JetBrains Mono, monospace"
            fill="#fff" fontWeight="600"
          >
            {latency.toFixed(0)}ms
          </text>
        </motion.g>
      )}
    </motion.g>
  );
}

// ─── Stage label ──────────────────────────────────────────────────────────────

const STAGE_LABELS: Record<Stage, string> = {
  idle:      "",
  embedding: "Embedding query with MiniLM-L6-v2…",
  fanout:    "Fanning out to 3 shards in parallel…",
  searching: "Workers scanning FAISS indexes…",
  merging:   "Merging & re-ranking top-K results…",
  done:      "Done",
};

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  loading: boolean;
  response: SearchResponse | null;
}

export default function SearchFlowAnimation({ loading, response }: Props) {
  const [stage, setStage] = useState<Stage>("idle");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = []; };

  useEffect(() => {
    clearTimers();
    if (loading) {
      setStage("embedding");
      timers.current.push(setTimeout(() => setStage("fanout"),    420));
      timers.current.push(setTimeout(() => setStage("searching"), 900));
    } else if (response) {
      setStage("merging");
      timers.current.push(setTimeout(() => setStage("done"), 600));
    } else {
      setStage("idle");
    }
    return clearTimers;
  }, [loading, response]);

  if (stage === "idle") return null;

  const showFanout   = ["fanout", "searching", "merging", "done"].includes(stage);
  const showWorkers  = ["searching", "merging", "done"].includes(stage);
  const showReturn   = ["merging", "done"].includes(stage);
  const showMerge    = ["merging", "done"].includes(stage);
  const isDone       = stage === "done";

  // Actual latency numbers from the response
  const workerLatencies = response?.workers_queried.map((wid) => {
    // approximate from total − overhead − merge
    const approx = (response.fanout_ms / response.workers_queried.length);
    return approx;
  });

  return (
    <div className="w-full flex flex-col items-center gap-3 py-6 select-none">
      {/* Stage label */}
      <AnimatePresence mode="wait">
        <motion.p
          key={stage}
          className="text-xs font-mono text-slate-500 h-4"
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
        >
          {STAGE_LABELS[stage]}
        </motion.p>
      </AnimatePresence>

      {/* SVG tree */}
      <svg
        viewBox="0 0 600 320"
        className="w-full max-w-xl"
        style={{ maxHeight: 260 }}
        aria-hidden="true"
      >
        {/* ── Fan-out lines (coord → workers) ── */}
        {showFanout && WORKERS.map((w, i) => (
          <AnimatedPath
            key={`down-${i}`}
            x1={COORD.x} y1={COORD.y + 26}
            x2={w.x}     y2={w.y - 26}
            color={WORKER_COLORS[i]}
            delay={i * 0.07}
            duration={0.35}
          />
        ))}

        {/* ── Return lines (workers → merge) ── */}
        {showReturn && WORKERS.map((w, i) => (
          <AnimatedPath
            key={`up-${i}`}
            x1={w.x}     y1={w.y + 26}
            x2={MERGE.x} y2={MERGE.y - 20}
            color={WORKER_COLORS[i]}
            delay={i * 0.06}
            duration={0.3}
            reverse
          />
        ))}

        {/* ── Nodes ── */}

        {/* Coordinator — always shown */}
        <Node
          x={COORD.x} y={COORD.y}
          label="coordinator"
          sublabel={stage === "embedding" ? "embedding…" : stage === "fanout" ? "fan-out →" : ""}
          color="#6366f1"
          bg="#eef2ff"
          border="#c7d2fe"
          delay={0}
          latency={isDone && response ? response.coordinator_overhead_ms : undefined}
        />

        {/* Workers */}
        {showWorkers && WORKERS.map((w, i) => (
          <Node
            key={i}
            x={w.x} y={w.y}
            label={`worker-${i}`}
            sublabel={WORKER_SHARDS[i]}
            color={WORKER_COLORS[i]}
            bg={WORKER_BG[i]}
            border={WORKER_BORDER[i]}
            delay={i * 0.07}
            pulse={stage === "searching"}
            latency={isDone && response ? (response.fanout_ms / response.workers_queried.length) : undefined}
          />
        ))}

        {/* Merge node */}
        {showMerge && (
          <Node
            x={MERGE.x} y={MERGE.y}
            label="merge top-K"
            sublabel={isDone && response ? `${response.results.length} results` : "re-ranking…"}
            color="#8b5cf6"
            bg="#f5f3ff"
            border="#ddd6fe"
            delay={0}
            latency={isDone && response ? response.merge_ms : undefined}
          />
        )}

        {/* ── Total latency badge (done state) ── */}
        {isDone && response && (
          <motion.g initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
            style={{ transformOrigin: "300px 160px" }} transition={{ delay: 0.3 }}>
            <rect x={230} y={148} width={140} height={24} rx="12" fill="#6366f1" />
            <text x={300} y={164} textAnchor="middle" fontSize="10"
              fontFamily="JetBrains Mono, monospace" fill="#fff" fontWeight="600">
              {response.total_latency_ms.toFixed(1)} ms total
            </text>
          </motion.g>
        )}
      </svg>

      {/* Legend */}
      {showWorkers && (
        <motion.div
          className="flex items-center gap-4 flex-wrap justify-center"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
        >
          {WORKERS.map((_, i) => (
            <span key={i} className="flex items-center gap-1.5 text-xs font-mono"
              style={{ color: WORKER_COLORS[i] }}>
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: WORKER_COLORS[i] }} />
              {WORKER_LABELS[i]}
            </span>
          ))}
        </motion.div>
      )}
    </div>
  );
}
