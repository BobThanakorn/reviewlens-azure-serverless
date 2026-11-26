"""Package and publish both Function Apps (and optionally the dashboard) to Azure.

Layout of each package (the Python v2 model needs function_app.py at the package root):

    function_app.py, host.json, requirements.txt
    common/        shared code
    pipeline/ or api/   the app's own package (imported as ``pipeline.*`` / ``api.*``)

Publishing uses ``az functionapp deployment source config-zip`` with a remote build, so
dependencies are installed on Azure for the right platform. Requires ``az login`` (locally) or
``azure/login`` (CI). Idempotent: deploying the same package twice is harmless.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TF_ENV_DIR = ROOT / "terraform" / "envs" / "dev"
APPS = {"pipeline": "pipeline_app_name", "api": "api_app_name"}
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def stage_app(app: str, stage_dir: Path, src: Path = SRC, requirements: Path | None = None) -> Path:
    """Copy one app's files into ``stage_dir`` using the layout described in the module doc."""
    if app not in APPS:
        raise ValueError(f"unknown app {app!r}; expected one of {sorted(APPS)}")
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    shutil.copy2(src / app / "function_app.py", stage_dir / "function_app.py")
    shutil.copy2(src / app / "host.json", stage_dir / "host.json")
    shutil.copy2(requirements or ROOT / "requirements.txt", stage_dir / "requirements.txt")
    shutil.copytree(src / "common", stage_dir / "common", ignore=IGNORED)
    shutil.copytree(src / app, stage_dir / app, ignore=IGNORED)
    return stage_dir


def zip_dir(stage_dir: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(p for p in stage_dir.rglob("*") if p.is_file()):
            zf.write(file, file.relative_to(stage_dir).as_posix())
    return zip_path


def build_package(app: str, out_dir: Path, src: Path = SRC) -> Path:
    stage = stage_app(app, out_dir / f"stage-{app}", src=src)
    return zip_dir(stage, out_dir / f"{app}.zip")


def terraform_outputs() -> dict[str, str]:
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=TF_ENV_DIR, capture_output=True, text=True, check=True,
    )  # fmt: skip
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def az(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    exe = shutil.which("az")
    if exe is None:
        raise SystemExit("Azure CLI (az) not found on PATH")
    return subprocess.run([exe, *args], check=True, capture_output=capture, text=True)


def ensure_identity_only_storage(resource_group: str, app_name: str) -> bool:
    """Remove the bare ``AzureWebJobsStorage`` setting; return True if one was removed.

    azurerm injects it with an empty AccountKey on every apply and hides it from the plan
    (hashicorp/terraform-provider-azurerm#29149). The host then signs requests with that empty
    key instead of using the ``AzureWebJobsStorage__*`` identity settings, so secrets, health and
    triggers fail with 403 while shared-key access is disabled (docs/runbook.md, incident 13).
    """
    listed = az(
        "functionapp", "config", "appsettings", "list",
        "--resource-group", resource_group,
        "--name", app_name,
        "--query", "[].name",
        "--output", "tsv",
        capture=True,
    )  # fmt: skip
    if "AzureWebJobsStorage" not in listed.stdout.split():
        return False
    az(
        "functionapp", "config", "appsettings", "delete",
        "--resource-group", resource_group,
        "--name", app_name,
        "--setting-names", "AzureWebJobsStorage",
        "--output", "none",
    )  # fmt: skip
    return True


def publish(resource_group: str, app_name: str, zip_path: Path) -> None:
    az(
        "functionapp", "deployment", "source", "config-zip",
        "--resource-group", resource_group,
        "--name", app_name,
        "--src", str(zip_path),
        "--build-remote", "true",
    )  # fmt: skip


def upload_web(storage_account: str) -> None:
    """Upload web/ (index.html, app.js and the Terraform-generated config.js) to $web."""
    az(
        "storage", "blob", "upload-batch",
        "--auth-mode", "login",
        "--account-name", storage_account,
        "--destination", "$web",
        "--source", str(ROOT / "web"),
        "--overwrite", "true",
    )  # fmt: skip


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--resource-group")
    p.add_argument("--pipeline-app")
    p.add_argument("--api-app")
    p.add_argument("--web-account")
    p.add_argument("--out-dir", type=Path, default=ROOT / ".deploy")
    p.add_argument("--package-only", action="store_true", help="build the zips, do not publish")
    p.add_argument("--with-web", action="store_true", help="also upload the dashboard")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    zips = {app: build_package(app, args.out_dir) for app in APPS}
    for path in zips.values():
        print(f"built {path} ({path.stat().st_size // 1024} KiB)")
    if args.package_only:
        return 0

    outputs = {}
    if not (args.resource_group and args.pipeline_app and args.api_app):
        outputs = terraform_outputs()
    group = args.resource_group or outputs["resource_group_name"]
    names = {
        "pipeline": args.pipeline_app or outputs["pipeline_app_name"],
        "api": args.api_app or outputs["api_app_name"],
    }
    for app, path in zips.items():
        if ensure_identity_only_storage(group, names[app]):
            print(f"removed stray AzureWebJobsStorage connection string from {names[app]}")
        print(f"publishing {app} -> {names[app]}")
        publish(group, names[app], path)
    if args.with_web:
        web_account = args.web_account or outputs.get("web_storage_account_name")
        upload_web(web_account or terraform_outputs()["web_storage_account_name"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
