import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricsSnapshot } from "../types";

interface LatencyChartProps {
  history: MetricsSnapshot[];
}

export default function LatencyChart({ history }: LatencyChartProps) {
  const data = history.map((s, i) => ({
    idx: i,
    p50: s.p50_ms,
    p95: s.p95_ms,
    p99: s.p99_ms,
  }));

  return (
    <ResponsiveContainer width="100%" height={192}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="idx" hide />
        <YAxis
          tickFormatter={(v: number) => `${v}ms`}
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
          width={56}
        />
        <Tooltip
          contentStyle={{
            fontSize: 11,
            fontFamily: "JetBrains Mono",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
          }}
          formatter={(value: number, name: string) => [`${value.toFixed(1)}ms`, name]}
          labelFormatter={() => ""}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
        />
        <Line
          type="monotone"
          dataKey="p50"
          stroke="#6366f1"
          strokeWidth={1.5}
          dot={false}
          name="p50"
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="p95"
          stroke="#fbbf24"
          strokeWidth={1.5}
          dot={false}
          name="p95"
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="p99"
          stroke="#ef4444"
          strokeWidth={1.5}
          dot={false}
          name="p99"
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
