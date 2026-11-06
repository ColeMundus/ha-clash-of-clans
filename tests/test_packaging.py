"""Artifact acceptance and fail-closed packaging tests."""

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.build_artifact import MAX_FILE, PREFIX, REQUIRED, build, validate_member

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["LICENSE", "NOTICE.md"])
def test_source_download_includes_notices(filename):
    """HACS downloads the component subtree, not repository-root notices."""
    assert (ROOT / PREFIX / filename).read_bytes() == (ROOT / filename).read_bytes()


@pytest.fixture
def package_source(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(
        ROOT / "custom_components",
        root / "custom_components",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for filename in ["LICENSE", "NOTICE.md"]:
        shutil.copyfile(ROOT / filename, root / filename)
    return root


def test_build_reproducible_complete_and_importable(package_source, tmp_path):
    archive, count, digest = build(package_source, tmp_path / "first")
    again, _, again_digest = build(package_source, tmp_path / "second")
    assert archive.read_bytes() == again.read_bytes()
    assert digest == again_digest == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert count == len(REQUIRED) + 2
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {
            PREFIX + name for name in REQUIRED | {"LICENSE", "NOTICE.md"}
        }
        bundle.extractall(tmp_path / "installed")
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import custom_components.clash_of_clans.sensor as sensor; import custom_components.clash_of_clans.config_flow; assert len(sensor.SENSORS) == 20; print(sensor.__file__)",
        ],
        cwd=tmp_path / "installed",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert str(tmp_path / "installed") in result.stdout


@pytest.mark.parametrize(
    "name",
    [
        "../api.py",
        "/api.py",
        PREFIX + "../api.py",
        PREFIX + "secret.env",
        PREFIX + "tests/test_api.py",
        "custom_components/other/api.py",
    ],
)
def test_paths_fail_closed(name):
    with pytest.raises(ValueError):
        validate_member(name, b"pass")


def test_size_limit():
    with pytest.raises(ValueError, match="size limit"):
        validate_member(PREFIX + "api.py", b"x" * (MAX_FILE + 1))


def test_credentials_rejected():
    credential = b"eyJ" + b"x" * 30 + b"." + b"y" * 30 + b"." + b"z" * 30
    with pytest.raises(ValueError, match="credential"):
        validate_member(PREFIX + "NOTICE.md", credential)


@pytest.mark.parametrize(
    "filename", ["brand/icon.png", "translations/en.json", "manifest.json"]
)
def test_missing_runtime_file_rejected(package_source, tmp_path, filename):
    (package_source / PREFIX / filename).unlink()
    with pytest.raises(ValueError, match="Missing required"):
        build(package_source, tmp_path / "dist")


@pytest.mark.parametrize("filename", ["LICENSE", "NOTICE.md"])
def test_missing_notice_rejected(package_source, tmp_path, filename):
    (package_source / filename).unlink()
    with pytest.raises(FileNotFoundError):
        build(package_source, tmp_path / "dist")


def test_unapproved_extra_file_rejected(package_source, tmp_path):
    (package_source / PREFIX / "secrets.yaml").write_text("synthetic: true")
    with pytest.raises(ValueError, match="Unapproved"):
        build(package_source, tmp_path / "dist")


def test_symlink_rejected(package_source, tmp_path):
    target = package_source / PREFIX / "api.py"
    target.unlink()
    target.symlink_to(ROOT / PREFIX / "api.py")
    with pytest.raises(ValueError, match="Symlinks"):
        build(package_source, tmp_path / "dist")


def test_translation_matches_source():
    import json

    assert json.loads((ROOT / PREFIX / "strings.json").read_text()) == json.loads(
        (ROOT / PREFIX / "translations/en.json").read_text()
    )
