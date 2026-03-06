import { useEffect, useState } from "react";
import { useStore } from "../store";
import { ParcelInfo } from "./ParcelInfo";
import { CoherenceChart } from "./CoherenceChart";
import { ImageGrid } from "./ImageGrid";

export function DetailPanel() {
  const selectedParcel = useStore((s) => s.selectedParcel);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Auto-open drawer when a parcel is selected
  useEffect(() => {
    if (selectedParcel) setDrawerOpen(true);
  }, [selectedParcel]);

  const sidebarClass = `sidebar${drawerOpen ? " open" : ""}`;
  const toggleClass = `sidebar-toggle${drawerOpen ? " drawer-open" : ""}`;

  if (!selectedParcel) {
    return (
      <>
        <div className={sidebarClass}>
          <div style={{ color: "#666", fontStyle: "italic", padding: 16 }}>
            Click a parcel on the map or search to view details.
          </div>
        </div>
        <button
          className={toggleClass}
          onClick={() => setDrawerOpen((v) => !v)}
        >
          {drawerOpen ? "▼ Close" : "▲ Details"}
        </button>
      </>
    );
  }

  return (
    <>
      <div className={sidebarClass}>
        <ParcelInfo parcel={selectedParcel} />
        <CoherenceChart parcel={selectedParcel} />
        <ImageGrid parcelNo={selectedParcel.ParcelNo} />
      </div>
      <button
        className={toggleClass}
        onClick={() => setDrawerOpen((v) => !v)}
      >
        {drawerOpen ? "▼ Close" : "▲ Details"}
      </button>
    </>
  );
}
