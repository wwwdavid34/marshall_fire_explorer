import { useStore } from "../store";
import { useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";
import type { ParcelProperties } from "../types";
import { useMemo } from "react";

const CLASSES = ["Destroyed", "Damaged", "Unaffected"] as const;
const CLASS_COLORS: Record<string, string> = {
  Destroyed: "#e41a1c",
  Damaged: "#ff7f00",
  Unaffected: "#4daf4a",
};

export function FilterControls() {
  const { damageClasses, toggleDamageClass, recoveryFilter, setRecoveryFilter } =
    useStore();

  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () => fetch(`${import.meta.env.BASE_URL}data/parcels.geojson`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const counts = useMemo(() => {
    if (!parcels) return {} as Record<string, number>;
    const c: Record<string, number> = {};
    for (const f of parcels.features) {
      const p = f.properties as ParcelProperties;
      c[p.Condition] = (c[p.Condition] ?? 0) + 1;
    }
    return c;
  }, [parcels]);

  const visibleCount = useMemo(() => {
    if (!parcels) return 0;
    return parcels.features.filter((f) => {
      const p = f.properties as ParcelProperties;
      if (!damageClasses.has(p.Condition)) return false;
      if (recoveryFilter === "recovered" && !p.recovery_date) return false;
      if (recoveryFilter === "not-recovered" && p.recovery_date) return false;
      return true;
    }).length;
  }, [parcels, damageClasses, recoveryFilter]);

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ marginBottom: 8 }}>
        <strong>Damage Class</strong>
        {CLASSES.map((cls) => (
          <label key={cls} style={{ display: "block", margin: "4px 0", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={damageClasses.has(cls)}
              onChange={() => toggleDamageClass(cls)}
            />{" "}
            <span style={{ color: CLASS_COLORS[cls], fontWeight: 600 }}>{cls}</span>
            <span style={{ color: "#888", marginLeft: 4 }}>({counts[cls] ?? 0})</span>
          </label>
        ))}
      </div>

      <div style={{ marginBottom: 8 }}>
        <strong>Recovery</strong>
        {(["all", "recovered", "not-recovered"] as const).map((val) => (
          <label key={val} style={{ display: "block", margin: "4px 0", cursor: "pointer" }}>
            <input
              type="radio"
              name="recovery"
              checked={recoveryFilter === val}
              onChange={() => setRecoveryFilter(val)}
            />{" "}
            {val === "all" ? "All" : val === "recovered" ? "Recovered" : "Not recovered"}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: 8 }}>
        <strong>Legend</strong>
        <div style={{ display: "flex", alignItems: "center", margin: "4px 0" }}>
          <svg width={24} height={12} style={{ marginRight: 6, flexShrink: 0 }}>
            <line x1={0} y1={6} x2={24} y2={6} stroke="#4a90d9" strokeWidth={2} strokeDasharray="6 3" />
          </svg>
          <span style={{ fontSize: 13 }}>Fire perimeter</span>
        </div>
      </div>

      <div style={{ color: "#888", fontSize: 12 }}>
        Showing {visibleCount} parcels
      </div>
    </div>
  );
}
