import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "../store";
import type { ParcelProperties } from "../types";
import type { Feature, FeatureCollection } from "geojson";
import type { Layer, PathOptions } from "leaflet";
import { useMemo } from "react";

const WAYBACK_BASE = "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile";

const BASE_LAYERS: Record<string, { url: string; attribution: string; maxZoom: number }> = {
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "ESRI",
    maxZoom: 19,
  },
  "pre-fire": {
    url: `${WAYBACK_BASE}/26120/{z}/{y}/{x}`,
    attribution: "ESRI Wayback — Pre-fire",
    maxZoom: 19,
  },
  "post-fire": {
    url: `${WAYBACK_BASE}/7110/{z}/{y}/{x}`,
    attribution: "ESRI Wayback — Post-fire",
    maxZoom: 19,
  },
  "aug-2023": {
    url: `${WAYBACK_BASE}/17632/{z}/{y}/{x}`,
    attribution: "ESRI Wayback — Aug 2023",
    maxZoom: 19,
  },
};

const CONDITION_COLORS: Record<string, string> = {
  Destroyed: "#e41a1c",
  Damaged: "#ff7f00",
  Unaffected: "#4daf4a",
};

export function ParcelMap() {
  const { damageClasses, recoveryFilter, baseLayer, selectedParcel, setSelectedParcel } =
    useStore();

  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () => fetch(`${import.meta.env.BASE_URL}data/parcels.geojson`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const { data: perimeter } = useQuery<FeatureCollection>({
    queryKey: ["perimeter"],
    queryFn: () => fetch(`${import.meta.env.BASE_URL}data/perimeter.geojson`).then((r) => r.json()),
    staleTime: Infinity,
  });

  const filtered = useMemo(() => {
    if (!parcels) return null;
    const features = parcels.features.filter((f) => {
      const p = f.properties as ParcelProperties;
      if (!damageClasses.has(p.Condition)) return false;
      if (recoveryFilter === "recovered" && !p.recovery_date) return false;
      if (recoveryFilter === "not-recovered" && p.recovery_date) return false;
      return true;
    });
    return { ...parcels, features };
  }, [parcels, damageClasses, recoveryFilter]);

  const selectedFeature = useMemo(() => {
    if (!selectedParcel || !parcels) return null;
    const feat = parcels.features.find(
      (f) => f.properties?.ParcelNo === selectedParcel.ParcelNo
    );
    if (!feat) return null;
    return { type: "FeatureCollection" as const, features: [feat] };
  }, [selectedParcel, parcels]);

  const filterKey = `${[...damageClasses].sort().join(",")}-${recoveryFilter}`;

  function style(feature?: Feature): PathOptions {
    const condition = feature?.properties?.Condition ?? "Unaffected";
    return {
      color: CONDITION_COLORS[condition] ?? "#999",
      weight: 1.5,
      opacity: 0.8,
      fillColor: CONDITION_COLORS[condition] ?? "#999",
      fillOpacity: 0.4,
    };
  }

  function onEachFeature(feature: Feature, layer: Layer) {
    layer.on("click", () => {
      setSelectedParcel(feature.properties as ParcelProperties);
    });
  }

  return (
    <MapContainer
      center={[39.9597, -105.1742]}
      zoom={14}
      className="map-container"
    >
      <TileLayer
        key={baseLayer}
        url={BASE_LAYERS[baseLayer].url}
        attribution={BASE_LAYERS[baseLayer].attribution}
        maxZoom={BASE_LAYERS[baseLayer].maxZoom}
      />
      {perimeter && (
        <GeoJSON
          data={perimeter}
          style={{ color: "#4a90d9", weight: 2, fillOpacity: 0, dashArray: "6 3" }}
        />
      )}
      {filtered && (
        <GeoJSON
          key={filterKey}
          data={filtered}
          style={style}
          onEachFeature={onEachFeature}
        />
      )}
      {selectedFeature && (
        <GeoJSON
          key={`selected-${selectedParcel?.ParcelNo}`}
          data={selectedFeature}
          style={{
            color: "#00ffff",
            weight: 3,
            opacity: 1,
            fillColor: "#00ffff",
            fillOpacity: 0.25,
          }}
        />
      )}
    </MapContainer>
  );
}
