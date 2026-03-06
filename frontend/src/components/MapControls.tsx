import { useStore } from "../store";
import { ParcelSearch } from "./ParcelSearch";
import { FilterControls } from "./FilterControls";

export function MapControls() {
  const showAbout = useStore((s) => s.showAbout);

  if (showAbout) return null;

  return (
    <div className="map-controls">
      <ParcelSearch />
      <FilterControls />
    </div>
  );
}
