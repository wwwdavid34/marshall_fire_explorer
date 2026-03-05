"""Single entry point for the Marshall Fire pipeline."""

import logging
import subprocess
from pathlib import Path

import click

from pipeline.acquire.landsat import acquire_landsat
from pipeline.acquire.lidar import acquire_lidar
from pipeline.acquire.parcels_permits import acquire_parcels_permits
from pipeline.acquire.sentinel1 import acquire_sentinel1
from pipeline.output.parcel_json import write_parcel_json
from pipeline.output.registry import write_registry_json
from pipeline.output.timeline_json import write_timeline_json
from pipeline.process.landsat import process_landsat
from pipeline.process.lidar import process_lidar
from pipeline.process.sar import process_sar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_dbt() -> None:
    """Run dbt models to build the DuckDB mart from zonal stats parquet."""
    logger.info("run_dbt: executing dbt run")
    dbt_dir = Path("dbt")
    if not dbt_dir.exists():
        logger.warning("run_dbt: dbt/ directory not found — skipping")
        return
    try:
        result = subprocess.run(
            ["dbt", "run", "--profiles-dir", str(dbt_dir), "--project-dir", str(dbt_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("run_dbt: dbt run succeeded")
        else:
            logger.warning("run_dbt: dbt run failed:\n%s", result.stderr[:500])
    except FileNotFoundError:
        logger.warning("run_dbt: dbt not installed — skipping (pip install dbt-duckdb)")
    except subprocess.TimeoutExpired:
        logger.error("run_dbt: dbt run timed out")


def run_damage_inference() -> None:
    logger.info("run_damage_inference: loading weights and running damage model")
    logger.info("run_damage_inference: not yet implemented — skipping")


def run_rebuild_inference() -> None:
    logger.info("run_rebuild_inference: loading weights and running rebuild model")
    logger.info("run_rebuild_inference: not yet implemented — skipping")


@click.command()
@click.option("--skip-acquisition", is_flag=True, help="Skip data download step")
@click.option("--skip-processing", is_flag=True, help="Skip raster processing step")
@click.option("--skip-ml", is_flag=True, help="Skip ML inference step")
@click.option("--env", default="dev", type=click.Choice(["dev", "prod"]), help="Target environment")
def run_pipeline(skip_acquisition: bool, skip_processing: bool, skip_ml: bool, env: str) -> None:
    """Run the Marshall Fire data pipeline end to end."""
    logger.info("Starting pipeline (env=%s)", env)

    if not skip_acquisition:
        acquire_sentinel1()
        acquire_landsat()
        acquire_lidar()
        acquire_parcels_permits()
    else:
        logger.info("Skipping acquisition")

    if not skip_processing:
        process_sar()
        process_landsat()
        process_lidar()
    else:
        logger.info("Skipping processing")

    run_dbt()

    if not skip_ml:
        run_damage_inference()
        run_rebuild_inference()
    else:
        logger.info("Skipping ML inference")

    write_parcel_json()
    write_timeline_json()
    write_registry_json()

    logger.info("Pipeline complete")


if __name__ == "__main__":
    run_pipeline()
