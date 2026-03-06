import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "../store";
import type { ParcelProperties } from "../types";
import type { Feature, FeatureCollection } from "geojson";
import type { Layer, PathOptions } from "leaflet";
import { useMemo } from "react";

const CONDITION_COLORS: Record<string, string> = {
  Destroyed: "#e41a1c",
  Damaged: "#ff7f00",
  Unaffected: "#4daf4a",
};

export function ParcelMap() {
  const { damageClasses, recoveryFilter, selectedParcel, setSelectedParcel } =
    useStore();

  const { data: parcels } = useQuery<FeatureCollection>({
    queryKey: ["parcels"],
    queryFn: () => fetch("/data/parcels.geojson").then((r) => r.json()),
    staleTime: Infinity,
  });

  const { data: perimeter } = useQuery<FeatureCollection>({
    queryKey: ["perimeter"],
    queryFn: () => fetch("/data/perimeter.geojson").then((r) => r.json()),
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
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attribution="ESRI"
        maxZoom={19}
      />
      {perimeter && (
        <GeoJSON
          data={perimeter}
          style={{ color: "#e41a1c", weight: 2, fillOpacity: 0, dashArray: "6 3" }}
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
