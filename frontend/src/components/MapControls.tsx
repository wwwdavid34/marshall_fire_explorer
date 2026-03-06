import { ParcelSearch } from "./ParcelSearch";
import { FilterControls } from "./FilterControls";

export function MapControls() {
  return (
    <div className="map-controls">
      <ParcelSearch />
      <FilterControls />
    </div>
  );
}
