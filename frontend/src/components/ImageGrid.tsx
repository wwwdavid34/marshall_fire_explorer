import { useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";
import { useMemo } from "react";

const SLOTS = [
  { suffix: "pre", label: "Pre-fire" },
  { suffix: "post", label: "Post-fire" },
  { suffix: "17632", label: "Aug 2023" },
  { suffix: "48925", label: "Jul 2025" },
];

const CROP_BUFFER = 0.0002; // degrees, matches notebook download_parcel_crop

function ParcelOverlay({ parcelNo }: { parcelNo: string }) {
  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () => fetch("/data/parcels.geojson").then((r) => r.json()),
    staleTime: Infinity,
  });

  const svgPath = useMemo(() => {
    if (!parcels) return null;
    const feat = parcels.features.find(
      (f) => f.properties?.ParcelNo === parcelNo
    );
    if (!feat || feat.geometry.type !== "Polygon") return null;

    const coords = (feat.geometry as GeoJSON.Polygon).coordinates[0];
    const xs = coords.map((c) => c[0]);
    const ys = coords.map((c) => c[1]);
    const minx = Math.min(...xs) - CROP_BUFFER;
    const maxx = Math.max(...xs) + CROP_BUFFER;
    const miny = Math.min(...ys) - CROP_BUFFER;
    const maxy = Math.max(...ys) + CROP_BUFFER;
    const w = maxx - minx;
    const h = maxy - miny;

    // Map lon/lat to 0-100% SVG coordinates (lat is flipped: higher lat = top)
    const points = coords
      .map((c) => {
        const px = ((c[0] - minx) / w) * 100;
        const py = ((maxy - c[1]) / h) * 100;
        return `${px},${py}`;
      })
      .join(" ");

    return points;
  }, [parcels, parcelNo]);

  if (!svgPath) return null;

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    >
      <polygon
        points={svgPath}
        fill="none"
        stroke="#e41a1c"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function ImageGrid({ parcelNo }: { parcelNo: string }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <strong style={{ fontSize: 13 }}>ESRI Wayback Crops</strong>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 6,
          marginTop: 6,
        }}
      >
        {SLOTS.map(({ suffix, label }) => (
          <div key={suffix} style={{ textAlign: "center" }}>
            <div style={{ position: "relative", display: "inline-block", width: "100%" }}>
              <img
                src={`/data/crops/${parcelNo}_${suffix}.jpg`}
                alt={`${parcelNo} ${label}`}
                style={{
                  width: "100%",
                  display: "block",
                  borderRadius: 4,
                  border: "1px solid #333",
                }}
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
              <ParcelOverlay parcelNo={parcelNo} />
            </div>
            <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
