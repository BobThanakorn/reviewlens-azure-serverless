import json
import threading
import urllib.error
import urllib.request

import pytest

import dev_server


@pytest.fixture(scope="module")
def base_url():
    server = dev_server.make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - local test server
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def test_serves_dashboard_and_generated_config(base_url):
    status, html = get(f"{base_url}/index.html")
    assert status == 200 and "ReviewLens" in html
    status, js = get(f"{base_url}/config.js")
    assert status == 200 and '"/api"' in js


def test_api_routes_return_real_aggregates(base_url):
    _, body = get(f"{base_url}/api/stats/daily?days=10")
    series = json.loads(body)["series"]
    assert len(series) == 10 and all(day["total"] == dev_server.PER_DAY for day in series)
    _, body = get(f"{base_url}/api/stats/accuracy")
    assert json.loads(body)["sample_size"] == dev_server.DAYS * dev_server.PER_DAY
    _, body = get(f"{base_url}/api/reviews?sentiment=negative&limit=5")
    assert json.loads(body)["count"] == 5


def test_bad_input_is_a_400_and_unknown_route_a_404(base_url):
    assert get(f"{base_url}/api/stats/daily?days=999")[0] == 400
    assert get(f"{base_url}/api/nope")[0] == 404


def test_static_server_does_not_leak_files_outside_web(base_url):
    status, _ = get(f"{base_url}/..%2f..%2fpyproject.toml")
    assert status in (301, 400, 403, 404)
    assert "[project]" not in get(f"{base_url}/..%2fpyproject.toml")[1]
