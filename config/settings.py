"""Environment configuration for dev (LocalStack) and prod (Cloudflare R2)."""

import os
from dataclasses import dataclass

import boto3
from dotenv import load_dotenv

load_dotenv()


@dataclass
class EnvironmentConfig:
    s3_endpoint_url: str
    data_bucket: str
    data_base_url: str
    r2_account_id: str | None = None


CONFIGS = {
    "dev": EnvironmentConfig(
        s3_endpoint_url="http://localhost:4566",
        data_bucket="dm-dev-data",
        data_base_url="http://localhost:4566/dm-dev-data",
    ),
    "prod": EnvironmentConfig(
        s3_endpoint_url=f"https://{os.getenv('CF_ACCOUNT_ID', '')}.r2.cloudflarestorage.com",
        data_bucket="dm-prod-data",
        data_base_url="https://marshallfire.yourdomain.com/data",
        r2_account_id=os.getenv("CF_ACCOUNT_ID"),
    ),
}

AOI = [-105.23, 39.915, -105.12, 39.98]

OBSERVATION_DATES = ["2021-11", "2022-01", "2022-06", "2023-06", "2024-06"]


def get_config(env: str | None = None) -> EnvironmentConfig:
    env = env or os.getenv("DEPLOY_ENV", "dev")
    return CONFIGS[env]


def get_s3_client(config: EnvironmentConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint_url,
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    )
