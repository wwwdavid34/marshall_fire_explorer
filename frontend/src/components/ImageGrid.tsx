import { useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";

const SLOTS = [
  { release: 26120, label: "Pre-fire" },
  { release: 7110, label: "Post-fire" },
  { release: 17632, label: "Aug 2023" },
  { release: 48925, label: "Jul 2025" },
];

const CROP_BUFFER = 0.0002; // degrees — matches original notebook crops
const ZOOM = 19;
const TILE_SIZE = 256;

/** Convert longitude to tile X at given zoom */
function lonToTileX(lon: number, z: number): number {
  return Math.floor(((lon + 180) / 360) * 2 ** z);
}

/** Convert latitude to tile Y at given zoom */
function latToTileY(lat: number, z: number): number {
  const rad = (lat * Math.PI) / 180;
  return Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * 2 ** z
  );
}

/** Extract all coordinates from a Polygon or MultiPolygon geometry */
function extractCoords(geometry: GeoJSON.Geometry): number[][] {
  if (geometry.type === "Polygon") {
    return (geometry as GeoJSON.Polygon).coordinates[0];
  }
  if (geometry.type === "MultiPolygon") {
    return (geometry as GeoJSON.MultiPolygon).coordinates.flatMap(
      (poly) => poly[0]
    );
  }
  return [];
}

/** Convert longitude to fractional pixel X within tile grid */
function lonToPixelX(lon: number, z: number): number {
  return ((lon + 180) / 360) * 2 ** z * TILE_SIZE;
}

/** Convert latitude to fractional pixel Y within tile grid */
function latToPixelY(lat: number, z: number): number {
  const rad = (lat * Math.PI) / 180;
  return (
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) *
    2 ** z *
    TILE_SIZE
  );
}

interface CropResult {
  dataUrl: string;
  width: number;
  height: number;
}

async function fetchCrop(
  bbox: [number, number, number, number],
  release: number
): Promise<CropResult> {
  const [minLon, minLat, maxLon, maxLat] = bbox;

  const txMin = lonToTileX(minLon, ZOOM);
  const txMax = lonToTileX(maxLon, ZOOM);
  const tyMin = latToTileY(maxLat, ZOOM); // note: higher lat = lower tile Y
  const tyMax = latToTileY(minLat, ZOOM);

  const cols = txMax - txMin + 1;
  const rows = tyMax - tyMin + 1;

  // Fetch all tiles in parallel
  const tilePromises: Promise<{ img: HTMLImageElement; col: number; row: number }>[] = [];
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const ty = tyMin + row;
      const tx = txMin + col;
      const url = `https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/${release}/${ZOOM}/${ty}/${tx}`;
      tilePromises.push(
        new Promise((resolve, reject) => {
          const img = new Image();
          img.crossOrigin = "anonymous";
          img.onload = () => resolve({ img, col, row });
          img.onerror = () => reject(new Error(`Tile ${tx},${ty} failed`));
          img.src = url;
        })
      );
    }
  }

  const tiles = await Promise.all(tilePromises);

  // Composite tiles onto a full canvas
  const fullCanvas = document.createElement("canvas");
  fullCanvas.width = cols * TILE_SIZE;
  fullCanvas.height = rows * TILE_SIZE;
  const ctx = fullCanvas.getContext("2d")!;
  for (const { img, col, row } of tiles) {
    ctx.drawImage(img, col * TILE_SIZE, row * TILE_SIZE);
  }

  // Compute pixel offsets for the crop within the tile grid
  const gridOriginX = txMin * TILE_SIZE;
  const gridOriginY = tyMin * TILE_SIZE;

  const cropX = lonToPixelX(minLon, ZOOM) - gridOriginX;
  const cropY = latToPixelY(maxLat, ZOOM) - gridOriginY;
  const cropW = lonToPixelX(maxLon, ZOOM) - lonToPixelX(minLon, ZOOM);
  const cropH = latToPixelY(minLat, ZOOM) - latToPixelY(maxLat, ZOOM);

  // Extract the cropped region
  const cropCanvas = document.createElement("canvas");
  cropCanvas.width = Math.round(cropW);
  cropCanvas.height = Math.round(cropH);
  const cropCtx = cropCanvas.getContext("2d")!;
  cropCtx.drawImage(
    fullCanvas,
    Math.round(cropX),
    Math.round(cropY),
    Math.round(cropW),
    Math.round(cropH),
    0,
    0,
    Math.round(cropW),
    Math.round(cropH)
  );

  return {
    dataUrl: cropCanvas.toDataURL("image/jpeg", 0.85),
    width: Math.round(cropW),
    height: Math.round(cropH),
  };
}

function ParcelOverlay({ parcelNo }: { parcelNo: string }) {
  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () =>
      fetch(`${import.meta.env.BASE_URL}data/parcels.geojson`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const svgPath = useMemo(() => {
    if (!parcels) return null;
    const feat = parcels.features.find(
      (f) => f.properties?.ParcelNo === parcelNo
    );
    if (!feat) return null;
    const coords = extractCoords(feat.geometry);
    if (coords.length === 0) return null;

    const xs = coords.map((c) => c[0]);
    const ys = coords.map((c) => c[1]);
    const minx = Math.min(...xs) - CROP_BUFFER;
    const maxx = Math.max(...xs) + CROP_BUFFER;
    const miny = Math.min(...ys) - CROP_BUFFER;
    const maxy = Math.max(...ys) + CROP_BUFFER;
    const w = maxx - minx;
    const h = maxy - miny;

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

function WaybackCrop({
  parcelNo,
  release,
  label,
  bbox,
}: {
  parcelNo: string;
  release: number;
  label: string;
  bbox: [number, number, number, number];
}) {
  const [crop, setCrop] = useState<CropResult | null>(null);
  const [error, setError] = useState(false);
  const prevKey = useRef("");

  useEffect(() => {
    const key = `${parcelNo}-${release}`;
    if (key === prevKey.current) return;
    prevKey.current = key;
    setCrop(null);
    setError(false);
    fetchCrop(bbox, release)
      .then(setCrop)
      .catch(() => setError(true));
  }, [parcelNo, release, bbox]);

  return (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          position: "relative",
          display: "inline-block",
          width: "100%",
          minHeight: 80,
          background: "#111",
          borderRadius: 4,
          border: "1px solid #333",
          overflow: "hidden",
        }}
      >
        {!crop && !error && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: 80,
              color: "#666",
              fontSize: 11,
            }}
          >
            Loading...
          </div>
        )}
        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: 80,
              color: "#666",
              fontSize: 11,
            }}
          >
            Failed to load
          </div>
        )}
        {crop && (
          <>
            <img
              src={crop.dataUrl}
              alt={`${parcelNo} ${label}`}
              style={{ width: "100%", display: "block" }}
            />
            <ParcelOverlay parcelNo={parcelNo} />
          </>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{label}</div>
    </div>
  );
}

export function ImageGrid({ parcelNo }: { parcelNo: string }) {
  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () =>
      fetch(`${import.meta.env.BASE_URL}data/parcels.geojson`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const bbox = useMemo<[number, number, number, number] | null>(() => {
    if (!parcels) return null;
    const feat = parcels.features.find(
      (f) => f.properties?.ParcelNo === parcelNo
    );
    if (!feat) return null;
    const coords = extractCoords(feat.geometry);
    if (coords.length === 0) return null;

    const xs = coords.map((c) => c[0]);
    const ys = coords.map((c) => c[1]);
    return [
      Math.min(...xs) - CROP_BUFFER,
      Math.min(...ys) - CROP_BUFFER,
      Math.max(...xs) + CROP_BUFFER,
      Math.max(...ys) + CROP_BUFFER,
    ];
  }, [parcels, parcelNo]);

  if (!bbox) return null;

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
        {SLOTS.map(({ release, label }) => (
          <WaybackCrop
            key={release}
            parcelNo={parcelNo}
            release={release}
            label={label}
            bbox={bbox}
          />
        ))}
      </div>
    </div>
  );
}
