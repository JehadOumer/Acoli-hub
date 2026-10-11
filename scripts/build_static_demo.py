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
ROWS_PER_PAIR = 750
SCAN_PER_PAIR = 24000
MAX_PAIRS = 64
# Prefer lemmas that demo both direct hits and induced bridges in the static UI.
SEED_WORDS = {
    "love", "house", "water", "amour", "tree", "book", "hand", "man", "woman",
    "day", "night", "good", "new", "old", "city", "king", "god", "dog", "sun",
    "haus", "liebe", "wasser", "baum", "buch", "amor", "casa", "eau", "home",
}
# Queries that get server-computed induced paths baked in (correct language locks).
DEMO_BRIDGE_QUERIES = (
    "house", "water", "amour", "love", "haus", "tree", "casa", "liebe",
)


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
    listed = store.list_pairs(browsable_only=True, limit=5000)
    pairs = [p for p in listed.get("pairs", []) if p.get("collection") in DICT_COLLECTIONS]
    by_id = {p["id"]: p for p in pairs}

    # Precompute real induced paths (language-locked) from the live store
    bridges_cache: dict[str, dict] = {}
    force_pair_ids: set[str] = set()
    for q in DEMO_BRIDGE_QUERIES:
        try:
            payload = store.bridges(q, via="en", max_hops=4, limit=16)
        except Exception as e:
            print(f"  bridges skip {q}: {e}")
            continue
        # Drop heavy nested entry blobs; keep path annotations
        slim_paths = []
        for path in payload.get("paths") or []:
            p = dict(path)
            ent = p.get("entry")
            if isinstance(ent, dict):
                p["entry"] = {
                    k: ent.get(k)
                    for k in (
                        "source_word",
                        "translation",
                        "pos",
                        "synset_id",
                        "pair_id",
                        "pair_title",
                        "collection",
                        "collection_title",
                        "source_language",
                        "target_language",
                        "source_language_name",
                        "target_language_name",
                        "query_side",
                        "headword",
                        "meaning",
                        "reverse_pair_id",
                    )
                    if ent.get(k) is not None
                }
            for cid in p.get("collection_ids") or []:
                pass
            for node in p.get("path") or []:
                # Ensure UI fields
                if node.get("language") and not node.get("language_name"):
                    node["language_name"] = node["language"]
            slim_paths.append(p)
            for cid in path.get("collection_ids") or []:
                if cid:
                    force_pair_ids.add(cid)
            ent = path.get("entry") or {}
            if ent.get("pair_id"):
                force_pair_ids.add(ent["pair_id"])
        by_hops: dict[str, list] = {}
        for path in slim_paths:
            by_hops.setdefault(str(path.get("hops") or 2), []).append(path)
        bridges_cache[q.lower()] = {
            "query": q,
            "via": "en",
            "via_name": "English",
            "paths": slim_paths,
            "by_hops": by_hops,
            "one_hop": [p for p in slim_paths if (p.get("hops") or 0) == 2],
            "multi_hop": [p for p in slim_paths if (p.get("hops") or 0) >= 3],
            "one_hop_count": sum(1 for p in slim_paths if (p.get("hops") or 0) == 2),
            "multi_hop_count": sum(1 for p in slim_paths if (p.get("hops") or 0) >= 3),
            "bridge_forms": payload.get("bridge_forms") or [],
            "direct_neighbor_count": payload.get("direct_neighbor_count") or 0,
            "max_hops": 4,
            "hint": payload.get("hint"),
        }
        print(
            f"  bridges {q}: {len(slim_paths)} paths "
            f"(2h={bridges_cache[q.lower()]['one_hop_count']} "
            f"3+={bridges_cache[q.lower()]['multi_hop_count']})"
        )

    # Also pull pairs that hold seed lemmas (either side)
    for seed in sorted(SEED_WORDS):
        try:
            nbrs = store._exact_neighbors(
                seed,
                language=None,
                either_side=True,
                limit=16,
                pairs_cap=20,
                scan_rows=8000,
                prefer_via="en",
            )
        except Exception:
            continue
        for n in nbrs:
            if n.get("pair_id"):
                force_pair_ids.add(n["pair_id"])

    by_col: dict[str, list] = {}
    for p in pairs:
        by_col.setdefault(p["collection"], []).append(p)

    # Prefer English-linked pairs + diversity of the other language
    preferred_other = {
        "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "ru", "sv", "da", "fi",
        "hu", "el", "tr", "ar", "he", "ja", "zh", "ko", "hi", "eu", "ca", "gl",
        "ro", "bg", "uk", "sk", "sl", "hr", "sr", "ga", "cy", "is", "la",
    }

    def score(p: dict) -> tuple:
        langs = {p.get("source_language"), p.get("target_language")}
        other = (langs - {"en"}) or langs
        return (
            0 if "en" in langs else 1,
            0 if (other & preferred_other) else 1,
            0 if p["id"] in force_pair_ids else 1,
            p.get("bytes") or 0,
            p.get("id", ""),
        )

    chosen_ids: list[str] = []
    seen_ids: set[str] = set()

    # Guarantee every open collection appears, then force/bridge pairs, then fill
    per_col_floor = 4
    for col in DICT_COLLECTIONS:
        plist = by_col.get(col) or []
        for p in sorted(plist, key=score)[:per_col_floor]:
            if p["id"] not in seen_ids:
                chosen_ids.append(p["id"])
                seen_ids.add(p["id"])

    for pid in sorted(force_pair_ids):
        if pid in by_id and pid not in seen_ids and len(chosen_ids) < MAX_PAIRS:
            chosen_ids.append(pid)
            seen_ids.add(pid)

    # Round-robin fill for more language coverage
    per = max(4, MAX_PAIRS // max(1, len(by_col)))
    for _col, plist in by_col.items():
        for p in sorted(plist, key=score)[:per]:
            if p["id"] not in seen_ids:
                chosen_ids.append(p["id"])
                seen_ids.add(p["id"])
            if len(chosen_ids) >= MAX_PAIRS:
                break
        if len(chosen_ids) >= MAX_PAIRS:
            break

    if len(chosen_ids) < MAX_PAIRS:
        have_langs = set()
        for pid in chosen_ids:
            p = by_id[pid]
            have_langs.add(p.get("source_language"))
            have_langs.add(p.get("target_language"))
        for p in sorted(pairs, key=score):
            if p["id"] in seen_ids:
                continue
            langs = {p.get("source_language"), p.get("target_language")}
            if not (langs - have_langs):
                continue
            chosen_ids.append(p["id"])
            seen_ids.add(p["id"])
            have_langs |= langs
            if len(chosen_ids) >= MAX_PAIRS:
                break

    chosen = [by_id[pid] for pid in chosen_ids if pid in by_id][:MAX_PAIRS]

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
        if len(rest) <= ROWS_PER_PAIR:
            picked = rest
        else:
            step = len(rest) / ROWS_PER_PAIR
            idxs = sorted({min(len(rest) - 1, int(j * step)) for j in range(ROWS_PER_PAIR)})
            picked = [rest[i] for i in idxs]
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

    # Dimensions from what is actually baked (counts only)
    open_langs: set[str] = set()
    coll_counts: dict[str, int] = {}
    coll_langs: dict[str, set[str]] = {}
    for p in chosen:
        cid = p["collection"]
        coll_counts[cid] = coll_counts.get(cid, 0) + 1
        for code in (p.get("source_language"), p.get("target_language")):
            if not code:
                continue
            open_langs.add(code)
            coll_langs.setdefault(cid, set()).add(code)

    names = store.catalog.get("language_names", {})
    demo_dims = {
        "about": dims.get("about") or store.catalog.get("meta", {}),
        "collection_counts": coll_counts,
        "collection_language_counts": {
            cid: len(codes) for cid, codes in coll_langs.items()
        },
        "open_source_count": len([c for c in cols if coll_counts.get(c["id"], 0)]),
        "open_pair_count": len(chosen),
        "open_language_count": len(open_langs),
        "language_count": len(open_langs),
        "languages": sorted(
            [{"code": c, "name": names.get(c, c)} for c in open_langs],
            key=lambda x: x["name"],
        ),
        "pair_count": len(chosen),
        "browsable_pair_count": len(chosen),
        "browsable_collections": [c["id"] for c in cols if coll_counts.get(c["id"], 0)],
        "sources": [
            {
                "id": c["id"],
                "title": c["title"],
                "short": c.get("short", ""),
                "license": c.get("license", ""),
                "pair_count": coll_counts.get(c["id"], 0),
                "language_count": len(coll_langs.get(c["id"], set())),
                "browsable": True,
            }
            for c in cols
            if coll_counts.get(c["id"], 0)
        ],
    }

    # Patch collection objects' indexed_pairs to demo scale
    demo_cols = []
    for c in cols:
        cc = dict(c)
        cc["indexed_pairs"] = coll_counts.get(c["id"], 0)
        demo_cols.append(cc)

    bundle = {
        "dimensions": demo_dims,
        "collections": {
            "collections": demo_cols,
            "capability_catalog": CAPABILITY_CATALOG,
            "meta": {"demo": True, "note": "Static subset for GitHub Pages"},
        },
        "pairs": {"pairs": chosen, "count": len(chosen)},
        "pair_info": pair_infos,
        "rows": rows_by_pair,
        "bridges_cache": bridges_cache,
        "meta": {
            "pair_count": len(chosen),
            "row_total": sum(len(v) for v in rows_by_pair.values()),
            "language_count": len(open_langs),
            "bridge_query_count": len(bridges_cache),
            "note": "Baked dictionary rows + precomputed induced bridges for offline demo",
        },
    }
    _write_json(DOCS / "api" / "dicts" / "bundle.json", bundle)
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
