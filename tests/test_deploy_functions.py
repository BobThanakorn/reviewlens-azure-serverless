import zipfile
from unittest.mock import patch

import pytest

import deploy_functions as df


def names(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        return set(zf.namelist())


def test_pipeline_package_layout(tmp_path):
    archive = names(df.build_package("pipeline", tmp_path))
    assert {"function_app.py", "host.json", "requirements.txt"} <= archive
    assert "common/classifier.py" in archive
    assert "pipeline/ingest/handler.py" in archive
    assert "pipeline/enrich/prompt.py" in archive
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in archive)


def test_api_package_has_no_pipeline_code(tmp_path):
    archive = names(df.build_package("api", tmp_path))
    assert "api/aggregate.py" in archive and "common/storage.py" in archive
    assert not any(n.startswith("pipeline/") for n in archive)


def test_each_package_uses_its_own_host_json(tmp_path):
    pipeline = df.stage_app("pipeline", tmp_path / "p")
    api = df.stage_app("api", tmp_path / "a")
    assert "maxDequeueCount" in (pipeline / "host.json").read_text()
    assert "maxDequeueCount" not in (api / "host.json").read_text()


def test_unknown_app_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown app"):
        df.stage_app("web", tmp_path)


def test_package_only_publishes_nothing(tmp_path):
    with patch.object(df, "publish") as publish:
        assert df.main(["--package-only", "--out-dir", str(tmp_path)]) == 0
    publish.assert_not_called()
    assert (tmp_path / "pipeline.zip").exists() and (tmp_path / "api.zip").exists()


def test_publish_with_explicit_names_skips_terraform(tmp_path):
    with patch.object(df, "publish") as publish, patch.object(df, "terraform_outputs") as tf:
        rc = df.main(
            ["--resource-group", "rg", "--pipeline-app", "p", "--api-app", "a",
             "--out-dir", str(tmp_path)]
        )  # fmt: skip
    assert rc == 0
    tf.assert_not_called()
    assert [c.args[:2] for c in publish.call_args_list] == [("rg", "p"), ("rg", "a")]


def test_publish_builds_remote_build_command():
    with patch.object(df, "az") as az:
        df.publish("rg", "app", df.ROOT / "x.zip")
    cmd = az.call_args.args
    assert cmd[:4] == ("functionapp", "deployment", "source", "config-zip")
    assert "--build-remote" in cmd and "true" in cmd
