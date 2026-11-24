"""Guard rails for the GitHub Actions workflows: the security properties must not regress."""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def steps_text(job: dict) -> str:
    return yaml.safe_dump(job.get("steps", []))


@pytest.mark.parametrize("name", ["ci.yml", "deploy.yml", "destroy.yml"])
def test_no_hardcoded_guid_or_secret(name):
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
    assert "client-secret" not in text and "AZURE_CREDENTIALS" not in text


@pytest.mark.parametrize("name", ["ci.yml", "deploy.yml", "destroy.yml"])
def test_default_permissions_are_read_only(name):
    assert load(name)["permissions"] == {"contents": "read"}


def test_destroy_requires_the_exact_confirmation():
    wf = load("destroy.yml")
    # PyYAML reads the bare key `on` as boolean True.
    assert list(wf[True]) == ["workflow_dispatch"], "destroy must only be started manually"
    assert wf[True]["workflow_dispatch"]["inputs"]["confirm"]["required"] is True
    job = wf["jobs"]["destroy"]
    assert job["if"] == "github.event.inputs.confirm == 'destroy'"


def test_destroy_only_touches_the_dev_environment():
    text = steps_text(load("destroy.yml")["jobs"]["destroy"])
    assert "terraform/envs/dev" in text and "bootstrap" not in text


def test_plan_uses_read_only_identity_and_skips_the_lock():
    job = load("ci.yml")["jobs"]["plan"]
    text = steps_text(job)
    assert "AZURE_CLIENT_ID_PLAN" in text and "AZURE_CLIENT_ID_APPLY" not in text
    assert "-lock=false" in text
    assert "apply" not in text.replace("applies", "")
    assert "github.event.pull_request.head.repo.full_name == github.repository" in job["if"]


def test_apply_identity_is_only_used_by_main_branch_workflows():
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    deploy = load("deploy.yml")
    assert "AZURE_CLIENT_ID_APPLY" not in ci
    assert deploy[True]["push"]["branches"] == ["main"]
    assert "AZURE_CLIENT_ID_APPLY" in steps_text(deploy["jobs"]["deploy"])


def test_oidc_token_only_granted_to_jobs_that_log_in():
    for name in ("ci.yml", "deploy.yml", "destroy.yml"):
        for job_name, job in load(name)["jobs"].items():
            logs_in = "azure/login" in steps_text(job)
            has_token = job.get("permissions", {}).get("id-token") == "write"
            assert has_token == logs_in, f"{name}:{job_name}"


def test_deploy_never_cancels_a_running_apply():
    assert load("deploy.yml")["concurrency"]["cancel-in-progress"] is False


def test_untrusted_input_is_passed_through_env_not_interpolated_into_shell():
    deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    assert 'run: python scripts/smoke_test.py --days "$SMOKE_DAYS"' in deploy
    assert "run: python scripts/smoke_test.py --days ${{" not in deploy
