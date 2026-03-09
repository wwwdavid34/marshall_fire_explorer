import { useState } from "react";
import type { ParcelProperties } from "../types";

const BADGE_COLORS: Record<string, string> = {
  Destroyed: "#e41a1c",
  Damaged: "#ff7f00",
  Unaffected: "#4daf4a",
};

const LLM_HINT =
  "An AI model (Claude Sonnet) reviews the full-resolution smoothed coherence " +
  "time series, constrained by building permit dates, and identifies the inflection " +
  "point where sustained recovery begins after construction is authorized.";

const CURVATURE_HINT =
  "Smile curvature measures the U-shape of post-fire InSAR coherence. " +
  "Values ≥ 2.0 indicate a genuine destruction-recovery pattern; " +
  "lower values suggest vegetation or misclassification.";

function HintButton({ hint }: { hint: string }) {
  const [show, setShow] = useState(false);
  return (
    <>
      <button
        onClick={() => setShow((v) => !v)}
        title={hint}
        style={{
          background: "none",
          border: "1px solid #555",
          color: "#888",
          borderRadius: "50%",
          width: 16,
          height: 16,
          fontSize: 10,
          lineHeight: "14px",
          textAlign: "center",
          cursor: "pointer",
          marginLeft: 6,
          padding: 0,
          verticalAlign: "middle",
        }}
      >
        ?
      </button>
      {show && (
        <div
          style={{
            marginTop: 4,
            padding: "6px 8px",
            background: "#0d0d1a",
            border: "1px solid #444",
            borderRadius: 4,
            fontSize: 12,
            color: "#bbb",
            lineHeight: 1.5,
          }}
        >
          {hint}
        </div>
      )}
    </>
  );
}

export function ParcelInfo({ parcel }: { parcel: ParcelProperties }) {
  const address = [parcel.StrNum, parcel.Street].filter(Boolean).join(" ") || "—";
  const recoveryStr = parcel.recovery_date
    ? `${parcel.recovery_date.slice(0, 7)} (${parcel.recovery_months_post_fire?.toFixed(0)} mo)`
    : "Not recovered";
  const llmStr = (() => {
    if (parcel.recovery_llm == null) return "Not detected";
    const fireDate = new Date(2021, 11, 30); // Dec 30, 2021
    const llmDate = new Date(fireDate.getTime() + parcel.recovery_llm * 30.44 * 86400000);
    const dateStr = `${llmDate.getFullYear()}-${String(llmDate.getMonth() + 1).padStart(2, "0")}`;
    return `${dateStr} (${parcel.recovery_llm.toFixed(0)} mo)`;
  })();

  return (
    <div style={{ marginBottom: 16 }}>
      <h2 style={{ margin: "0 0 4px" }}>Parcel {parcel.ParcelNo}</h2>
      <div style={{ marginBottom: 4 }}>{address}</div>
      <div style={{ marginBottom: 4 }}>
        <span
          style={{
            background: BADGE_COLORS[parcel.Condition] ?? "#666",
            color: "#fff",
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {parcel.Condition}
        </span>
      </div>
      <div style={{ fontSize: 13, color: "#aaa" }}>
        Recovery: {recoveryStr}
      </div>
      <div style={{ fontSize: 13, color: "#c084fc" }}>
        LLM estimate: {llmStr}
        <HintButton hint={LLM_HINT} />
      </div>
      {parcel.smile_curvature != null && (
        <CurvatureRow parcel={parcel} />
      )}
    </div>
  );
}

function CurvatureRow({ parcel }: { parcel: ParcelProperties }) {
  const isValid = String(parcel.smile_valid) === "True" || parcel.smile_valid === true;

  return (
    <div style={{ fontSize: 13, color: "#aaa", marginTop: 2 }}>
      <span>Curvature: {parcel.smile_curvature!.toFixed(1)}</span>
      <HintButton hint={CURVATURE_HINT} />
      {!isValid && (
        <span style={{ color: "#ff7f00", marginLeft: 6 }}>below threshold</span>
      )}
    </div>
  );
}
