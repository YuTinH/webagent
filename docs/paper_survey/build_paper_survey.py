from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable

import requests
from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "pdfs"
FIG_DIR = ROOT / "figures"
TEXT_DIR = ROOT / "text"
META_PATH = ROOT / "papers.json"
USER_AGENT = "Mozilla/5.0 (paper-survey-builder)"


def load_papers() -> list[dict]:
    return json.loads(META_PATH.read_text())


def sanitize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 10_000:
        return
    response = requests.get(url, timeout=120, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    dest.write_bytes(response.content)


def extract_pages_text(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    texts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        texts.append(sanitize_text(text))
    return texts


def extract_abstract(full_text: str) -> str:
    patterns = [
        r"Abstract\s*(.+?)\n\s*(?:1\s+Introduction|I\.\s+Introduction|Introduction)",
        r"ABSTRACT\s*(.+?)\n\s*(?:1\s+INTRODUCTION|I\.\s+INTRODUCTION|INTRODUCTION)",
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, flags=re.S)
        if match:
            abstract = sanitize_text(match.group(1))
            if len(abstract) > 200:
                return abstract
    return ""


def collect_heading_lines(page_texts: list[str]) -> list[str]:
    headings: list[str] = []
    heading_re = re.compile(
        r"^(?:\d+(?:\.\d+)*|[IVX]+)\s+[A-Z][A-Za-z0-9 ,:/()\-\u2013]+$"
    )
    for text in page_texts:
        for line in text.splitlines():
            clean = line.strip()
            if 5 <= len(clean) <= 120 and heading_re.match(clean):
                headings.append(clean)
    return headings


def best_sentences(full_text: str, keywords: Iterable[str], limit: int = 6) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", full_text.replace("\n", " "))
    chosen: list[tuple[int, str]] = []
    for sent in sentences:
        clean = sanitize_text(sent)
        if len(clean) < 40 or len(clean) > 350:
            continue
        lower = clean.lower()
        score = sum(2 for kw in keywords if kw.lower() in lower)
        score += lower.count("benchmark")
        score += lower.count("agent")
        if score > 0:
            chosen.append((score, clean))
    chosen.sort(key=lambda x: (-x[0], len(x[1])))
    seen = set()
    result = []
    for _, sentence in chosen:
        if sentence in seen:
            continue
        seen.add(sentence)
        result.append(sentence)
        if len(result) >= limit:
            break
    return result


def page_score(text: str) -> tuple[int, Counter]:
    lower = text.lower()
    counter = Counter()
    keywords = {
        "experiments": 4,
        "experiment": 4,
        "evaluation": 4,
        "results": 3,
        "empirical": 3,
        "ablation": 3,
        "benchmark": 2,
        "baseline": 2,
        "comparison": 2,
        "score": 2,
        "success rate": 3,
        "accuracy": 2,
        "medal": 3,
        "cost": 2,
        "leaderboard": 2,
        "table": 1,
        "figure": 1,
    }
    score = 0
    for key, weight in keywords.items():
        count = lower.count(key)
        if count:
            counter[key] = count
            score += count * weight
    if "references" in lower[:500]:
        score -= 6
    if "appendix" in lower[:300]:
        score -= 1
    return score, counter


def find_key_pages(page_texts: list[str]) -> list[int]:
    fig_page = None
    for idx, text in enumerate(page_texts):
        low = text.lower()
        if "figure 1" in low or "fig. 1" in low or "fig 1" in low:
            fig_page = idx
            break

    scored_pages = []
    for idx, text in enumerate(page_texts):
        score, _ = page_score(text)
        if score > 0:
            scored_pages.append((score, idx))
    scored_pages.sort(reverse=True)

    selected: list[int] = []
    if fig_page is not None:
        selected.append(fig_page)
    for _, idx in scored_pages:
        if idx not in selected:
            selected.append(idx)
        if len(selected) >= 4:
            break
    return sorted(selected)


def write_text_dump(paper: dict, page_texts: list[str]) -> dict:
    slug = paper["slug"]
    full_text = "\n\n".join(page_texts)
    abstract = extract_abstract(full_text)
    headings = collect_heading_lines(page_texts)[:40]
    method_sentences = best_sentences(
        full_text,
        [
            "framework",
            "agent",
            "workflow",
            "optimiz",
            "bench",
            "repository",
            "search space",
            "surrogate",
            "multi-fidelity",
            "kaggle",
        ],
        limit=8,
    )
    experiment_sentences = best_sentences(
        full_text,
        [
            "experiment",
            "results",
            "evaluation",
            "baseline",
            "success rate",
            "accuracy",
            "cost",
            "budget",
            "tasks",
            "datasets",
            "repo",
            "competition",
        ],
        limit=10,
    )
    dump = {
        "title": paper["title"],
        "year": paper["year"],
        "source_url": paper["source_url"],
        "pdf_url": paper["pdf_url"],
        "abstract": abstract,
        "headings": headings,
        "method_sentences": method_sentences,
        "experiment_sentences": experiment_sentences,
    }
    (TEXT_DIR / f"{slug}.json").write_text(json.dumps(dump, indent=2, ensure_ascii=False))
    return dump


def render_pages(pdf_path: Path, slug: str, pages: list[int]) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    output = []
    for page_idx in pages:
        one_page_pdf = FIG_DIR / f"{slug}_p{page_idx + 1}.pdf"
        out_png = FIG_DIR / f"{slug}_p{page_idx + 1}.png"
        writer = PdfWriter()
        writer.add_page(reader.pages[page_idx])
        with one_page_pdf.open("wb") as handle:
            writer.write(handle)
        subprocess.run(
            ["sips", "-s", "format", "png", str(one_page_pdf), "--out", str(out_png)],
            check=True,
            capture_output=True,
            text=True,
        )
        output.append({"page": page_idx + 1, "pdf": str(one_page_pdf.name), "png": str(out_png.name)})
    return output


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    papers = load_papers()
    manifest = []
    for paper in papers:
        slug = paper["slug"]
        pdf_path = PDF_DIR / f"{slug}.pdf"
        print(f"[download] {slug}")
        download_file(paper["pdf_url"], pdf_path)
        print(f"[extract] {slug}")
        page_texts = extract_pages_text(pdf_path)
        dump = write_text_dump(paper, page_texts)
        pages = find_key_pages(page_texts)
        print(f"[render] {slug}: pages {pages}")
        figures = render_pages(pdf_path, slug, pages)
        manifest.append(
            {
                "slug": slug,
                "title": paper["title"],
                "year": paper["year"],
                "category": paper["category"],
                "source_url": paper["source_url"],
                "pdf_path": str(pdf_path.relative_to(ROOT)),
                "text_dump": str((TEXT_DIR / f"{slug}.json").relative_to(ROOT)),
                "abstract_found": bool(dump["abstract"]),
                "rendered_pages": figures,
            }
        )
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print("[done] manifest written")


if __name__ == "__main__":
    main()
