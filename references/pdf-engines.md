# PDF extraction engines

This skill supports two engines for getting figures + reading-order context out of a paper PDF. Pick per the user's preference; default to `pymupdf` unless they've configured otherwise.

## Choosing an engine

Read `papers/engine.json` if it exists:
```json
{ "engine": "mineru_api" }
```
No file, or `engine` missing/`"pymupdf"` → use the `pymupdf` engine. `"mineru_api"` → use the MinerU engine.

## Engine: pymupdf (default)

`scripts/extract_pdf_assets.py` — local, fast, no network, no extra setup beyond the already-installed PyMuPDF/pdfplumber. Extracts embedded raster images only — **misses figures that are drawn as vector graphics** in the PDF (lines/shapes composed directly, common for clean method-diagram figures). When a figure mentioned in the text doesn't show up in `figures_raw/`, that's the likely reason — tell the user rather than silently dropping the figure, and offer the MinerU engine as the fix.

## Engine: mineru_api

`scripts/mineru_extract.py` — calls the hosted MinerU API (mineru.net) instead of installing MinerU locally (no multi-GB model download). MinerU does full layout analysis on the rendered page, so it captures vector-drawn figures too, and returns content in original reading order, which makes figure-to-context placement much more reliable than raw embedded-image extraction.

**Setup required** — tell the user if missing, don't guess or skip silently:
1. An API token from mineru.net (account → API management page → create token).
2. The token available as either the `MINERU_API_TOKEN` environment variable, or a `mineru_api_token` field in `papers/engine.json` — in which case **pass `--engine-config <path to that engine.json>`** when invoking the script (it does not search for the file on its own; it only checks `--token`, then `MINERU_API_TOKEN`, then `--engine-config` if given).

**What it does** (see the script for the exact HTTP calls):
1. `POST /api/v4/file-urls/batch` with the file name → get a pre-signed upload URL + `batch_id`.
2. `PUT` the raw PDF bytes to that URL.
3. Poll `GET /api/v4/extract-results/batch/{batch_id}` until `state == "done"` (or `"failed"`).
4. Download `full_zip_url` and unzip into `<output_dir>/mineru/` — contains a markdown file with images already placed in their original reading-order position, plus a `content_list.json`/`images/` folder.

**Free tier note**: each account gets up to 1000 pages/day at top priority; beyond that, requests still go through but at lower priority (slower), per MinerU's documented limits as of when this was written — re-check mineru.net if a batch seems stuck.

**Using the output**: read the MinerU markdown instead of `text.txt` for figure-context judgment — the images are already inline near the paragraph that discusses them, which directly answers "where does this figure belong" far more reliably than matching page numbers. Copy the images you select from `mineru/images/` (or wherever the zip placed them) into `<output_dir>/figures/` the same way as the pymupdf path.

If a batch fails or times out, fall back to the `pymupdf` engine for that paper and tell the user why, rather than blocking the whole run.
