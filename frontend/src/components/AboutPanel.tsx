export function AboutPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="about-overlay" onClick={onClose}>
      <div className="about-panel" onClick={(e) => e.stopPropagation()}>
        <button className="about-close" onClick={onClose}>
          &times;
        </button>

        <h2>About This Project</h2>

        <section>
          <h3>The Marshall Fire</h3>
          <p>
            On December 30, 2021, the Marshall Fire swept through Superior and
            Louisville, Colorado, destroying over 1,000 homes and damaging
            hundreds more. It was the most destructive wildfire in Colorado
            history by property loss. This tool tracks the recovery of affected
            parcels using satellite imagery and radar data.
          </p>
        </section>

        <section>
          <h3>What This Map Shows</h3>
          <p>
            The map displays approximately 1,950 parcels assessed after the
            fire, colored by damage classification:
          </p>
          <ul>
            <li>
              <span style={{ color: "#e41a1c", fontWeight: 600 }}>Red</span> —
              Destroyed (1,111 parcels)
            </li>
            <li>
              <span style={{ color: "#ff7f00", fontWeight: 600 }}>Orange</span>{" "}
              — Damaged (369 parcels)
            </li>
            <li>
              <span style={{ color: "#4daf4a", fontWeight: 600 }}>Green</span> —
              Unaffected (470 parcels)
            </li>
          </ul>
          <p>
            Click any parcel to see its radar coherence time series and
            satellite imagery across four time periods.
          </p>
        </section>

        <section>
          <h3>How Recovery Is Detected</h3>
          <p>
            We use Sentinel-1 radar (InSAR coherence) to measure structural
            stability over time. Each parcel's coherence is normalized against a
            stable reference target (the Costco parking lot nearby) to remove
            weather and atmospheric effects.
          </p>
          <p>
            Before smoothing, anomalous acquisitions (weather events, orbit
            errors) are flagged and removed using Median Absolute Deviation
            (MAD) outlier rejection. Observations are then weighted by
            coherence-derived variance (Touzi et al. 1999) — low-coherence
            measurements get downweighted — before Wiener filtering.
          </p>
          <p>
            <strong>Algorithmic detection</strong> (green line): Recovery is
            detected when the smoothed coherence crosses back above 90% of its
            pre-fire baseline (capped at 1.05 for high-baseline parcels) and
            stays there for at least 60 days. Only parcels with validated
            destruction patterns are eligible.
          </p>
          <p>
            <strong>LLM detection</strong> (purple line): An AI model (Claude
            Sonnet) reviews each parcel's full-resolution smoothed coherence
            time series, constrained by building permit issuance dates, and
            identifies the inflection point where sustained recovery begins
            after construction is authorized.
          </p>
        </section>

        <section>
          <h3>The Smile Test</h3>
          <p>
            Not all parcels labeled "Destroyed" show real structural damage in
            the radar signal. Vegetation, open land, and large lots can be
            misclassified. We fit a quadratic curve to each parcel's post-fire
            coherence — a genuine destruction-and-rebuild creates a
            characteristic U-shaped "smile" pattern (dip then recovery).
          </p>
          <p>
            A 200-iteration bootstrap provides a 95% confidence interval on the
            curvature estimate. Parcels where the entire CI exceeds the
            threshold show the recovery line in solid green. Parcels with weak
            or uncertain curvature show a dimmed "Recovery?" line.
          </p>
        </section>

        <section>
          <h3>Data Sources</h3>
          <ul>
            <li>
              <strong>Sentinel-1 SAR</strong> — European Space Agency, 12-day
              revisit C-band radar via OPERA CSLC products
            </li>
            <li>
              <strong>ESRI Wayback Imagery</strong> — High-resolution satellite
              photos at four time points (pre-fire, post-fire, Aug 2023, Jul
              2025)
            </li>
            <li>
              <strong>Parcel boundaries &amp; damage assessments</strong> —
              Boulder County open data
            </li>
          </ul>
        </section>

        <section>
          <h3>Limitations</h3>
          <ul>
            <li>
              C-band radar is sensitive to vegetation, which adds noise to
              coherence measurements on tree-covered parcels. L-band radar would
              reduce this but no open L-band data exists for this time period.
            </li>
            <li>
              Sentinel-1 pixel resolution (5 &times; 10m) can be larger than
              small structures, blending building and ground signals.
            </li>
            <li>
              The quadratic "smile" model works well for typical 18–36 month
              rebuilds but can misclassify very fast recoveries (&lt;12 months)
              whose early completion creates a downward-trending tail.
            </li>
            <li>
              Recovery detection relies on coherence returning to pre-fire
              levels, which may not occur if the new structure differs
              significantly from the original.
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
