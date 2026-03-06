import { useState } from "react";
import { AboutPanel } from "./AboutPanel";

export function TitleBar() {
  const [showAbout, setShowAbout] = useState(false);

  return (
    <>
      <div className="title-bar">
        <span className="title-bar-text">Marshall Fire Parcel Explorer</span>
        <button
          className="about-button"
          onClick={() => setShowAbout((v) => !v)}
        >
          {showAbout ? "Close" : "About"}
        </button>
      </div>
      {showAbout && <AboutPanel onClose={() => setShowAbout(false)} />}
    </>
  );
}
