import csv
from pathlib import Path

import pytest

from thwake.config import DEFAULT_CONFIG_DIR, REPO_ROOT, ConfigError, load_config


def write_minimal_config(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "settings.yaml").write_text("dam:\n  name: Test Dam\n")
    (config_dir / "ee_collections.yaml").write_text("sentinel2_sr: TEST/S2\n")
    (config_dir / "thresholds.yaml").write_text("sentinel2:\n  fallback_threshold: 0.0\n")


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    path = tmp_path / "config"
    write_minimal_config(path)
    return path


@pytest.fixture(autouse=True)
def no_ee_project_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EE_PROJECT", raising=False)


def test_loads_yaml_files_by_stem(config_dir: Path, tmp_path: Path) -> None:
    (config_dir / "extra.yaml").write_text("key: value\n")
    cfg = load_config(config_dir, env_file=tmp_path / "missing.env")

    assert cfg.settings["dam"]["name"] == "Test Dam"
    assert cfg.ee_collections["sentinel2_sr"] == "TEST/S2"
    assert cfg.thresholds["sentinel2"]["fallback_threshold"] == 0.0
    assert cfg.files["extra"] == {"key": "value"}
    assert cfg.config_dir == config_dir


def test_empty_yaml_file_loads_as_empty_mapping(config_dir: Path, tmp_path: Path) -> None:
    (config_dir / "settings.yaml").write_text("")
    cfg = load_config(config_dir, env_file=tmp_path / "missing.env")
    assert cfg.settings == {}


def test_missing_config_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope")


def test_missing_required_file_raises(config_dir: Path) -> None:
    (config_dir / "thresholds.yaml").unlink()
    with pytest.raises(ConfigError, match="thresholds"):
        load_config(config_dir)


def test_non_mapping_yaml_raises(config_dir: Path) -> None:
    (config_dir / "settings.yaml").write_text("- a\n- b\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(config_dir)


def test_invalid_yaml_raises(config_dir: Path) -> None:
    (config_dir / "settings.yaml").write_text("dam: [unclosed\n")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(config_dir)


def test_ee_project_from_env_file(config_dir: Path, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EE_PROJECT=from-file\n")
    assert load_config(config_dir, env_file=env_file).ee_project == "from-file"


def test_environment_overrides_env_file(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EE_PROJECT=from-file\n")
    monkeypatch.setenv("EE_PROJECT", "from-environment")
    assert load_config(config_dir, env_file=env_file).ee_project == "from-environment"


def test_ee_project_none_when_unset_or_empty(config_dir: Path, tmp_path: Path) -> None:
    assert load_config(config_dir, env_file=tmp_path / "missing.env").ee_project is None
    env_file = tmp_path / ".env"
    env_file.write_text("EE_PROJECT=\n")
    assert load_config(config_dir, env_file=env_file).ee_project is None


def test_loading_env_file_does_not_modify_os_environ(config_dir: Path, tmp_path: Path) -> None:
    import os

    env_file = tmp_path / ".env"
    env_file.write_text("EE_PROJECT=from-file\n")
    load_config(config_dir, env_file=env_file)
    assert "EE_PROJECT" not in os.environ


# --- The real repository config -------------------------------------------------------


def test_repository_config_loads() -> None:
    cfg = load_config(DEFAULT_CONFIG_DIR, env_file=REPO_ROOT / "does-not-exist.env")
    assert cfg.settings["dam"]["name"] == "Thwake Dam"
    assert cfg.ee_collections["sentinel2_sr"]
    assert cfg.thresholds["baseline"]["aev_level_step_m"] == 0.5


def official_value(item: str) -> float:
    """First (current-design) value for an item in official_figures.csv."""
    path = REPO_ROOT / "data" / "external" / "official_figures.csv"
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["item"] == item:
                return float(row["value"])
    raise KeyError(item)


def test_settings_match_official_figures() -> None:
    dam = load_config(env_file=REPO_ROOT / "does-not-exist.env").settings["dam"]
    assert dam["full_supply_level_m_asl"] == official_value("full_supply_level")
    assert dam["design_capacity_mcm"] == official_value("storage_capacity_at_fsl")
    assert dam["maximum_flood_level_m_asl"] == official_value("maximum_flood_level")
