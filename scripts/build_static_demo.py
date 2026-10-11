# -*- coding: utf-8 -*-
"""Bake Lab Hub Sentence Reader + Dictionary into static GitHub Pages assets."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUGSBURG = ROOT.parent
APPS = AUGSBURG / "_labhub" / "apps"
DOCS = ROOT / "docs"
SAMPLES = APPS / "samples"

sys.path.insert(0, str(APPS / "server"))
from corpus_store import CorpusStore  # noqa: E402
from dict_store import DictStore, CAPABILITY_CATALOG  # noqa: E402

# Vary demo sizes across sources (at least 50 when available).
SIZE_CYCLE = [50, 60, 75, 80, 100, 120, 150, 90, 110, 70]

# Open-friendly dictionary collections for public demo (plus NC muse with notice).
DICT_COLLECTIONS = ("freedict", "apertium", "dbnary", "omw", "muse")
ROWS_PER_PAIR = 400
SCAN_PER_PAIR = 12000
MAX_PAIRS = 12
# Prefer lemmas that demo both direct hits and induced bridges in the static UI.
SEED_WORDS = {
    "love", "haus", "baum", "hand", "house", "water", "amour", "tree", "book",
    "man", "woman", "god", "king", "city", "day", "night", "good", "new", "old",
    "amor", "liebe", "buch", "neu",
}


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _demo_n(corpus_id: str, total: int, idx: int) -> int:
    if corpus_id == "rem_samples":
        return total
    if total <= 0:
        return 0
    target = SIZE_CYCLE[idx % len(SIZE_CYCLE)]
    return max(50, min(total, target)) if total >= 50 else total


def export_corpora(store: CorpusStore) -> dict:
    public = store.list_public()
    layer_catalog = store.layer_catalog()
    out_corpora = []
    stats = []

    for i, meta in enumerate(public):
        cid = meta["id"]
        total = int(meta.get("sentence_count") or 0)
        n = _demo_n(cid, total, i)
        if n <= 0:
            continue

        summaries = []
        sentences = []
        # Spread sample across the corpus instead of only the head.
        if total <= n:
            indices = list(range(total))
        else:
            step = total / n
            indices = sorted({min(total - 1, int(j * step)) for j in range(n)})
            # ensure length at least min(n, total)
            while len(indices) < n and len(indices) < total:
                for k in range(total):
                    if k not in indices:
                        indices.append(k)
                    if len(indices) >= n:
                        break
            indices = sorted(indices)[:n]

        for local_i, src_i in enumerate(indices):
            try:
                full = store.sentence(cid, src_i)
            except Exception as e:
                print(f"  skip {cid}[{src_i}]: {e}")
                continue
            sent = full.get("sentence") or {}
            summaries.append(
                {
                    "index": local_i,
                    "source_index": src_i,
                    "label": sent.get("label") or f"s{src_i}",
                    "text": sent.get("text") or "",
                    "token_count": len(sent.get("tokens") or []),
                }
            )
            # Re-index for the demo store so UI indices 0..n-1 work.
            sent = dict(sent)
            sent["index"] = local_i
            full = dict(full)
            full["sentence"] = sent
            full["demo_source_index"] = src_i
            sentences.append(full)

        if not sentences:
            continue

        demo_meta = dict(meta)
        demo_meta["sentence_count"] = len(sentences)
        demo_meta["demo_note"] = (
            f"Static GitHub Pages demo: {len(sentences)} of {total} sentences "
            f"(spread sample). Licenses unchanged; NC/scholarly for non-commercial lab demo."
        )
        out_corpora.append(demo_meta)

        bundle = {
            "id": cid,
            **{k: demo_meta[k] for k in demo_meta if k != "id"},
            "columns": sentences[0].get("columns") or [],
            "match_count": len(summaries),
            "sentences": summaries,
            "full_sentences": sentences,
            "store": "static-demo",
            "backend": "baked-json",
        }
        _write_json(DOCS / "api" / "corpora" / f"{cid}.json", bundle)
        stats.append((cid, len(sentences), total))
        print(f"  corpus {cid}: {len(sentences)} / {total}")

    catalog = {
        "layer_catalog": layer_catalog,
        "corpora": out_corpora,
        "store": "static-demo",
        "meta": {
            "title": "ACoLi Lab Hub · static demo",
            "note": "Precomputed subset for GitHub Pages. Not the full lab store.",
            "corpus_total": len(out_corpora),
            "sentence_total": sum(s[1] for s in stats),
        },
    }
    _write_json(DOCS / "api" / "corpora.json", catalog)
    return {"stats": stats, "catalog": catalog}


def export_dicts(store: DictStore) -> dict:
    dims = store.dimensions()
    cols = [c for c in store.collections() if c.get("id") in DICT_COLLECTIONS]
    listed = store.list_pairs(browsable_only=True, limit=1000)
    pairs = [p for p in listed.get("pairs", []) if p.get("collection") in DICT_COLLECTIONS]

    by_col: dict[str, list] = {}
    for p in pairs:
        by_col.setdefault(p["collection"], []).append(p)

    chosen = []
    per = max(1, MAX_PAIRS // max(1, len(by_col)))
    for _col, plist in by_col.items():
        def score(p):
            langs = {p.get("source_language"), p.get("target_language")}
            return (
                0 if "en" in langs else 1,
                0 if ({"de", "fr", "es", "it"} & langs) else 1,
                p.get("id", ""),
            )

        chosen.extend(sorted(plist, key=score)[:per])
    chosen = chosen[:MAX_PAIRS]

    rows_by_pair = {}
    pair_infos = {}
    def pack_row(e, info, pid):
        return {
            "source_word": e.get("source_word") or "",
            "translation": e.get("translation") or "",
            "pos": e.get("pos") or "",
            "pos_tag": e.get("pos_tag") or "",
            "synset_id": e.get("synset_id"),
            "meaning": e.get("source_word") or "",
            "headword": e.get("source_word") or "",
            "pair_id": pid,
            "pair_title": info.get("title") or pid,
            "collection": info.get("collection"),
            "collection_title": info.get("collection_title") or info.get("collection"),
            "source_language": info.get("source_language"),
            "target_language": info.get("target_language"),
            "source_language_name": info.get("source_language_name"),
            "target_language_name": info.get("target_language_name"),
            "license": info.get("license") or "",
            "reverse_pair_id": info.get("reverse_pair_id"),
            "source_sense_uri": e.get("source_sense_uri"),
            "target_sense_uri": e.get("target_sense_uri"),
            "link_uri": e.get("link_uri"),
        }

    for p in chosen:
        pid = p["id"]
        try:
            info = store.pair_info(pid)
            pool = store._load_entries(pid, SCAN_PER_PAIR)
        except Exception as e:
            print(f"  skip {pid}: {e}")
            continue
        if not pool:
            print(f"  empty rows {pid}")
            continue
        seeds = []
        rest = []
        for e in pool:
            blob = {
                (e.get("source_word") or "").lower(),
                (e.get("translation") or "").lower(),
            }
            if blob & SEED_WORDS:
                seeds.append(e)
            else:
                rest.append(e)
        # Spread sample across the file so demos are not stuck on letter "a".
        if len(rest) <= ROWS_PER_PAIR:
            picked = rest
        else:
            step = len(rest) / ROWS_PER_PAIR
            idxs = sorted({min(len(rest) - 1, int(j * step)) for j in range(ROWS_PER_PAIR)})
            picked = [rest[i] for i in idxs]
        # Prefer seed hits first, then fill.
        merged = []
        seen = set()
        for e in seeds + picked:
            key = (e.get("source_word"), e.get("translation"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(e)
            if len(merged) >= ROWS_PER_PAIR:
                break
        rows = [pack_row(e, info, pid) for e in merged]
        rows_by_pair[pid] = rows
        pair_infos[pid] = info
        print(f"  dict {pid}: {len(rows)} rows (seeds {len(seeds)})")

    chosen = [p for p in chosen if p["id"] in rows_by_pair]

    # Patch dimensions to demo scale
    demo_dims = dict(dims)
    demo_dims["pair_count"] = len(chosen)
    demo_dims["browsable_pair_count"] = len(chosen)
    demo_dims["open_pair_count"] = len(chosen)
    demo_dims["browsable_collections"] = [c["id"] for c in cols]
    demo_counts = {
        cid: sum(1 for p in chosen if p.get("collection") == cid) for cid in DICT_COLLECTIONS
    }
    demo_dims["collection_counts"] = dict(demo_counts)
    demo_dims["sources"] = [
        s for s in (dims.get("sources") or []) if s.get("id") in DICT_COLLECTIONS
    ]
    for s in demo_dims["sources"]:
        s["pair_count"] = demo_counts.get(s["id"], 0)

    bundle = {
        "dimensions": demo_dims,
        "collections": {
            "collections": cols,
            "capability_catalog": CAPABILITY_CATALOG,
            "meta": {"demo": True, "note": "Static subset for GitHub Pages"},
        },
        "pairs": {"pairs": chosen, "count": len(chosen)},
        "pair_info": pair_infos,
        "rows": rows_by_pair,
        "meta": {
            "pair_count": len(chosen),
            "row_total": sum(len(v) for v in rows_by_pair.values()),
            "note": "Baked dictionary rows for offline suggest / bridges / export",
        },
    }
    _write_json(DOCS / "api" / "dicts" / "bundle.json", bundle)
    # Also write thin endpoints for clarity
    _write_json(DOCS / "api" / "dicts" / "dimensions.json", demo_dims)
    _write_json(DOCS / "api" / "dicts" / "collections.json", bundle["collections"])
    _write_json(DOCS / "api" / "dicts" / "pairs.json", bundle["pairs"])
    return bundle["meta"]


def _patch_html(src: Path, dest: Path, *, kind: str) -> None:
    text = src.read_text(encoding="utf-8")
    # Inject static API shim early
    shim = '<script src="../shared/static_api.js"></script>\n' if kind != "hub" else '<script src="./shared/static_api.js"></script>\n'
    if "<head>" in text:
        text = text.replace("<head>", "<head>\n" + shim, 1)
    else:
        text = shim + text

    if kind == "hub":
        text = text.replace('href="/sentence_reader/"', 'href="./sentence_reader/"')
        text = text.replace('href="/dict_graph_reader/"', 'href="./dict_graph_reader/"')
        text = text.replace('href="/shared/tool.css"', 'href="./shared/tool.css"')
        text = text.replace('href="/html/resource_guide.html"', 'href="./"')
    elif kind == "sentence":
        text = text.replace('href="/shared/tool.css"', 'href="../shared/tool.css"')
        text = text.replace('href="/"', 'href="../"')
        text = text.replace(">All apps<", ">Lab Hub<")
    elif kind == "dict":
        text = text.replace('href="/shared/tool.css"', 'href="../shared/tool.css"')
        text = text.replace('href="/"', 'href="../"')
        text = text.replace(">All apps<", ">Lab Hub<")

    dest.write_text(text, encoding="utf-8")


def copy_ui() -> None:
    shutil.copy2(APPS / "shared" / "tool.css", DOCS / "shared" / "tool.css")
    _patch_html(APPS / "html" / "apps_index.html", DOCS / "index.html", kind="hub")
    _patch_html(
        APPS / "historical_sentence_reader" / "index.html",
        DOCS / "sentence_reader" / "index.html",
        kind="sentence",
    )
    _patch_html(
        APPS / "dict_graph_reader" / "index.html",
        DOCS / "dict_graph_reader" / "index.html",
        kind="dict",
    )


def main() -> None:
    print("Building static Lab Hub demo ->", DOCS)
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    print("UI copies…")
    copy_ui()

    print("Corpora…")
    cstore = CorpusStore(SAMPLES, AUGSBURG)
    corp_meta = export_corpora(cstore)

    print("Dictionaries…")
    dstore = DictStore(SAMPLES, AUGSBURG)
    dict_meta = export_dicts(dstore)

    summary = {
        "corpora": [{"id": a, "demo_sentences": b, "source_total": c} for a, b, c in corp_meta["stats"]],
        "dict": dict_meta,
        "pages": {
            "hub": "docs/index.html",
            "sentence_reader": "docs/sentence_reader/",
            "dictionary": "docs/dict_graph_reader/",
        },
    }
    _write_json(ROOT / "demo_manifest.json", summary)
    print("DONE")
    print(json.dumps({"corpus_count": len(corp_meta["stats"]), "sentence_total": sum(x[1] for x in corp_meta["stats"]), "dict": dict_meta}, indent=2))


if __name__ == "__main__":
    main()
