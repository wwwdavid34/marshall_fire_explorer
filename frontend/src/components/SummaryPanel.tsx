import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ParcelProperties } from "../types";

interface GeoJSON {
  features: { properties: ParcelProperties }[];
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div
      style={{
        background: "#16162a",
        border: "1px solid #333",
        borderRadius: 6,
        padding: "12px 16px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 22, fontWeight: 700, color: "#fff" }}>{value}</div>
      <div style={{ fontSize: 12, color: "#999", marginTop: 2 }}>{label}</div>
      {sub && (
        <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{sub}</div>
      )}
    </div>
  );
}

export function SummaryPanel({ onClose }: { onClose: () => void }) {
  const { data: geojson } = useQuery<GeoJSON>({
    queryKey: ["parcels"],
    queryFn: () =>
      fetch(`${import.meta.env.BASE_URL}data/parcels.geojson`).then((r) =>
        r.json()
      ),
  });

  const stats = useMemo(() => {
    if (!geojson) return null;

    const parcels = geojson.features.map((f) => f.properties);
    const total = parcels.length;

    const destroyed = parcels.filter((p) => p.Condition === "Destroyed");
    const damaged = parcels.filter((p) => p.Condition === "Damaged");
    const unaffected = parcels.filter((p) => p.Condition === "Unaffected");

    const algoRecovered = destroyed.filter(
      (p) => p.recovery_date != null && p.smile_valid
    );
    const llmRecovered = destroyed.filter((p) => p.recovery_llm != null);

    const algoMonths = algoRecovered
      .map((p) => p.recovery_months_post_fire)
      .filter((v): v is number => v != null);
    const llmMonths = llmRecovered
      .map((p) => p.recovery_llm)
      .filter((v): v is number => v != null);

    // Histogram bins (3-month intervals)
    const maxMonth = 48;
    const binSize = 3;
    const bins: { range: string; algo: number; llm: number }[] = [];
    for (let start = 0; start < maxMonth; start += binSize) {
      const end = start + binSize;
      bins.push({
        range: `${start}-${end}`,
        algo: algoMonths.filter((m) => m >= start && m < end).length,
        llm: llmMonths.filter((m) => m >= start && m < end).length,
      });
    }

    // Cumulative recovery curve
    const allMonthsSorted = Array.from(
      new Set([...algoMonths, ...llmMonths])
    ).sort((a, b) => a - b);
    const cumulative = allMonthsSorted.map((month) => ({
      month: Math.round(month),
      algo: Math.round(
        (algoMonths.filter((m) => m <= month).length / destroyed.length) * 100
      ),
      llm: Math.round(
        (llmMonths.filter((m) => m <= month).length / destroyed.length) * 100
      ),
    }));

    // Deduplicate cumulative by month (keep last value per month)
    const cumulativeMap = new Map<number, (typeof cumulative)[0]>();
    for (const pt of cumulative) {
      cumulativeMap.set(pt.month, pt);
    }
    const cumulativeDeduped = Array.from(cumulativeMap.values()).sort(
      (a, b) => a.month - b.month
    );

    return {
      total,
      destroyed: destroyed.length,
      damaged: damaged.length,
      unaffected: unaffected.length,
      algoRecovered: algoRecovered.length,
      llmRecovered: llmRecovered.length,
      algoPercent: Math.round((algoRecovered.length / destroyed.length) * 100),
      llmPercent: Math.round((llmRecovered.length / destroyed.length) * 100),
      medianAlgo: Math.round(median(algoMonths)),
      medianLlm: Math.round(median(llmMonths)),
      bins,
      cumulative: cumulativeDeduped,
    };
  }, [geojson]);

  if (!stats) return null;

  return (
    <div className="about-overlay" onClick={onClose}>
      <div
        className="about-panel summary-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="about-close" onClick={onClose}>
          &times;
        </button>

        <h2>Executive Summary</h2>

        {/* Stats cards grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 10,
            marginBottom: 24,
          }}
        >
          <StatCard label="Total Parcels" value={stats.total.toLocaleString()} />
          <StatCard
            label="Destroyed"
            value={stats.destroyed.toLocaleString()}
          />
          <StatCard label="Damaged" value={stats.damaged.toLocaleString()} />
          <StatCard
            label="Unaffected"
            value={stats.unaffected.toLocaleString()}
          />
        </div>

        {/* Recovery stats */}
        <h3>Recovery Detection</h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 10,
            marginBottom: 24,
          }}
        >
          <StatCard
            label="Algorithmic Recoveries"
            value={stats.algoRecovered}
            sub={`${stats.algoPercent}% of destroyed`}
          />
          <StatCard
            label="LLM Detections"
            value={stats.llmRecovered}
            sub={`${stats.llmPercent}% of destroyed`}
          />
          <StatCard
            label="Median Recovery (Algo)"
            value={`${stats.medianAlgo} mo`}
          />
          <StatCard
            label="Median Recovery (LLM)"
            value={`${stats.medianLlm} mo`}
          />
        </div>

        {/* Damage breakdown */}
        <h3>Damage Breakdown</h3>
        <div
          style={{
            display: "flex",
            gap: 12,
            marginBottom: 24,
            fontSize: 14,
          }}
        >
          {[
            { label: "Destroyed", count: stats.destroyed, color: "#e41a1c" },
            { label: "Damaged", count: stats.damaged, color: "#ff7f00" },
            { label: "Unaffected", count: stats.unaffected, color: "#4daf4a" },
          ].map(({ label, count, color }) => (
            <div
              key={label}
              style={{
                flex: 1,
                background: "#16162a",
                border: `1px solid ${color}44`,
                borderRadius: 6,
                padding: "10px 14px",
                textAlign: "center",
              }}
            >
              <div style={{ color, fontWeight: 700, fontSize: 20 }}>{count}</div>
              <div style={{ color: "#999", fontSize: 12 }}>{label}</div>
              <div style={{ color: "#666", fontSize: 11 }}>
                {Math.round((count / stats.total) * 100)}%
              </div>
            </div>
          ))}
        </div>

        {/* Recovery timeline histogram */}
        <h3>Recovery Timeline (Months Post-Fire)</h3>
        <div style={{ width: "100%", height: 220, marginBottom: 24 }}>
          <ResponsiveContainer>
            <BarChart data={stats.bins}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis
                dataKey="range"
                tick={{ fill: "#999", fontSize: 11 }}
                label={{
                  value: "Months post-fire",
                  position: "insideBottom",
                  offset: -2,
                  fill: "#666",
                  fontSize: 11,
                }}
              />
              <YAxis tick={{ fill: "#999", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: "#1a1a2e",
                  border: "1px solid #444",
                  borderRadius: 4,
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="algo" name="Algorithmic" fill="#4daf4a" />
              <Bar dataKey="llm" name="LLM" fill="#984ea3" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cumulative recovery curve */}
        <h3>Cumulative Recovery (% of Destroyed Parcels)</h3>
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={stats.cumulative}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis
                dataKey="month"
                tick={{ fill: "#999", fontSize: 11 }}
                label={{
                  value: "Months post-fire",
                  position: "insideBottom",
                  offset: -2,
                  fill: "#666",
                  fontSize: 11,
                }}
              />
              <YAxis
                tick={{ fill: "#999", fontSize: 11 }}
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "#1a1a2e",
                  border: "1px solid #444",
                  borderRadius: 4,
                  fontSize: 12,
                }}
                formatter={(value) => `${value}%`}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="algo"
                name="Algorithmic"
                stroke="#4daf4a"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="llm"
                name="LLM"
                stroke="#984ea3"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
