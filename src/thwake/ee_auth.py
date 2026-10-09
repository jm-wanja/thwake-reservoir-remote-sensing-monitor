"""Authenticate to Earth Engine: user credentials locally, service account in CI.

Locally, run ``earthengine authenticate`` once (HUMAN-STEPS.md H2); the stored user
credentials are then picked up here. The service-account path for GitHub Actions is added
with the scheduled workflow (prompt 11). See .ai/docs/06-deployment.md.
"""

from __future__ import annotations

import ee

from thwake.config import Config, ConfigError


def initialize(cfg: Config) -> None:
    """Initialise the Earth Engine client for the project in ``EE_PROJECT``.

    Args:
        cfg: Loaded configuration; ``cfg.ee_project`` must be set (``.env`` or environment).

    Raises:
        ConfigError: If ``EE_PROJECT`` is not set.
    """
    if not cfg.ee_project:
        raise ConfigError("EE_PROJECT is not set; add it to .env (see .env.example)")
    ee.Initialize(project=cfg.ee_project)
