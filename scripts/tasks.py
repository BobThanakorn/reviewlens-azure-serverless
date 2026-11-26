"""Cross-platform task runner for ReviewLens.

Usage: python scripts/tasks.py <command> [options]

Every command is a thin wrapper around a tool or another script, so the same
steps run locally (PowerShell) and in GitHub Actions (ubuntu-latest).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
TF_ENV_DIR = ROOT / "terraform" / "envs" / "dev"
TF_DIRS = [ROOT / "terraform" / "bootstrap", TF_ENV_DIR]


def venv_python() -> str:
    """Return the venv interpreter if it exists, else the current interpreter."""
    candidate = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


def run_script(name: str, *args: str) -> int:
    script = ROOT / "scripts" / name
    if not script.exists():
        print(f"error: scripts/{name} does not exist yet", file=sys.stderr)
        return 2
    return run([venv_python(), str(script), *args])


def cmd_init(_: argparse.Namespace) -> int:
    if not VENV_DIR.exists():
        rc = run([sys.executable, "-m", "venv", str(VENV_DIR)])
        if rc:
            return rc
    py = venv_python()
    for req in ("requirements.txt", "requirements-dev.txt"):
        rc = run([py, "-m", "pip", "install", "-r", req])
        if rc:
            return rc
    for tf_dir in TF_DIRS:
        if tf_dir.exists():
            rc = run(["terraform", "init", "-backend=false", "-input=false"], cwd=tf_dir)
            if rc:
                return rc
    return 0


def cmd_fmt(_: argparse.Namespace) -> int:
    rc = run([venv_python(), "-m", "ruff", "format", "."])
    rc |= run([venv_python(), "-m", "ruff", "check", "--fix", "."])
    if (ROOT / "terraform").exists():
        rc |= run(["terraform", "fmt", "-recursive", "terraform"])
    return rc


def cmd_lint(_: argparse.Namespace) -> int:
    rc = run([venv_python(), "-m", "ruff", "check", "."])
    rc |= run([venv_python(), "-m", "ruff", "format", "--check", "."])
    if (ROOT / "terraform").exists():
        rc |= run(["terraform", "fmt", "-check", "-recursive", "terraform"])
        for tf_dir in TF_DIRS:
            if (tf_dir / ".terraform").exists():
                rc |= run(["terraform", "validate"], cwd=tf_dir)
    return rc


def cmd_test(args: argparse.Namespace) -> int:
    return run([venv_python(), "-m", "pytest", *args.pytest_args])


def cmd_dev(args: argparse.Namespace) -> int:
    """Serve the dashboard locally against mock data (no Azure)."""
    return run_script("dev_server.py", "--port", str(args.port))


def cmd_checkov(_: argparse.Namespace) -> int:
    """Run checkov from its own venv (it pins libraries that conflict with pytest)."""
    venv = ROOT / ".venv-checkov"
    exe = venv / ("Scripts/checkov.cmd" if sys.platform == "win32" else "bin/checkov")
    if not exe.exists():
        py = str(venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))
        rc = run([sys.executable, "-m", "venv", str(venv)])
        rc = rc or run([py, "-m", "pip", "install", "-r", "requirements-checkov.txt"])
        if rc:
            return rc
    return run([str(exe), "-d", "terraform", "--framework", "terraform", "--quiet", "--compact"])


def cmd_plan(_: argparse.Namespace) -> int:
    return run(["terraform", "plan", "-input=false"], cwd=TF_ENV_DIR)


def cmd_deploy(args: argparse.Namespace) -> int:
    """Apply infrastructure, then deploy function code. Interactive confirm by default."""
    apply_cmd = ["terraform", "apply", "-input=false"]
    if args.yes:
        apply_cmd.append("-auto-approve")
    rc = run(apply_cmd, cwd=TF_ENV_DIR)
    if rc:
        return rc
    return run_script("deploy_functions.py")


def cmd_deploy_functions(_: argparse.Namespace) -> int:
    return run_script("deploy_functions.py")


def cmd_bootstrap_data(args: argparse.Namespace) -> int:
    return run_script("bootstrap_data.py", *args.script_args)


def cmd_backfill(args: argparse.Namespace) -> int:
    return run_script("smoke_test.py", "--backfill-only", "--days", str(args.days))


def cmd_smoke_test(args: argparse.Namespace) -> int:
    return run_script("smoke_test.py", *args.script_args)


def cmd_evaluate(_: argparse.Namespace) -> int:
    return run_script("evaluate.py")


def cmd_destroy(_: argparse.Namespace) -> int:
    print(
        "Destroy is intentionally manual. To tear everything down yourself:\n"
        "  1. terraform -chdir=terraform/envs/dev destroy\n"
        "  2. terraform -chdir=terraform/bootstrap destroy   (also removes the state account)\n"
        "or run the 'destroy' GitHub workflow with confirm=destroy.\n"
        "This command never deletes anything."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tasks.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create .venv, install deps, terraform init -backend=false")
    sub.add_parser("fmt", help="format Python and Terraform")
    sub.add_parser("lint", help="ruff + terraform fmt -check + validate")
    p = sub.add_parser("test", help="run pytest with coverage gate")
    p.add_argument("pytest_args", nargs="*")
    p = sub.add_parser("dev", help="dashboard on mock data at http://127.0.0.1:PORT (no Azure)")
    p.add_argument("--port", type=int, default=8000)
    sub.add_parser("checkov", help="security scan of terraform/ (isolated venv)")
    sub.add_parser("plan", help="terraform plan for envs/dev")
    p = sub.add_parser("deploy", help="terraform apply for envs/dev, then deploy function code")
    p.add_argument("--yes", action="store_true", help="skip the interactive approval")
    sub.add_parser("deploy-functions", help="package and publish both Function Apps")
    p = sub.add_parser("bootstrap-data", help="sample the dataset and upload chunks")
    p.add_argument("script_args", nargs="*")
    p = sub.add_parser("backfill", help="call the ops/backfill endpoint")
    p.add_argument("--days", type=int, required=True)
    p = sub.add_parser("smoke-test", help="end-to-end check against the deployed environment")
    p.add_argument("script_args", nargs="*")
    sub.add_parser("evaluate", help="compute accuracy and write docs/evaluation.md")
    sub.add_parser("destroy", help="print teardown instructions (never deletes anything)")
    return parser


HANDLERS = {
    "init": cmd_init,
    "fmt": cmd_fmt,
    "lint": cmd_lint,
    "test": cmd_test,
    "dev": cmd_dev,
    "checkov": cmd_checkov,
    "plan": cmd_plan,
    "deploy": cmd_deploy,
    "deploy-functions": cmd_deploy_functions,
    "bootstrap-data": cmd_bootstrap_data,
    "backfill": cmd_backfill,
    "smoke-test": cmd_smoke_test,
    "evaluate": cmd_evaluate,
    "destroy": cmd_destroy,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
