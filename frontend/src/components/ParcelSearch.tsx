import { useState, useMemo, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "../store";
import type { ParcelProperties } from "../types";
import type { FeatureCollection } from "geojson";

export function ParcelSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const setSelectedParcel = useStore((s) => s.setSelectedParcel);

  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () => fetch(`${import.meta.env.BASE_URL}data/parcels.geojson`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const allParcels = useMemo(() => {
    if (!parcels) return [];
    return parcels.features.map((f) => f.properties as ParcelProperties);
  }, [parcels]);

  const results = useMemo(() => {
    if (!query.trim() || query.length < 2) return [];
    const q = query.toLowerCase();
    return allParcels
      .filter((p) => {
        const addr = [p.StrNum, p.Street].filter(Boolean).join(" ").toLowerCase();
        return p.ParcelNo.toLowerCase().includes(q) || addr.includes(q);
      })
      .slice(0, 8);
  }, [query, allParcels]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function select(p: ParcelProperties) {
    setSelectedParcel(p);
    setQuery("");
    setOpen(false);
  }

  return (
    <div ref={ref} style={{ position: "relative", marginBottom: 12 }}>
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => query.length >= 2 && setOpen(true)}
        placeholder="Search parcel # or address..."
        style={{
          width: "100%",
          padding: "6px 10px",
          background: "#0d0d1a",
          border: "1px solid #444",
          borderRadius: 4,
          color: "#ddd",
          fontSize: 13,
          boxSizing: "border-box",
        }}
      />
      {open && results.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            background: "#1a1a2e",
            border: "1px solid #444",
            borderTop: "none",
            borderRadius: "0 0 4px 4px",
            zIndex: 100,
            maxHeight: 240,
            overflowY: "auto",
          }}
        >
          {results.map((p) => {
            const addr = [p.StrNum, p.Street].filter(Boolean).join(" ");
            return (
              <div
                key={p.ParcelNo}
                onClick={() => select(p)}
                style={{
                  padding: "6px 10px",
                  cursor: "pointer",
                  fontSize: 13,
                  borderBottom: "1px solid #2a2a3e",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "#2a2a4e")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
              >
                <span style={{ color: "#fff" }}>{p.ParcelNo}</span>
                {addr && (
                  <span style={{ color: "#888", marginLeft: 8 }}>{addr}</span>
                )}
                <span
                  style={{
                    color:
                      p.Condition === "Destroyed"
                        ? "#e41a1c"
                        : p.Condition === "Damaged"
                          ? "#ff7f00"
                          : "#4daf4a",
                    marginLeft: 8,
                    fontSize: 11,
                  }}
                >
                  {p.Condition}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
