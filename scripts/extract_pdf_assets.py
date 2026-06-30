#!/usr/bin/env python3
"""Extract cover candidates, full text, and candidate figures from a paper PDF.

Deterministic extraction only — no judgment about which figures matter or
which page is the real title page. Those decisions are made later by reading
manifest.json + text.txt (and, for the cover, by inspecting the per-page text
of each candidate — publisher landing pages ("To cite this article", "View
related articles", "Crossmark") usually lack author affiliations, so the real
title page is often page 2, not page 1).

Usage:
    python extract_pdf_assets.py <pdf_path> <output_dir> [--min-area 22500] [--cover-pages 3]

Writes into <output_dir>:
    cover_candidates/pageN.png   first N pages rendered at 200dpi, pick one
    text.txt                     full extracted text, paginated with markers
    manifest.json                list of candidate figures with page/size/context
    figures_raw/<name>           the candidate figure image files
"""
import argparse
import json
import os
import sys

import fitz  # PyMuPDF


def extract(pdf_path: str, output_dir: str, min_area: int, cover_pages: int) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    figures_dir = os.path.join(output_dir, "figures_raw")
    os.makedirs(figures_dir, exist_ok=True)
    cover_dir = os.path.join(output_dir, "cover_candidates")
    os.makedirs(cover_dir, exist_ok=True)

    doc = fitz.open(pdf_path)

    cover_candidates = []
    for page_num in range(min(cover_pages, doc.page_count)):
        path = os.path.join(cover_dir, f"page{page_num + 1}.png")
        doc[page_num].get_pixmap(dpi=200).save(path)
        cover_candidates.append(path)

    text_parts = []
    for page_num, page in enumerate(doc):
        text_parts.append(f"\n--- PAGE {page_num + 1} ---\n")
        text_parts.append(page.get_text())
    text_path = os.path.join(output_dir, "text.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write("".join(text_parts))

    manifest = []
    seen_xrefs = set()
    fig_count = 0
    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue
            width = base_image["width"]
            height = base_image["height"]
            if width * height < min_area:
                continue
            fig_count += 1
            ext = base_image["ext"]
            fname = f"page{page_num + 1}_{fig_count}.{ext}"
            fpath = os.path.join(figures_dir, fname)
            with open(fpath, "wb") as imf:
                imf.write(base_image["image"])
            manifest.append({
                "file": fname,
                "page": page_num + 1,
                "width": width,
                "height": height,
                "page_text_excerpt": page_text[:1500],
            })

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {
        "cover_candidates": cover_candidates,
        "text": text_path,
        "manifest": manifest_path,
        "num_pages": doc.page_count,
        "num_candidate_figures": len(manifest),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path")
    parser.add_argument("output_dir")
    parser.add_argument("--min-area", type=int, default=22500,
                         help="Minimum width*height in pixels to keep a candidate figure "
                              "(filters out logos/icons). Default 22500 (~150x150).")
    parser.add_argument("--cover-pages", type=int, default=3,
                         help="Render the first N pages as cover candidates (default 3). "
                              "Pick whichever one actually shows journal+title+institution+authors together.")
    args = parser.parse_args()

    if not os.path.isfile(args.pdf_path):
        print(f"error: pdf not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = extract(args.pdf_path, args.output_dir, args.min_area, args.cover_pages)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
