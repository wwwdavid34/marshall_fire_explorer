import { useQuery } from "@tanstack/react-query";
import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { CoherencePoint } from "../types";
import type { ParcelProperties } from "../types";
import { useMemo } from "react";

const FIRE_MONTHS = 0;

export function CoherenceChart({ parcel }: { parcel: ParcelProperties }) {
  const { data, isLoading } = useQuery<CoherencePoint[]>({
    queryKey: ["timeseries", parcel.ParcelNo],
    queryFn: () =>
      fetch(`/data/timeseries/${parcel.ParcelNo}.json`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const chartData = useMemo(() => {
    if (!data) return [];
    return data.map((d) => ({
      months: d.months_post_fire,
      mid_date: d.mid_date,
      norm_coh: d.norm_coh,
      smoothed: d.smoothed,
    }));
  }, [data]);

  if (isLoading)
    return <div style={{ color: "#888", padding: 8 }}>Loading...</div>;
  if (!data) return null;

  const isValid = String(parcel.smile_valid) === "True" || parcel.smile_valid === true;
  const recoveryMonths = parcel.recovery_months_post_fire;

  return (
    <div style={{ marginBottom: 16 }}>
      <strong style={{ fontSize: 13 }}>Coherence Time Series</strong>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart
          data={chartData}
          margin={{ top: 20, right: 8, bottom: 4, left: -10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis
            dataKey="months"
            type="number"
            tick={{ fontSize: 10, fill: "#888" }}
            tickFormatter={(v: number) => `${v.toFixed(0)}mo`}
            domain={["dataMin", "dataMax"]}
          />
          <YAxis
            domain={[0, 1.5]}
            tick={{ fontSize: 10, fill: "#888" }}
            label={{
              value: "γ / γ_Costco",
              angle: -90,
              position: "insideLeft",
              fontSize: 10,
              fill: "#888",
            }}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: "1px solid #444",
              fontSize: 12,
            }}
            labelFormatter={(v: number) => {
              const pt = chartData.find((d) => d.months === v);
              return pt ? `${pt.mid_date} (${v.toFixed(1)} mo)` : `${v.toFixed(1)} mo`;
            }}
          />
          <ReferenceLine
            x={FIRE_MONTHS}
            stroke="#e41a1c"
            strokeDasharray="4 2"
            label={{
              value: "Fire",
              fill: "#e41a1c",
              fontSize: 10,
              position: "top",
            }}
          />
          {recoveryMonths != null && (
            <ReferenceLine
              x={recoveryMonths}
              stroke={isValid ? "#4daf4a" : "#4daf4a55"}
              strokeDasharray="4 2"
              label={{
                value: isValid ? "Recovery" : "Recovery?",
                fill: isValid ? "#4daf4a" : "#4daf4a55",
                fontSize: 10,
                position: "top",
              }}
            />
          )}
          <Scatter
            dataKey="norm_coh"
            fill="#666"
            opacity={0.2}
            r={1}
            name="Raw"
          />
          <Line
            type="monotone"
            dataKey="smoothed"
            stroke="#1f77b4"
            dot={false}
            strokeWidth={2}
            connectNulls
            name="Wiener"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
