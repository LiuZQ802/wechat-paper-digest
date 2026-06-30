---
name: wechat-paper-digest
description: Batch-convert academic paper PDFs into WeChat official-account ("公众号") "论文荐读" article markdown, following a fixed lab formatting template (cover screenshot, 16/18px text, accent-colored highlights, curated figures, optional references/author bios), plus a styled HTML preview with a one-click rich-text copy button for pasting into the Xiumi (秀米) editor. Use when the user wants to turn one or more paper PDFs into a 公众号/WeChat article draft, asks to "做公众号推文", "论文荐读", or batch-process a folder of papers into posts.
---

# WeChat Paper Digest

## Overview

Turns a folder of paper PDFs into ready-to-paste WeChat "论文荐读" (paper recommendation) articles. Each PDF becomes its own output folder with a cover image, curated figures, a clean markdown article, suggested title/share-summary metadata, and a styled HTML preview with a copy button.

Two-stage pipeline: (1) deterministic asset extraction via a script (no judgment calls), (2) content synthesis and figure curation done by reading the extracted text/context (judgment calls — what to say, which figures matter, where they go, how to organize sections).

Read `references/format-rules.md` before generating the first article in a session — it is the full formatting spec this skill follows. Read `references/pdf-engines.md` before the first extraction — it explains the two extraction engines and when each applies. Read `references/writing-style.md` before writing the first `article.md` — it's the standard content must meet: specific enough that a reader never has to guess what a sentence means.

## Hard Constraint

`references/format-rules.md` describes how the output *should look*. Its own text — the numbered rules, section labels like "专题：论文荐读" — is internal guidance for me, not article content. **Never copy any of that rules text into `article.md`.** The generated article must read like a normal paper-recommendation post: title/journal/authors, content digest, research sections, figures, the paper's own citation, and optional author bios. Nothing about formatting rules themselves.

## Don't Guess When Unsure — Ask

This skill has two points where a wrong automatic guess is worse than asking: which page is the real cover, and which figure goes where. If the evidence is clear (page text plainly shows journal+title+institution+authors; a figure's surrounding text plainly names it), decide and move on. If it's genuinely ambiguous — multiple cover candidates each missing something, or two figures could plausibly fill the same slot — stop and ask the user with `AskUserQuestion` (show the candidates) instead of picking one silently. Note this in the per-paper report either way.

## Input Convention

```
papers/                     <- folder the user points me at
  engine.json                 <- optional, global: {"engine": "pymupdf"|"mineru_api", "mineru_api_token": "..."}
  authors.json                <- optional, shared across runs: name -> {affiliation, title}
  notes.json                  <- optional, per-PDF overrides: {color, focus, is_own_group}
  paper1.pdf
  paper2.pdf
```

- `engine.json` picks the extraction engine for the whole batch (see `references/pdf-engines.md`). `"mineru_api"` → calls the hosted MinerU API; needs a token (env var `MINERU_API_TOKEN` or `mineru_api_token` in this file) — if missing, tell the user how to get one rather than silently falling back.
- `authors.json` is the "own lab" roster. If a paper's author list has any match, treat it as an own-group paper.
- `notes.json` keys are PDF filenames. Any field not given falls back to default (`color: deep_blue`, focus auto-derived from the abstract, `is_own_group` auto-detected via `authors.json`).
- If `papers/` has no `authors.json`/`notes.json`, proceed with defaults (no author bios, default color) — don't ask the user to create them unless they want those features. **`engine.json` is different: don't default it silently.**

## Step 0: Pick the Extraction Engine (once per `papers/` folder)

Before processing any PDF, check for `papers/engine.json`. If it exists, use what it says. If it doesn't exist, **ask the user** with `AskUserQuestion` — pymupdf (local, no setup, misses vector-drawn figures) vs MinerU (hosted API, needs a token, catches vector figures and gives reading-order context) — see `references/pdf-engines.md` for the trade-off to summarize in the question. Once they answer, write `{"engine": "<their choice>"}` to `papers/engine.json` (plus `mineru_api_token` if they give one) so this isn't asked again for this folder. Only re-ask if the user later asks to change engines or deletes the file.

## Workflow

For each PDF in the input folder:

1. **Extract assets** (deterministic, run the script — don't hand-roll this with other tools):
   ```bash
   python <skill_dir>/scripts/extract_pdf_assets.py <pdf_path> <output_dir>
   ```
   Produces `<output_dir>/cover_candidates/page{1..3}.png`, `text.txt`, `manifest.json`, `figures_raw/*`. This always runs, regardless of engine — it's also the source of the cover candidates and the text.

   If `engine.json` says `mineru_api`, additionally run:
   ```bash
   python <skill_dir>/scripts/mineru_extract.py <pdf_path> <output_dir> --engine-config <path to papers/engine.json>
   ```
   Always pass `--engine-config` pointing at the actual `engine.json` you read in Step 0 — don't rely on the script to guess its location.
   and use its `mineru/` output (images in original reading order) as the figure source instead of `figures_raw/`/`manifest.json` for step 4. If this call fails (bad token, timeout, API error), tell the user what happened and fall back to the `pymupdf` figures for this paper rather than aborting the batch.

2. **Pick the cover page**: read the per-page text in `text.txt` for each page in `cover_candidates/`. Skip any page that reads like a publisher landing page (telltale phrases: "To cite this article", "View related articles", "Crossmark", "Submit your article") *unless* it's the only candidate that has journal+title+authors — affiliations ("学校") are the field most often missing from these landing pages, so prefer whichever candidate page has all four. Copy the chosen one to `<output_dir>/cover.png`. If no single page covers all four, or two pages are both plausible, ask the user which to use (see "Don't Guess When Unsure").

3. **Read the text** (chunk it if long) and pull out: journal name, paper title, first author's institution ("学校"), full author list, abstract, DOI, volume/issue/pages if assigned, and however the paper says its data can be obtained — a public link, a repository name, or just "contact the corresponding author at \<email\>". Any of these counts as "数据集获取" content; don't skip it just because it isn't a clickable URL. Also note enough for the paper's own citation (step 7).

4. **Check own-group status**: match the author list against `authors.json`. Note the result — it gates step 6's author-bio section.

5. **Pick figures and where they go**: using whichever figure source step 1 produced, pick 2-4 images that the surrounding text plausibly references as a meaningful method/result figure ("Figure N", "Fig. N", "图N", or a clear caption nearby). Skip logos/icons/decorative banners. For each pick, you should be able to point to the specific sentence that justifies both *that this figure matters* and *where in the article it belongs*. If you can't, that's the ambiguous case in "Don't Guess When Unsure" — surface it instead of placing it anyway. Copy chosen files from the figure source into `<output_dir>/figures/`, renamed `fig1.<ext>`, `fig2.<ext>`, etc., **keeping the original file extension** (pymupdf figures are often actually JPEG even though they came from a PDF — check, don't assume `.png`).

6. **Write `article.md`**: organize using the structure in `references/format-rules.md`'s "输出结构参考". Pick whichever of 研究背景/科学问题/方法/结论 actually have content to support them — don't force all four, but don't go thin either: each chosen section needs at least 2 substantive paragraphs with concrete numbers/comparisons/examples from the paper, not a one-line abstract restatement (see rule 6 in format-rules.md — thin content is a defect, not a style choice). If the paper has a qualitative case/example table (e.g. "here's a case where baseline methods got it wrong and our method didn't"), that's exactly the kind of concrete material to include — it reads far better than abstract method description. If the method has clear sequential stages (e.g. "two-stage fine-tuning", "a three-step pipeline"), give each stage its own ①②③-numbered sub-heading and paragraph instead of folding them into one block of prose — much easier to scan. Write every sentence to the standard in `references/writing-style.md`: specific enough that the reader never has to guess what it means — no "显著提升/有效解决/具有重要意义" floating without a number or concrete fact attached. Section headings are self-written and can be lively/evocative, not literal labels. Bold the key terms (`**word**`) — these become the colored-highlight spots in the HTML preview. Insert figures using `![图N 图说](figures/figN.ext)` at the point they're discussed. Include the "本文引用信息" section (rule 7: this paper's *own* formal citation — authors, year, title, venue, volume/issue/pages, DOI — not a pick from the paper's internal bibliography). Include an author-bio section only if step 4 found a match — format each line `**姓名** 单位　职称`, pulling affiliation/title from `authors.json`.

7. **Self-check `article.md`**: confirm it contains none of the literal rule text from `references/format-rules.md` and no "专题：论文荐读" label. Confirm the "本文引用信息" section cites the featured paper itself, not papers from its bibliography. Then do a vagueness pass per `references/writing-style.md`: read every sentence and ask "if I deleted this, what specific information would the reader lose?" — any sentence whose answer is "nothing, it's just a mood word" needs a concrete number/fact added or needs to go. If any check fails, rewrite that part.

8. **Write `meta.md`**: suggested title `文献荐读 | <短标题>`, a one-to-two sentence suggested share summary, and a note on whether a cover-card image is warranted (default: leave blank, per the rules the publisher applies a shared template when blank).

9. **Build `preview.html`** from `templates/preview_shell.html`:
   - Look up the accent color: `notes.json` entry's `color` name resolved against `references/color-themes.json`, default `deep_blue`.
   - Convert `article.md` into the inner HTML: paragraphs as `<p>`, section headings as `<h1>`, bolded key terms as `<strong class="accent">`. For each figure, emit a `<div class="fig-marker">图N：figures/figN.ext（手动拖拽到秀米中此处）<img src="figures/figN.ext"></div>` — the image shows in the local preview, but only the marker text survives copy-paste, so keep the marker text itself short and exact about which file to drop in.
   - Replace `{{TITLE}}`, `{{ACCENT_COLOR}}`, `{{ARTICLE_HTML}}` in the template and write the result to `<output_dir>/preview.html`.

10. **QA the preview**: try to render `preview.html` to a screenshot for a visual sanity check before reporting done. Look for a local Chrome/Edge binary (e.g. `C:\Program Files\Google\Chrome\Application\chrome.exe`, `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`) and run:
    ```bash
    "<browser>" --headless=new --disable-gpu --screenshot="<tmp>.png" --window-size=900,<tall> "file:///<absolute path to preview.html>"
    ```
    Read the screenshot to confirm the accent color, headings, and figure markers actually rendered, then delete the temp screenshot. If no browser is found, skip this and tell the user to open `preview.html` manually instead of silently skipping QA.

11. Move to the next PDF. If one PDF fails (corrupt file, no extractable text, etc.), report the failure and continue with the rest of the batch — don't abort the whole run.

After the batch, report per-paper: output folder path, which cover candidate was used (and why, if it wasn't page 1), whether own-group author bio was included, how many figures were picked and via which engine, anything flagged for user confirmation, and any papers that failed with why.

## Using the HTML Preview

Images do not survive the copy-paste into 秀米/公众号 (pasted rich text can't carry local file references across browser origins). The realistic flow is: open `preview.html`, click "复制正文", paste into the 秀米/公众号 editor (text, bold, color, headings carry over), then manually drag each file from `figures/` into the spot marked by its `图N：...` text marker, and delete the marker text.

## Validation Standard

A paper's output is done only when:
- `article.md` contains zero literal text from `references/format-rules.md` and no "专题：论文荐读"/numbered-rule artifacts
- the cover page actually shows journal+title+institution+authors together (not a publisher landing page missing affiliations)
- every figure referenced in `article.md` exists in `figures/` with the correct extension, and each placement is backed by a specific sentence in the source text (not a guess)
- each research section has at least 2 substantive, concrete paragraphs — not single-line abstractions
- no sentence relies on an unanchored vague qualifier (显著/有效/一定程度上/良好/重要意义) without a number or specific fact next to it (`references/writing-style.md`)
- "本文引用信息" cites the featured paper itself (with DOI), not an entry from its internal bibliography
- `meta.md` has a `文献荐读 | xxx` title and a non-empty share summary
- `preview.html` opens in a browser showing the accent color, 16px body / 18px headings, and a working copy button
- author-bio section is present only when an actual `authors.json` match was found
