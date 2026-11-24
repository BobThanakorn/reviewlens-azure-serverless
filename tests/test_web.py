"""Static checks and Node unit tests for the dashboard."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_javascript_unit_tests_pass():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    # Node 22+ treats the argument as a file or glob, not a directory.
    result = subprocess.run(  # noqa: S603 - fixed arguments, no user input
        [node, "--test", "tests/web/*.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_review_text_is_never_written_with_innerhtml():
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source
    assert "document.write" not in source and "eval(" not in source


def test_chart_library_is_pinned_with_integrity_hash():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    tag = re.search(r"<script[^>]+chart\.js[^>]*>", html, re.DOTALL)
    assert tag, "Chart.js script tag missing"
    assert re.search(r"chart\.js@\d+\.\d+\.\d+/", tag.group(0)), "version must be pinned"
    assert 'integrity="sha384-' in tag.group(0) and 'crossorigin="anonymous"' in tag.group(0)


def test_csp_blocks_inline_script_and_limits_script_sources():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', html).group(1)
    assert "script-src 'self' https://cdn.jsdelivr.net" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", html), "no inline scripts"


def test_api_url_is_not_hardcoded():
    for name in ("index.html", "app.js"):
        text = (WEB / name).read_text(encoding="utf-8")
        assert "azurewebsites.net" not in text and "localhost" not in text


def test_generated_config_is_git_ignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "web/config.js" in ignore
