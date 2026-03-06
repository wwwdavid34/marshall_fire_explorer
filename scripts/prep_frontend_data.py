"""Prepare static data files for the Marshall Fire Parcel Explorer frontend.

Thin wrapper around pipeline.output.frontend_data.generate_frontend_data().
Run: .venv/bin/python scripts/prep_frontend_data.py
"""

import logging

from pipeline.output.frontend_data import generate_frontend_data

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    generate_frontend_data()
