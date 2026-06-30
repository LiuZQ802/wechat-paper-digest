#!/usr/bin/env python3
"""Extract a paper PDF via the hosted MinerU API (mineru.net) instead of local parsing.

Unlike scripts/extract_pdf_assets.py (embedded-image extraction only), MinerU
does full page-layout analysis, so it also catches figures drawn as vector
graphics, and returns content in original reading order — which makes
figure-to-paragraph placement far more reliable.

Requires an API token: see references/pdf-engines.md for how to obtain one.
Pass it via --token, the MINERU_API_TOKEN env var, or a "mineru_api_token"
field in papers/engine.json.

Usage:
    python mineru_extract.py <pdf_path> <output_dir> [--token TOKEN] [--model-version pipeline]
                              [--poll-interval 5] [--timeout 600]

Writes into <output_dir>/mineru/:
    the unzipped MinerU result (markdown + content_list.json + images/)
"""
import argparse
import json
import os
import sys
import time
import zipfile
from io import BytesIO

import requests

API_BASE = "https://mineru.net/api/v4"


def request_upload_url(token: str, filename: str, model_version: str) -> tuple[str, str]:
    resp = requests.post(
        f"{API_BASE}/file-urls/batch",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"files": [{"name": filename}], "model_version": model_version},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return data["batch_id"], data["file_urls"][0]


def upload_file(upload_url: str, pdf_path: str) -> None:
    with open(pdf_path, "rb") as f:
        resp = requests.put(upload_url, data=f, timeout=120)
    resp.raise_for_status()


def poll_result(token: str, batch_id: str, poll_interval: int, timeout: int) -> str:
    deadline = time.time() + timeout
    url = f"{API_BASE}/extract-results/batch/{batch_id}"
    while time.time() < deadline:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        resp.raise_for_status()
        results = resp.json()["data"]["extract_result"]
        result = results[0]
        state = result.get("state")
        if state == "done":
            return result["full_zip_url"]
        if state == "failed":
            raise RuntimeError(f"MinerU extraction failed: {result.get('err_msg')}")
        time.sleep(poll_interval)
    raise TimeoutError(f"MinerU extraction did not finish within {timeout}s (batch_id={batch_id})")


def download_and_unzip(zip_url: str, output_dir: str) -> str:
    mineru_dir = os.path.join(output_dir, "mineru")
    os.makedirs(mineru_dir, exist_ok=True)
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        zf.extractall(mineru_dir)
    return mineru_dir


def resolve_token(cli_token: str | None, output_dir: str) -> str:
    if cli_token:
        return cli_token
    env_token = os.environ.get("MINERU_API_TOKEN")
    if env_token:
        return env_token
    engine_config = os.path.join(os.path.dirname(output_dir.rstrip("/\\")) or ".", "engine.json")
    for candidate in (engine_config, "papers/engine.json"):
        if os.path.isfile(candidate):
            with open(candidate, encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("mineru_api_token"):
                return cfg["mineru_api_token"]
    raise RuntimeError(
        "No MinerU API token found. Set MINERU_API_TOKEN, pass --token, or add "
        '"mineru_api_token" to papers/engine.json. See references/pdf-engines.md.'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path")
    parser.add_argument("output_dir")
    parser.add_argument("--token", default=None)
    parser.add_argument("--model-version", default="pipeline")
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    if not os.path.isfile(args.pdf_path):
        print(f"error: pdf not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    token = resolve_token(args.token, args.output_dir)
    filename = os.path.basename(args.pdf_path)

    batch_id, upload_url = request_upload_url(token, filename, args.model_version)
    upload_file(upload_url, args.pdf_path)
    zip_url = poll_result(token, batch_id, args.poll_interval, args.timeout)
    mineru_dir = download_and_unzip(zip_url, args.output_dir)

    print(json.dumps({"mineru_dir": mineru_dir, "batch_id": batch_id}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
