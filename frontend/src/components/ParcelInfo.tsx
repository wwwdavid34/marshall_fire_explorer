import { useState } from "react";
import type { ParcelProperties } from "../types";

const BADGE_COLORS: Record<string, string> = {
  Destroyed: "#e41a1c",
  Damaged: "#ff7f00",
  Unaffected: "#4daf4a",
};

const CURVATURE_HINT =
  "Smile curvature measures the U-shape of post-fire InSAR coherence. " +
  "Values ≥ 2.0 indicate a genuine destruction-recovery pattern; " +
  "lower values suggest vegetation or misclassification.";

export function ParcelInfo({ parcel }: { parcel: ParcelProperties }) {
  const address = [parcel.StrNum, parcel.Street].filter(Boolean).join(" ") || "—";
  const recoveryStr = parcel.recovery_date
    ? `${parcel.recovery_date.slice(0, 7)} (${parcel.recovery_months_post_fire?.toFixed(0)} mo)`
    : "Not recovered";

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
      {parcel.smile_curvature != null && (
        <CurvatureRow parcel={parcel} />
      )}
    </div>
  );
}

function CurvatureRow({ parcel }: { parcel: ParcelProperties }) {
  const [showHint, setShowHint] = useState(false);
  const isValid = String(parcel.smile_valid) === "True" || parcel.smile_valid === true;

  return (
    <div style={{ fontSize: 13, color: "#aaa", marginTop: 2 }}>
      <span>Curvature: {parcel.smile_curvature!.toFixed(1)}</span>
      <button
        onClick={() => setShowHint((v) => !v)}
        title={CURVATURE_HINT}
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
      {!isValid && (
        <span style={{ color: "#ff7f00", marginLeft: 6 }}>below threshold</span>
      )}
      {showHint && (
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
          {CURVATURE_HINT}
        </div>
      )}
    </div>
  );
}
