"""Web UI and API. Run locally with `python -m web`; set PUBLIC_MODE=1 for a public deployment."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sitemap_core import (ARTICLE, TYPES, Entry, FetchConfig, Fetcher, Filter, Limits, Progress, extract,
                          sites_without_articles)
from sitemap_core.export import csv_rows

STATIC_DIR = Path(__file__).parent / "static"
PREVIEW_LIMIT = 500
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass
class Settings:
    public_mode: bool = False
    trust_proxy: bool = False          # read the client IP from X-Forwarded-For (behind a reverse proxy)
    rate_limit_per_hour: int = 0       # jobs per IP per hour; 0 = unlimited
    max_concurrent_jobs: int = 3
    max_queue: int = 20
    result_ttl: int = 3600             # seconds a finished job's results are kept
    max_inputs: int = 200
    max_urls: int = 5_000_000
    max_seconds: int = 0               # 0 = unlimited
    max_bytes: int = 50 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        public = _env_bool("PUBLIC_MODE")
        return cls(
            public_mode=public,
            trust_proxy=_env_bool("TRUST_PROXY"),
            rate_limit_per_hour=_env_int("RATE_LIMIT_PER_HOUR", 20 if public else 0),
            max_concurrent_jobs=_env_int("MAX_CONCURRENT_JOBS", 3),
            max_queue=_env_int("MAX_QUEUE", 20),
            result_ttl=_env_int("RESULT_TTL", 3600),
            max_inputs=_env_int("MAX_INPUTS", 10 if public else 200),
            max_urls=_env_int("MAX_URLS", 200_000 if public else 5_000_000),
            max_seconds=_env_int("MAX_SECONDS", 300 if public else 0),
            max_bytes=_env_int("MAX_FILE_MB", 50) * 1024 * 1024,
        )


class RateLimiter:
    """Sliding-window limit of `limit` events per `window` seconds, per key."""

    def __init__(self, limit: int, window: float = 3600.0, clock=time.monotonic):
        self.limit = limit
        self.window = window
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = self._clock()
        with self._lock:
            if len(self._events) > 10_000:
                for k in [k for k, q in self._events.items() if not q or q[-1] <= now - self.window]:
                    del self._events[k]
            q = self._events.setdefault(key, deque())
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


class Job:
    def __init__(self, job_id: str, inputs: list[str], path: Path):
        self.id = job_id
        self.inputs = inputs
        self.path = path
        self.status = "queued"  # queued -> running -> done
        self.progress = Progress()
        self.cancel = threading.Event()
        self.finished_at: float | None = None
        self.type_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def entries(self) -> Iterator[Entry]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                yield Entry(*json.loads(line))


class CreateJobBody(BaseModel):
    inputs: list[str] = Field(min_length=1, max_length=1000)


class FilterBody(BaseModel):
    types: list[str] | None = Field(default_factory=lambda: [ARTICLE])  # null = every type
    include: list[str] = Field(default_factory=list, max_length=20)
    exclude: list[str] = Field(default_factory=list, max_length=20)
    date_from: str = ""
    date_to: str = ""
    skip_sources: list[int] = Field(default_factory=list, max_length=20_000)
    fallback: bool = True  # list every URL for sites with no detectable articles


class DownloadBody(FilterBody):
    format: str = "csv"  # csv | txt | zip
    lang: str = "zh"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", name).strip("._") or "site"


def create_app(settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    workdir = Path(tempfile.mkdtemp(prefix="sitemap-extractor-"))
    fetcher = Fetcher(
        FetchConfig(allow_private=not settings.public_mode, restrict_ports=settings.public_mode,
                    max_bytes=settings.max_bytes),
        transport=transport,
    )
    limits = Limits(max_inputs=settings.max_inputs, max_urls=settings.max_urls,
                    max_seconds=settings.max_seconds or None)
    pool = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs, thread_name_prefix="job")
    limiter = RateLimiter(settings.rate_limit_per_hour)
    jobs: dict[str, Job] = {}
    jobs_lock = threading.Lock()
    stop = threading.Event()

    def cleanup() -> None:
        now = time.monotonic()
        with jobs_lock:
            expired = [j for j in jobs.values()
                       if j.finished_at is not None and now - j.finished_at > settings.result_ttl]
            for job in expired:
                del jobs[job.id]
        for job in expired:
            job.path.unlink(missing_ok=True)

    def janitor() -> None:
        while not stop.wait(60):
            cleanup()

    threading.Thread(target=janitor, daemon=True, name="janitor").start()

    def shutdown() -> None:
        stop.set()
        with jobs_lock:
            for job in jobs.values():
                job.cancel.set()
        pool.shutdown(wait=False, cancel_futures=True)
        fetcher.close()
        shutil.rmtree(workdir, ignore_errors=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        shutdown()

    app = FastAPI(title="Sitemap Extractor", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.state.settings = settings
    app.state.jobs = jobs
    app.state.cleanup = cleanup

    def run_job(job: Job) -> None:
        job.status = "running"
        try:
            with job.path.open("w", encoding="utf-8") as fh:
                def on_entry(entry: Entry) -> None:
                    fh.write(json.dumps([entry.site, entry.url, entry.lastmod, entry.source, entry.type],
                                        ensure_ascii=False) + "\n")
                    job.type_counts[entry.site][entry.type] += 1
                extract(job.inputs, fetcher, on_entry, limits, job.progress, job.cancel)
        except Exception as exc:  # keep the job reportable whatever happens
            job.progress.add_error("", "internal", type(exc).__name__)
        finally:
            job.status = "done"
            job.finished_at = time.monotonic()

    def client_ip(request: Request) -> str:
        if settings.trust_proxy:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    def get_job(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job_not_found")
        return job

    def build_filter(job: Job, body: FilterBody) -> Filter:
        if body.types is not None and not set(body.types) <= set(TYPES):
            raise HTTPException(400, "bad_request")
        for value in (body.date_from, body.date_to):
            if value and not DATE_RE.match(value):
                raise HTTPException(400, "bad_request")
        keywords = [k for k in body.include + body.exclude]
        if any(len(k) > 200 for k in keywords):
            raise HTTPException(400, "bad_request")
        sources = job.progress.sources
        skip = frozenset(sources[i].url for i in body.skip_sources if 0 <= i < len(sources))
        types = None if body.types is None else frozenset(body.types)
        fallback = frozenset()
        if body.fallback and types == frozenset({ARTICLE}):
            fallback = sites_without_articles(job.type_counts)
        return Filter(
            types=types,
            include=tuple(k.strip() for k in body.include if k.strip()),
            exclude=tuple(k.strip() for k in body.exclude if k.strip()),
            date_from=body.date_from, date_to=body.date_to,
            skip_sources=skip, fallback_sites=fallback,
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/config")
    def config():
        return {
            "public_mode": settings.public_mode,
            "max_inputs": settings.max_inputs,
            "max_urls": settings.max_urls,
            "max_seconds": settings.max_seconds,
            "rate_limit_per_hour": settings.rate_limit_per_hour,
            "preview_limit": PREVIEW_LIMIT,
        }

    @app.post("/api/jobs")
    def create_job(body: CreateJobBody, request: Request):
        inputs = list(dict.fromkeys(s.strip() for s in body.inputs if s.strip()))
        if not inputs or any(len(s) > 2000 for s in inputs):
            raise HTTPException(400, "bad_request")
        if len(inputs) > settings.max_inputs:
            raise HTTPException(400, "too_many_inputs")
        with jobs_lock:
            active = sum(1 for j in jobs.values() if j.status != "done")
            if active >= settings.max_concurrent_jobs + settings.max_queue:
                raise HTTPException(503, "busy")
        if not limiter.allow(client_ip(request)):
            raise HTTPException(429, "rate_limited")
        job_id = secrets.token_urlsafe(16)
        job = Job(job_id, inputs, workdir / f"{job_id}.jsonl")
        with jobs_lock:
            jobs[job_id] = job
        pool.submit(run_job, job)
        return {"id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        job = get_job(job_id)
        p = job.progress
        with p.lock:
            data = {
                "id": job.id,
                "status": job.status,
                "sitemaps_done": p.sitemaps_done,
                "sitemaps_total": p.sitemaps_total,
                "urls": p.urls,
                "errors": p.errors[:200],
                "truncated": p.truncated,
            }
            if job.status == "done":
                data["sources"] = [{"index": i, "url": s.url, "site": s.site, "count": s.count, "type": s.type}
                                   for i, s in enumerate(p.sources)]
                data["type_counts"] = {site: dict(c) for site, c in job.type_counts.items()}
        return data

    @app.delete("/api/jobs/{job_id}")
    def cancel_job(job_id: str):
        get_job(job_id).cancel.set()
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/results")
    def job_results(job_id: str, body: FilterBody):
        job = get_job(job_id)
        if job.status != "done":
            raise HTTPException(409, "not_ready")
        flt = build_filter(job, body)
        rows, total = [], 0
        sites: set[str] = set()
        for e in flt.apply(job.entries()):
            total += 1
            sites.add(e.site)
            if len(rows) < PREVIEW_LIMIT:
                rows.append([e.site, e.url, e.lastmod, e.source, e.type])
        return {"total": total, "rows": rows, "sites": sorted(sites),
                "fallback_sites": sorted(flt.fallback_sites)}

    @app.post("/api/jobs/{job_id}/download")
    def job_download(job_id: str, body: DownloadBody):
        job = get_job(job_id)
        if job.status != "done":
            raise HTTPException(409, "not_ready")
        if body.format not in ("csv", "txt", "zip"):
            raise HTTPException(400, "bad_request")
        lang = body.lang if body.lang in ("zh", "en") else "en"
        flt = build_filter(job, body)
        today = dt.date.today().isoformat()
        all_sites = sorted(job.type_counts)
        base = _safe_name(all_sites[0]) if len(all_sites) == 1 else "sitemap-urls"

        def csv_bytes(entries) -> Iterator[bytes]:
            yield b"\xef\xbb\xbf"
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator="\r\n")
            for n, row in enumerate(csv_rows(entries, lang), 1):
                writer.writerow(row)
                if n % 2000 == 0:
                    yield buf.getvalue().encode("utf-8")
                    buf.seek(0)
                    buf.truncate()
            yield buf.getvalue().encode("utf-8")

        if body.format == "txt":
            def txt_bytes() -> Iterator[bytes]:
                chunk: list[str] = []
                for e in flt.apply(job.entries()):
                    chunk.append(e.url)
                    if len(chunk) >= 2000:
                        yield ("\n".join(chunk) + "\n").encode("utf-8")
                        chunk = []
                if chunk:
                    yield ("\n".join(chunk) + "\n").encode("utf-8")
            return StreamingResponse(txt_bytes(), media_type="text/plain; charset=utf-8", headers={
                "Content-Disposition": f'attachment; filename="{base}_{today}.txt"'})

        if body.format == "zip":
            spool = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
            with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as zf:
                for site in all_sites:
                    site_entries = (e for e in flt.apply(job.entries()) if e.site == site)
                    first = next(site_entries, None)
                    if first is None:
                        continue
                    with zf.open(f"{_safe_name(site)}_{today}.csv", "w") as member:
                        def chained(first=first, rest=site_entries):
                            yield first
                            yield from rest
                        for part in csv_bytes(chained()):
                            member.write(part)
            spool.seek(0)

            def zip_bytes() -> Iterator[bytes]:
                try:
                    while True:
                        part = spool.read(64 * 1024)
                        if not part:
                            break
                        yield part
                finally:
                    spool.close()
            return StreamingResponse(zip_bytes(), media_type="application/zip", headers={
                "Content-Disposition": f'attachment; filename="sitemap-urls_{today}.zip"'})

        return StreamingResponse(csv_bytes(flt.apply(job.entries())), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": f'attachment; filename="{base}_{today}.csv"'})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
