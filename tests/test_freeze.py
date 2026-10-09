"""Baseline freeze manifest (AGENTS.md rule 8).

`test_repository_baseline_matches_manifest` is the CI gate: once `baseline_v1.sha256`
exists, any change to a frozen baseline file fails the build. Changing the baseline needs
an ADR and a new version (v2) with its own manifest.
"""

import hashlib
from pathlib import Path

import pytest

from thwake import baseline as b
from thwake.config import REPO_ROOT, Config, load_config


@pytest.fixture
def cfg() -> Config:
    return load_config(env_file=REPO_ROOT / "does-not-exist.env")


def test_frozen_files_cover_every_baseline_output(cfg: Config) -> None:
    # Only data/baseline/ is baseline-only. media/ also holds later outputs; its frozen files
    # (the baseline figures) are protected by the checksum manifest below.
    names = {p.relative_to(REPO_ROOT).as_posix() for p in b.frozen_files(cfg)}
    on_disk = {
        p.relative_to(REPO_ROOT).as_posix()
        for p in (REPO_ROOT / "data" / "baseline").iterdir()
        if p.is_file() and p.name != ".gitkeep" and p != b.manifest_path(cfg)
    }
    assert on_disk <= names, f"baseline outputs not in FROZEN_PATH_KEYS: {on_disk - names}"


def test_repository_baseline_matches_manifest(cfg: Config) -> None:
    if not b.is_frozen(cfg):
        pytest.skip("baseline not frozen yet")
    assert b.verify_manifest(cfg) == []


def write(root: Path, name: str, content: bytes) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_sha256_file(tmp_path: Path) -> None:
    path = write(tmp_path, "a.csv", b"level,area\n912,30.36\n")
    assert b.sha256_file(path) == hashlib.sha256(b"level,area\n912,30.36\n").hexdigest()


def test_manifest_round_trip_and_sha256sum_format(tmp_path: Path) -> None:
    files = [write(tmp_path, "data/a.csv", b"a"), write(tmp_path, "media/b.png", b"b")]
    text = b.manifest_text(files, root=tmp_path)
    first = text.splitlines()[0]
    assert first == f"{hashlib.sha256(b'a').hexdigest()}  data/a.csv"
    manifest = write(tmp_path, "m.sha256", text.encode())
    entries = b.read_manifest(manifest)
    assert list(entries) == ["data/a.csv", "media/b.png"]
    assert b.manifest_problems(entries, files, root=tmp_path) == []


def test_manifest_problems_reports_changed_missing_and_unlisted(tmp_path: Path) -> None:
    a = write(tmp_path, "a.csv", b"a")
    c = write(tmp_path, "c.csv", b"c")
    entries = b.read_manifest(
        write(tmp_path, "m.sha256", b.manifest_text([a, c], root=tmp_path).encode())
    )
    a.write_bytes(b"tuned")
    c.unlink()
    new = write(tmp_path, "new.geojson", b"{}")
    problems = b.manifest_problems(entries, [a, c, new], root=tmp_path)
    assert problems == [
        "new.geojson: frozen file not listed in the manifest",
        "a.csv: changed since the freeze",
        "c.csv: missing",
    ]


def test_verify_without_manifest_raises(cfg: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(b, "manifest_path", lambda cfg: REPO_ROOT / "no-such.sha256")
    assert b.is_frozen(cfg) is False
    with pytest.raises(b.BaselineError, match="not frozen"):
        b.verify_manifest(cfg)


def test_write_manifest_refuses_missing_files(cfg: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(b, "frozen_files", lambda cfg: [REPO_ROOT / "data" / "nope.csv"])
    with pytest.raises(b.BaselineError, match="nope.csv"):
        b.write_manifest(cfg)
