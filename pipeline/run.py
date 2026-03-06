"""Single entry point for the Marshall Fire pipeline.

Pipeline stages:
  1. Acquire   — Download CSLC from ASF, Landsat from Planetary Computer, verify parcels
  2. Process   — Compute InSAR coherence pairs, Landsat indices (dNBR, NDVI)
  3. Analyze   — Curvature validation ("smile test"), recovery detection (Wiener + sustain)
  4. Output    — Generate static frontend data (GeoJSON, timeseries JSON, crops)

Run: uv run python pipeline/run.py [--skip-acquisition] [--skip-processing] [--skip-analysis]
"""

import logging

import click

from pipeline.acquire.landsat import acquire_landsat
from pipeline.acquire.parcels import acquire_parcels
from pipeline.acquire.sentinel1 import acquire_sentinel1
from pipeline.analyze.curvature import run_curvature_analysis
from pipeline.analyze.recovery import run_recovery_detection
from pipeline.output.frontend_data import generate_frontend_data
from pipeline.process.coherence import process_coherence
from pipeline.process.landsat import process_landsat

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@click.command()
@click.option("--skip-acquisition", is_flag=True, help="Skip data download step")
@click.option("--skip-processing", is_flag=True, help="Skip coherence/Landsat processing step")
@click.option("--skip-analysis", is_flag=True, help="Skip curvature + recovery detection step")
@click.option("--skip-output", is_flag=True, help="Skip frontend data generation step")
@click.option("--include-landsat", is_flag=True, help="Include Landsat acquisition and processing (off by default)")
def run_pipeline(
    skip_acquisition: bool,
    skip_processing: bool,
    skip_analysis: bool,
    skip_output: bool,
    include_landsat: bool,
) -> None:
    """Run the Marshall Fire InSAR recovery pipeline end to end."""
    logger.info("Starting pipeline")

    # 1. Acquire
    if not skip_acquisition:
        acquire_sentinel1()
        if include_landsat:
            acquire_landsat()
        acquire_parcels()
    else:
        logger.info("Skipping acquisition")

    # 2. Process
    if not skip_processing:
        process_coherence()
        if include_landsat:
            process_landsat()
    else:
        logger.info("Skipping processing")

    # 3. Analyze
    if not skip_analysis:
        run_curvature_analysis()
        run_recovery_detection()
    else:
        logger.info("Skipping analysis")

    # 4. Output
    if not skip_output:
        generate_frontend_data()
    else:
        logger.info("Skipping output")

    logger.info("Pipeline complete")


if __name__ == "__main__":
    run_pipeline()
