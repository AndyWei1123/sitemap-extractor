from __future__ import annotations

import io
import time
import zipfile

import pytest
from conftest import index, make_transport, urlset
from fastapi.testclient import TestClient

from web.app import RateLimiter, Settings, create_app

A = "https://a.example"
B = "https://b.example"
ROUTES = {
    f"{A}/sitemap_index.xml": index(f"{A}/post-sitemap.xml", f"{A}/page-sitemap.xml"),
    f"{A}/post-sitemap.xml": urlset(f"{A}/hello/", f"{A}/world/", f"{A}/=evil/"),
    f"{A}/page-sitemap.xml": urlset(f"{A}/about/"),
    f"{B}/sitemap.xml": urlset(f"{B}/x/", f"{B}/y/"),
}


def make_client(routes=ROUTES, **settings) -> TestClient:
    app = create_app(Settings(**settings), transport=make_transport(routes))
    return TestClient(app)


def run_job(client: TestClient, inputs: list[str]) -> dict:
    resp = client.post("/api/jobs", json={"inputs": inputs})
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["id"]
    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "done":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@pytest.fixture(autouse=True)
def fast_hosts(monkeypatch, public_dns):
    monkeypatch.setattr("sitemap_core.fetch.FetchConfig.per_host_interval", 0)


def test_full_flow_simple_mode():
    with make_client() as client:
        job = run_job(client, [f"{A}/sitemap_index.xml", f"{B}/sitemap.xml"])
        assert job["urls"] == 6 and job["sitemaps_done"] == 4 and not job["errors"]
        assert job["type_counts"]["a.example"] == {"article": 3, "page": 1}
        assert len(job["sources"]) == 3

        res = client.post(f"/api/jobs/{job['id']}/results", json={}).json()
        # a.example: 3 articles. b.example has no detectable articles, so all of its URLs are listed.
        assert res["total"] == 5 and res["fallback_sites"] == ["b.example"]
        assert f"{A}/about/" not in [row[1] for row in res["rows"]]

        everything = client.post(f"/api/jobs/{job['id']}/results", json={"types": None}).json()
        assert everything["total"] == 6


def test_filters_and_skip_sources():
    with make_client() as client:
        job = run_job(client, [f"{A}/sitemap_index.xml"])
        url = f"/api/jobs/{job['id']}/results"
        assert client.post(url, json={"include": ["hello"]}).json()["total"] == 1
        assert client.post(url, json={"exclude": ["hello"]}).json()["total"] == 2
        assert client.post(url, json={"date_from": "2027-01-01"}).json()["total"] == 0
        post_index = next(s["index"] for s in job["sources"] if "post-sitemap" in s["url"])
        assert client.post(url, json={"types": None, "skip_sources": [post_index]}).json()["total"] == 1
        assert client.post(url, json={"types": ["nonsense"]}).status_code == 400
        assert client.post(url, json={"date_from": "yesterday"}).status_code == 400


def test_downloads():
    with make_client() as client:
        job = run_job(client, [f"{A}/sitemap_index.xml", f"{B}/sitemap.xml"])
        url = f"/api/jobs/{job['id']}/download"

        resp = client.post(url, json={"format": "csv", "lang": "en"})
        assert resp.content.startswith(b"\xef\xbb\xbf")
        assert 'filename="sitemap-urls_' in resp.headers["content-disposition"]
        lines = resp.content.decode("utf-8-sig").strip().split("\r\n")
        assert lines[0] == "site,url,lastmod,source_sitemap,type" and len(lines) == 6
        assert f"a.example,{A}/hello/,2026-01-02,{A}/post-sitemap.xml,article" in lines

        txt = client.post(url, json={"format": "txt"}).text
        assert txt.splitlines()[0] == f"{A}/hello/" and len(txt.splitlines()) == 5

        archive = zipfile.ZipFile(io.BytesIO(client.post(url, json={"format": "zip"}).content))
        names = sorted(archive.namelist())
        assert len(names) == 2 and names[0].startswith("a.example_") and names[1].startswith("b.example_")
        assert archive.read(names[1]).decode("utf-8-sig").count("\r\n") == 3

        assert client.post(url, json={"format": "exe"}).status_code == 400


def test_single_site_file_name():
    with make_client() as client:
        job = run_job(client, [f"{B}/sitemap.xml"])
        resp = client.post(f"/api/jobs/{job['id']}/download", json={})
        assert 'filename="b.example_' in resp.headers["content-disposition"]


def test_security_headers_and_static():
    with make_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200 and "Sitemap Extractor" in resp.text
        assert resp.headers["content-security-policy"].startswith("default-src 'self'")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/api/jobs/nope").status_code == 404


def test_public_mode_blocks_internal_targets():
    with make_client(public_mode=True) as client:
        job = run_job(client, ["http://127.0.0.1/sitemap.xml", "http://169.254.169.254/latest/",
                               "https://a.example:8443/sitemap.xml"])
        assert job["urls"] == 0
        assert {e["code"] for e in job["errors"]} == {"unsafe_url"}
        assert len(job["errors"]) == 3


def test_public_mode_blocks_host_resolving_to_private(public_dns):
    public_dns["rebind.example"] = ["192.168.0.10"]
    routes = {"https://rebind.example/sitemap.xml": urlset("https://rebind.example/secret/")}
    with make_client(routes, public_mode=True) as client:
        job = run_job(client, ["https://rebind.example/sitemap.xml"])
        assert job["urls"] == 0 and job["errors"][0]["code"] == "unsafe_url"


def test_input_limits():
    with make_client(max_inputs=2) as client:
        resp = client.post("/api/jobs", json={"inputs": ["a.example", "b.example", "c.example"]})
        assert resp.status_code == 400 and resp.json() == {"error": "too_many_inputs"}
        assert client.post("/api/jobs", json={"inputs": ["  ", ""]}).status_code == 400
        assert client.post("/api/jobs", json={"inputs": []}).status_code == 422
        assert client.post("/api/jobs", json={"inputs": ["x" * 3000]}).status_code == 400


def test_rate_limit_per_ip():
    with make_client(rate_limit_per_hour=2) as client:
        codes = [client.post("/api/jobs", json={"inputs": [f"{B}/sitemap.xml"]}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


def test_rate_limit_uses_forwarded_ip_only_when_trusted():
    with make_client(rate_limit_per_hour=1, trust_proxy=True) as client:
        body = {"inputs": [f"{B}/sitemap.xml"]}
        assert client.post("/api/jobs", json=body, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.post("/api/jobs", json=body, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
        assert client.post("/api/jobs", json=body, headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}).status_code == 429
    with make_client(rate_limit_per_hour=1, trust_proxy=False) as client:
        body = {"inputs": [f"{B}/sitemap.xml"]}
        assert client.post("/api/jobs", json=body, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.post("/api/jobs", json=body, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(2, window=60, clock=lambda: now[0])
    assert limiter.allow("ip") and limiter.allow("ip") and not limiter.allow("ip")
    assert limiter.allow("other")
    now[0] = 61
    assert limiter.allow("ip")


def test_max_urls_limit_is_reported():
    with make_client(max_urls=2) as client:
        job = run_job(client, [f"{A}/sitemap_index.xml"])
        assert job["urls"] == 2 and job["truncated"] == "max_urls"


def test_results_expire():
    with make_client(result_ttl=0) as client:
        job = run_job(client, [f"{B}/sitemap.xml"])
        time.sleep(0.01)
        client.app.state.cleanup()
        assert client.get(f"/api/jobs/{job['id']}").status_code == 404
