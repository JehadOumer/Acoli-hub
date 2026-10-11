/* Static GitHub Pages API shim for ACoLi Lab Hub demo */
(function () {
  "use strict";

  function basePrefix() {
    // docs/index.html -> ./
    // docs/sentence_reader/ -> ../
    // docs/dict_graph_reader/ -> ../
    var path = location.pathname.replace(/\\/g, "/");
    if (/\/sentence_reader(\/|$)/.test(path) || /\/dict_graph_reader(\/|$)/.test(path)) {
      return "..";
    }
    return ".";
  }

  var BASE = basePrefix();
  var corpCache = Object.create(null);
  var dictBundle = null;
  var corporaList = null;

  function jsonResponse(obj, status) {
    return new Response(JSON.stringify(obj), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  function textResponse(text, status, headers) {
    return new Response(text, {
      status: status || 200,
      headers: Object.assign({ "Content-Type": "text/plain; charset=utf-8" }, headers || {}),
    });
  }

  async function loadCorporaList() {
    if (corporaList) return corporaList;
    var r = await fetch(BASE + "/api/corpora.json");
    corporaList = await r.json();
    return corporaList;
  }

  async function loadCorpus(id) {
    if (corpCache[id]) return corpCache[id];
    var r = await fetch(BASE + "/api/corpora/" + encodeURIComponent(id) + ".json");
    if (!r.ok) throw new Error("corpus missing: " + id);
    corpCache[id] = await r.json();
    return corpCache[id];
  }

  async function loadDict() {
    if (dictBundle) return dictBundle;
    var r = await fetch(BASE + "/api/dicts/bundle.json");
    dictBundle = await r.json();
    return dictBundle;
  }

  function parseQuery(url) {
    var u = new URL(url, location.origin);
    var q = {};
    u.searchParams.forEach(function (v, k) {
      q[k] = v;
    });
    return { path: u.pathname, query: q, url: u };
  }

  function apiPath(url) {
    var abs = url;
    try {
      abs = new URL(url, location.href).pathname;
    } catch (e) {}
    var m = abs.match(/\/api\/(.*)$/);
    return m ? m[1] : null;
  }

  async function handleCorpora(rest, query) {
    if (!rest || rest === "") {
      return jsonResponse(await loadCorporaList());
    }
    var parts = rest.split("/").filter(Boolean);
    var id = decodeURIComponent(parts[0] || "");
    if (parts.length === 1 || (parts.length >= 1 && !parts[1])) {
      var bundle = await loadCorpus(id);
      var offset = Math.max(0, parseInt(query.offset || "0", 10) || 0);
      var limit = Math.min(500, Math.max(1, parseInt(query.limit || "100", 10) || 100));
      var q = (query.q || "").trim().toLowerCase();
      var list = bundle.sentences || [];
      if (q) {
        list = list.filter(function (s) {
          return (
            String(s.text || "").toLowerCase().indexOf(q) >= 0 ||
            String(s.label || "").toLowerCase().indexOf(q) >= 0
          );
        });
      }
      var slice = list.slice(offset, offset + limit);
      return jsonResponse({
        id: bundle.id,
        button: bundle.button,
        title: bundle.title,
        short: bundle.short,
        description: bundle.description,
        language: bundle.language,
        lang_code: bundle.lang_code,
        annotation_summary: bundle.annotation_summary,
        best_for: bundle.best_for,
        has_dependencies: bundle.has_dependencies,
        license_tier: bundle.license_tier,
        license_note: bundle.license_note,
        github: bundle.github,
        acoli_github: bundle.acoli_github,
        external_github: bundle.external_github,
        origin: bundle.origin,
        citation: bundle.citation,
        reference: bundle.reference,
        layers: bundle.layers,
        profile: bundle.profile,
        sentence_count: bundle.sentence_count,
        source_entries: bundle.source_entries,
        imported_entries: bundle.imported_entries,
        source_count: bundle.source_count,
        columns: bundle.columns,
        match_count: list.length,
        offset: offset,
        limit: limit,
        q: query.q || "",
        sentences: slice,
        store: "static-demo",
        backend: "baked-json",
      });
    }
    if (parts[1] === "sentences" && parts[2] != null) {
      var idx = parseInt(parts[2], 10);
      var corp = await loadCorpus(id);
      var full = (corp.full_sentences || [])[idx];
      if (!full) return jsonResponse({ detail: "Sentence out of range" }, 404);
      return jsonResponse(full);
    }
    return jsonResponse({ detail: "Not found" }, 404);
  }

  function rowToSuggestion(row, query, side) {
    return {
      query_side: side,
      source_word: row.source_word,
      translation: row.translation,
      meaning: row.meaning || row.source_word,
      headword: row.headword || row.source_word,
      pos: row.pos || "",
      pos_tag: row.pos_tag || "",
      synset_id: row.synset_id || null,
      synset_uri: null,
      source_sense_uri: null,
      target_sense_uri: null,
      link_uri: null,
      pair_id: row.pair_id,
      pair_title: row.pair_title,
      reverse_pair_id: row.reverse_pair_id || null,
      collection: row.collection,
      collection_title: row.collection_title,
      source_language: row.source_language,
      target_language: row.target_language,
      source_language_name: row.source_language_name,
      target_language_name: row.target_language_name,
      license: row.license || "",
    };
  }

  async function handleDicts(rest, query) {
    var bundle = await loadDict();
    var parts = rest.split("/").filter(Boolean);

    if (parts[0] === "dimensions") return jsonResponse(bundle.dimensions);
    if (parts[0] === "collections") return jsonResponse(bundle.collections);
    if (parts[0] === "pairs" && parts.length === 1) {
      return jsonResponse(bundle.pairs);
    }

    if (parts[0] === "suggest") {
      var q = (query.q || "").trim().toLowerCase();
      var limit = Math.min(80, Math.max(1, parseInt(query.limit || "48", 10) || 48));
      var collections = (query.collections || "").split(",").filter(Boolean);
      var language = (query.language || "").trim().toLowerCase();
      var pos = (query.pos || "").trim().toLowerCase();
      var hits = [];
      if (q) {
        Object.keys(bundle.rows).forEach(function (pid) {
          var meta = (bundle.pair_info || {})[pid] || {};
          if (collections.length && collections.indexOf(meta.collection || "") < 0) return;
          bundle.rows[pid].forEach(function (row) {
            if (language) {
              if (
                String(row.source_language || "").toLowerCase() !== language &&
                String(row.target_language || "").toLowerCase() !== language
              ) {
                return;
              }
            }
            if (pos && String(row.pos || "").toLowerCase().indexOf(pos) < 0) return;
            var src = String(row.source_word || "").toLowerCase();
            var tgt = String(row.translation || "").toLowerCase();
            var side = null;
            if (src === q || src.indexOf(q) === 0) side = "source";
            else if (tgt === q || tgt.indexOf(q) === 0) side = "target";
            else if (src.indexOf(q) >= 0) side = "source";
            else if (tgt.indexOf(q) >= 0) side = "target";
            if (!side) return;
            hits.push(rowToSuggestion(row, q, side));
          });
        });
      }
      // Prefer exact / prefix
      hits.sort(function (a, b) {
        function rank(h) {
          var w = (h.query_side === "target" ? h.translation : h.source_word) || "";
          w = w.toLowerCase();
          if (w === q) return 0;
          if (w.indexOf(q) === 0) return 1;
          return 2;
        }
        return rank(a) - rank(b);
      });
      var sliced = hits.slice(0, limit);
      return jsonResponse({
        query: query.q || "",
        language: query.language || null,
        language_name: null,
        collections: collections,
        collection: null,
        pair_id: null,
        pos: query.pos || null,
        pairs_searched: Object.keys(bundle.rows).length,
        match_count: hits.length,
        suggestions: sliced,
        hint: hits.length ? null : "No matches in the static demo lexicon subset.",
      });
    }

    if (parts[0] === "bridges") {
      var bqRaw = (query.q || "").trim();
      var bq = bqRaw.toLowerCase();
      var via = (query.via || "en").toLowerCase();
      // Prefer server-baked, language-locked induced paths when available
      if (bq && bundle.bridges_cache && bundle.bridges_cache[bq]) {
        return jsonResponse(bundle.bridges_cache[bq]);
      }

      var langName = function (code) {
        var langs = (bundle.dimensions && bundle.dimensions.languages) || [];
        for (var i = 0; i < langs.length; i++) {
          if (langs[i].code === code) return langs[i].name || code;
        }
        return code || "?";
      };
      var node = function (word, code, role) {
        return {
          word: word,
          language: code,
          language_name: langName(code),
          role: role || "mid",
        };
      };

      // Fallback: induce A→B→C… from baked rows (language-locked, no self-loops)
      var paths = [];
      var byHops = { "2": [], "3": [], "4": [] };
      if (bq) {
        function neighbors(word, lockLang) {
          var w = String(word || "").toLowerCase();
          var out = [];
          var seen = {};
          Object.keys(bundle.rows).forEach(function (pid) {
            bundle.rows[pid].forEach(function (row) {
              var src = String(row.source_word || "");
              var tgt = String(row.translation || "");
              var sl = String(row.source_language || "").toLowerCase();
              var tl = String(row.target_language || "").toLowerCase();
              var other = null;
              var otherLang = null;
              var selfLang = null;
              if (lockLang) {
                if (src.toLowerCase() === w && sl === lockLang) {
                  other = tgt;
                  otherLang = tl;
                  selfLang = sl;
                } else if (tgt.toLowerCase() === w && tl === lockLang) {
                  other = src;
                  otherLang = sl;
                  selfLang = tl;
                }
              } else {
                if (src.toLowerCase() === w) {
                  other = tgt;
                  otherLang = tl;
                  selfLang = sl;
                } else if (tgt.toLowerCase() === w) {
                  other = src;
                  otherLang = sl;
                  selfLang = tl;
                }
              }
              if (!other || !otherLang) return;
              var ol = other.toLowerCase();
              if (ol === w) return; // self-loop
              var key = otherLang + ":" + ol;
              if (seen[key]) return;
              seen[key] = 1;
              out.push({
                word: other,
                language: otherLang,
                language_name: row.source_language === otherLang
                  ? row.source_language_name
                  : row.target_language_name || langName(otherLang),
                self_language: selfLang,
                entry: rowToSuggestion(
                  row,
                  w,
                  src.toLowerCase() === w ? "source" : "target"
                ),
                collection: row.collection_title || row.collection,
                collection_id: row.collection,
              });
            });
          });
          return out;
        }

        var direct = neighbors(bq, null);
        var startLang = via;
        var votes = {};
        direct.forEach(function (n) {
          var sl = n.self_language || "";
          if (sl) votes[sl] = (votes[sl] || 0) + 1;
        });
        var best = 0;
        Object.keys(votes).forEach(function (k) {
          if (votes[k] > best) {
            best = votes[k];
            startLang = k;
          }
        });
        var directEnds = {};
        direct.forEach(function (n) {
          directEnds[String(n.word).toLowerCase()] = 1;
          directEnds[n.language + ":" + String(n.word).toLowerCase()] = 1;
        });
        directEnds[bq] = 1;

        var frontier = [];
        var seedTips = {};
        direct.slice(0, 14).forEach(function (n) {
          var tipKey = n.language + ":" + String(n.word).toLowerCase();
          if (seedTips[tipKey]) return;
          seedTips[tipKey] = 1;
          frontier.push({
            nodes: [
              node(bqRaw || bq, startLang, "start"),
              node(n.word, n.language, "end"),
            ],
            seenNodes: {},
            seenWords: {},
            entry: n.entry,
            collections: [n.collection],
            collection_ids: [n.collection_id],
          });
          frontier[frontier.length - 1].seenNodes[startLang + ":" + bq] = 1;
          frontier[frontier.length - 1].seenNodes[tipKey] = 1;
          frontier[frontier.length - 1].seenWords[bq] = 1;
          frontier[frontier.length - 1].seenWords[String(n.word).toLowerCase()] = 1;
        });

        var seenEnds = {};
        var beam = 6;
        for (var hops = 2; hops <= 4; hops++) {
          var next = [];
          frontier.slice(0, beam).forEach(function (prev) {
            var tip = prev.nodes[prev.nodes.length - 1];
            var tipW = tip.word;
            var tipLang = tip.language;
            if (!tipW || !tipLang) return;
            neighbors(tipW, tipLang).forEach(function (n) {
              var wl = String(n.word).toLowerCase();
              var endKey = n.language + ":" + wl;
              if (wl === String(tipW).toLowerCase()) return;
              if (wl === bq) return;
              if (prev.seenNodes[endKey] || prev.seenWords[wl]) return;
              var nodes = prev.nodes.map(function (x, i) {
                return Object.assign({}, x, {
                  role: i === 0 ? "start" : "mid",
                });
              });
              nodes.push(node(n.word, n.language, "end"));
              var state = {
                nodes: nodes,
                seenNodes: Object.assign({}, prev.seenNodes),
                seenWords: Object.assign({}, prev.seenWords),
                entry: n.entry || prev.entry,
                collections: prev.collections.concat([n.collection]).filter(Boolean),
                collection_ids: prev.collection_ids
                  .concat([n.collection_id])
                  .filter(Boolean),
              };
              state.seenNodes[endKey] = 1;
              state.seenWords[wl] = 1;
              var isDirect = directEnds[wl] || directEnds[endKey];
              if (!isDirect && !seenEnds[endKey] && (byHops[String(hops)] || []).length < 8) {
                seenEnds[endKey] = 1;
                var pathObj = {
                  hops: hops,
                  bridge_count: hops - 1,
                  label: hops + " hops",
                  path: nodes,
                  end_word: n.word,
                  end_language: n.language,
                  end_language_name: n.language_name || langName(n.language),
                  bridge_words: nodes.slice(1, -1).map(function (x) {
                    return x.word;
                  }),
                  collections: state.collections.filter(function (c, i, a) {
                    return a.indexOf(c) === i;
                  }),
                  collection_ids: state.collection_ids.filter(function (c, i, a) {
                    return a.indexOf(c) === i;
                  }),
                  entry: state.entry,
                };
                byHops[String(hops)].push(pathObj);
                paths.push(pathObj);
              }
              if (hops < 4 && next.length < beam * 2) next.push(state);
            });
          });
          next.sort(function (a, b) {
            var ae = a.nodes[a.nodes.length - 1].language === via ? 0 : 1;
            var be = b.nodes[b.nodes.length - 1].language === via ? 0 : 1;
            return ae - be;
          });
          frontier = next.slice(0, beam);
          if (!frontier.length) break;
        }
      }
      var two = byHops["2"] || [];
      var longer = (byHops["3"] || []).concat(byHops["4"] || []);
      return jsonResponse({
        query: bqRaw,
        via: via,
        via_name: langName(via),
        paths: paths.slice(0, 24),
        by_hops: byHops,
        one_hop: two,
        multi_hop: longer,
        one_hop_count: two.length,
        multi_hop_count: longer.length,
        bridge_forms: [],
        hint: paths.length
          ? paths.length + " induced paths from the static demo lexicon."
          : "No bridge paths in the static demo subset.",
      });
    }

    if (parts[0] === "pairs" && parts.length >= 2) {
      var pairId = decodeURIComponent(parts[1]);
      // nested path segments may include encoded slashes already joined — FastAPI used {pair_id:path}
      if (parts.length > 3) {
        pairId = decodeURIComponent(parts.slice(1, parts.length - 1).join("/"));
      }
      // recover pair id when URL is pairs/freedict:de-en/info
      var action = parts[parts.length - 1];
      if (parts.length >= 3) {
        pairId = decodeURIComponent(parts.slice(1, -1).join("/"));
      }

      if (action === "info") {
        var info = (bundle.pair_info || {})[pairId];
        if (!info) return jsonResponse({ detail: "Unknown pair" }, 404);
        return jsonResponse(info);
      }

      if (action === "reverse") {
        var sw = (query.source_word || "").toLowerCase();
        var tr = (query.translation || "").toLowerCase();
        var meta = (bundle.pair_info || {})[pairId] || {};
        var rid = meta.reverse_pair_id;
        var entry = null;
        if (rid && bundle.rows[rid]) {
          bundle.rows[rid].forEach(function (row) {
            if (entry) return;
            if (
              String(row.source_word || "").toLowerCase() === tr &&
              String(row.translation || "").toLowerCase() === sw
            ) {
              entry = rowToSuggestion(row, tr, "source");
            }
          });
        }
        if (!entry) {
          // flipped view on same pair rows
          (bundle.rows[pairId] || []).forEach(function (row) {
            if (entry) return;
            if (
              String(row.source_word || "").toLowerCase() === sw &&
              String(row.translation || "").toLowerCase() === tr
            ) {
              entry = rowToSuggestion(
                {
                  source_word: row.translation,
                  translation: row.source_word,
                  pos: row.pos,
                  pos_tag: row.pos_tag,
                  synset_id: row.synset_id,
                  meaning: row.translation,
                  headword: row.translation,
                  pair_id: rid || pairId,
                  pair_title: row.pair_title,
                  collection: row.collection,
                  collection_title: row.collection_title,
                  source_language: row.target_language,
                  target_language: row.source_language,
                  source_language_name: row.target_language_name,
                  target_language_name: row.source_language_name,
                  license: row.license,
                  reverse_pair_id: pairId,
                },
                tr,
                "source"
              );
            }
          });
        }
        if (!entry) return jsonResponse({ detail: "No reverse sibling" }, 404);
        return jsonResponse({ entry: entry });
      }

      if (action === "export") {
        var eq = (query.q || "").toLowerCase();
        var format = (query.format || "tsv").toLowerCase();
        var elimit = Math.min(500, Math.max(1, parseInt(query.limit || "500", 10) || 500));
        var erows = (bundle.rows[pairId] || []).filter(function (row) {
          if (!eq) return true;
          return (
            String(row.source_word || "").toLowerCase().indexOf(eq) >= 0 ||
            String(row.translation || "").toLowerCase().indexOf(eq) >= 0
          );
        }).slice(0, elimit);
        if (format === "json") {
          return jsonResponse({ pair_id: pairId, rows: erows, count: erows.length });
        }
        if (format === "csv") {
          var csv = "source_word,translation,pos\n" + erows.map(function (r) {
            return [r.source_word, r.translation, r.pos || ""]
              .map(function (x) { return '"' + String(x).replace(/"/g, '""') + '"'; })
              .join(",");
          }).join("\n");
          return textResponse(csv, 200, {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="' + pairId.replace(/[:/]/g, "_") + '.csv"',
          });
        }
        var tsv = "source_word\ttranslation\tpos\n" + erows.map(function (r) {
          return [r.source_word, r.translation, r.pos || ""].join("\t");
        }).join("\n");
        return textResponse(tsv, 200, {
          "Content-Type": "text/tab-separated-values; charset=utf-8",
          "Content-Disposition": 'attachment; filename="' + pairId.replace(/[:/]/g, "_") + '.tsv"',
        });
      }
    }

    return jsonResponse({ detail: "Not found in static demo: " + rest }, 404);
  }

  async function handleApi(rest, fullUrl) {
    var parsed = parseQuery(fullUrl);
    var q = parsed.query;
    if (rest.indexOf("corpora") === 0) {
      var cRest = rest === "corpora" ? "" : rest.replace(/^corpora\/?/, "");
      // static files use corpora.json — list has no trailing path
      if (!cRest) return handleCorpora("", q);
      return handleCorpora(cRest, q);
    }
    if (rest.indexOf("dicts/") === 0 || rest === "dicts") {
      return handleDicts(rest.replace(/^dicts\/?/, ""), q);
    }
    return jsonResponse({ detail: "Unknown API " + rest }, 404);
  }

  var nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : input && input.url;
    if (!url) return nativeFetch(input, init);
    var rest = apiPath(url);
    if (rest == null) return nativeFetch(input, init);
    // Allow real static file fetches for our baked JSON
    if (/\.json(\?|$)/.test(url) && url.indexOf("/api/") >= 0) {
      return nativeFetch(input, init);
    }
    return handleApi(rest, url);
  };

  // Dictionary export uses window.location navigation; rewrite to blob download.
  var locDesc = Object.getOwnPropertyDescriptor(window, "location");
  // Patch by intercepting assignment via a helper used if apps set location — instead hook click path:
  var _assign = window.location.assign.bind(window.location);
  try {
    window.location.assign = function (url) {
      var rest = apiPath(String(url));
      if (rest && rest.indexOf("dicts/") === 0) {
        handleApi(rest, String(url)).then(async function (resp) {
          var blob = await resp.blob();
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          var cd = resp.headers.get("Content-Disposition") || "";
          var m = cd.match(/filename=\"?([^\";]+)\"?/);
          a.download = m ? m[1] : "export.txt";
          document.body.appendChild(a);
          a.click();
          a.remove();
        });
        return;
      }
      return _assign(url);
    };
  } catch (e) {}

  // Also trap direct window.location = for exportNow
  try {
    var htmlLoc = window.location;
    // Monkey-patch by wrapping export at runtime after load is fragile; use click capture on same-origin API navigations via beforeunload? Better: override Location setter via history.
  } catch (e2) {}

  // Intercept export by patching after DOM ready: replace exportNow if present
  document.addEventListener("DOMContentLoaded", function () {
    if (typeof window.exportNow === "function") {
      var origExport = window.exportNow;
      window.exportNow = function (format) {
        try {
          if (!window.state || !window.state.selected) return origExport(format);
        } catch (e) {}
        // Fall through to original which sets location; we intercept via fetch-based rewrite:
        var sel = window.state && window.state.selected;
        if (!sel) return;
        var side = sel.query_side || "source";
        var q =
          side === "target"
            ? sel.translation || sel.headword || ""
            : sel.source_word || sel.headword || "";
        var url =
          "/api/dicts/pairs/" +
          encodeURIComponent(sel.pair_id) +
          "/export?format=" +
          encodeURIComponent(format) +
          "&mode=results&q=" +
          encodeURIComponent(q) +
          "&limit=500";
        handleApi(apiPath(url), url).then(async function (resp) {
          var blob = await resp.blob();
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          var cd = resp.headers.get("Content-Disposition") || "";
          var m = cd.match(/filename=\"?([^\";]+)\"?/);
          a.download = m ? m[1] : "export." + format;
          document.body.appendChild(a);
          a.click();
          a.remove();
        });
      };
    }
  });

  console.info("[labhub-static] API shim active · base=" + BASE);
})();
