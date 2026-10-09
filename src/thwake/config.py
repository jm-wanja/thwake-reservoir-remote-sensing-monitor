"""Load project configuration from ``config/*.yaml`` and environment variables from ``.env``.

Every YAML file in the config directory is loaded and exposed under its file stem, e.g.
``config/thresholds.yaml`` becomes ``cfg.files["thresholds"]``. The three files the pipeline
needs (``settings``, ``ee_collections``, ``thresholds``) are also available as attributes.

Secrets and machine-specific values (``EE_PROJECT``) come only from the environment or a
git-ignored ``.env`` file. Variables already set in the environment take precedence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
REQUIRED_FILES = ("settings", "ee_collections", "thresholds")
ENV_KEYS = ("EE_PROJECT",)


class ConfigError(Exception):
    """Raised when configuration is missing or malformed."""


@dataclass(frozen=True)
class Config:
    """Loaded project configuration.

    Attributes:
        files: Parsed YAML content keyed by file stem.
        env: Values of the known environment keys (``None`` when unset).
        config_dir: Directory the YAML files were read from.
    """

    files: dict[str, dict[str, Any]]
    env: dict[str, str | None]
    config_dir: Path

    @property
    def settings(self) -> dict[str, Any]:
        """Project settings (``settings.yaml``)."""
        return self.files["settings"]

    @property
    def ee_collections(self) -> dict[str, Any]:
        """Earth Engine dataset IDs (``ee_collections.yaml``)."""
        return self.files["ee_collections"]

    @property
    def thresholds(self) -> dict[str, Any]:
        """Algorithm parameters (``thresholds.yaml``)."""
        return self.files["thresholds"]

    @property
    def ee_project(self) -> str | None:
        """Google Cloud project ID for Earth Engine, from ``EE_PROJECT``."""
        return self.env.get("EE_PROJECT")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return content


def _load_env(env_file: Path) -> dict[str, str | None]:
    file_values = dotenv_values(env_file) if env_file.is_file() else {}
    env: dict[str, str | None] = {}
    for key in ENV_KEYS:
        value = os.environ.get(key) or file_values.get(key)
        env[key] = value or None
    return env


def load_config(config_dir: Path | None = None, env_file: Path | None = None) -> Config:
    """Load all YAML config files and the known environment variables.

    Args:
        config_dir: Directory containing ``*.yaml`` files. Defaults to ``<repo>/config``.
        env_file: Path to a ``.env`` file. Defaults to ``<repo>/.env``; a missing file is fine.

    Returns:
        The loaded configuration.

    Raises:
        ConfigError: If the directory or a required file is missing, or a file is not a
            YAML mapping.
    """
    config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    env_file = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE

    if not config_dir.is_dir():
        raise ConfigError(f"Config directory not found: {config_dir}")

    files = {path.stem: _load_yaml(path) for path in sorted(config_dir.glob("*.yaml"))}
    missing = [name for name in REQUIRED_FILES if name not in files]
    if missing:
        raise ConfigError(f"Missing config file(s) in {config_dir}: {', '.join(missing)}")

    return Config(files=files, env=_load_env(env_file), config_dir=config_dir)
