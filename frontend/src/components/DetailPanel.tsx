import { useStore } from "../store";
import { ParcelInfo } from "./ParcelInfo";
import { CoherenceChart } from "./CoherenceChart";
import { ImageGrid } from "./ImageGrid";

export function DetailPanel() {
  const selectedParcel = useStore((s) => s.selectedParcel);

  if (!selectedParcel) {
    return (
      <div className="sidebar">
        <div style={{ color: "#666", fontStyle: "italic", padding: 16 }}>
          Click a parcel on the map or search to view details.
        </div>
      </div>
    );
  }

  return (
    <div className="sidebar">
      <ParcelInfo parcel={selectedParcel} />
      <CoherenceChart parcel={selectedParcel} />
      <ImageGrid parcelNo={selectedParcel.ParcelNo} />
    </div>
  );
}
