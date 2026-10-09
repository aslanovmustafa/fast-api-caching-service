from pathlib import Path

from pydantic import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_")

    data_dir: Path = Path("data")