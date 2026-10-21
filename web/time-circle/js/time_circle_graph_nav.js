/**
 * time_circle_graph_nav.js – Kaskade graph navigation (archival to neighbors).
 * Created: 2026-06-28
 * Last updated: 2026-10-21
 */
(function (root) {
  "use strict";

  var EDGE_SECTION_ORDER = ["REFERENCES", "EPISODE_OF", "ABOUT", "TAGGED_WITH", "CO_RECALLED_WITH", "CONTAINS", "SOFT_LINK", "HARD_LINK"];
  var EDGE_SECTION_LABELS = {
    REFERENCES: "References",
    EPISODE_OF: "Episode",
    ABOUT: "People (ABOUT)",
    TAGGED_WITH: "Tags",
    CO_RECALLED_WITH: "Co-Recall",
    CONTAINS: "Contains",
    SOFT_LINK: "Soft-Link",
    HARD_LINK: "Hard-Link",
  };
  var EDGE_COLORS = {
    REFERENCES: "#a855f7",
    ABOUT: "#41dce1",
    EPISODE_OF: "#9dc76d",
    TAGGED_WITH: "#dc8546",
    SOFT_LINK: "#6a8fd8",
    HARD_LINK: "#ef597a",
    default: "#888",
  };

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function log(level, message, ctx) {
    var payload = {
      timestamp: new Date().toISOString(),
      level: level,
      module: "time_circle_graph_nav",
      message: message,
    };
    if (ctx) payload.context = ctx;
    var fn = level === "ERROR" ? console.error : level === "WARN" ? console.warn : console.log;
    fn(JSON.stringify(payload));
  }

  function stripHtmlHint(text) {
    return String(text || "")
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 160);
  }

  function friendlyFetchError(err, status, hint) {
    var raw = String((err && err.message) || err || "");
    if (/did not match the expected pattern/i.test(raw) || err instanceof SyntaxError) {
      return "API returned invalid JSON" + (status ? " (HTTP " + status + ")" : "") +
        (hint ? ": " + hint : "");
    }
    if (status && raw.indexOf("HTTP") !== 0) return "HTTP " + status + (hint ? ": " + hint : "");
    return raw || "Unknown API error";
  }

  function parseFetchBody(r) {
    return r.text().then(function (text) {
      var body = String(text || "");
      if (!body.trim()) throw new Error(friendlyFetchError(null, r.status, "empty response"));
      var ct = (r.headers.get("content-type") || "").toLowerCase();
      var looksJson = ct.indexOf("json") >= 0 || /^[\s[{]/.test(body);
      if (!looksJson) throw new Error(friendlyFetchError(null, r.status, stripHtmlHint(body)));
      try {
        return JSON.parse(body);
      } catch (parseErr) {
        log("ERROR", "json_parse_failed", {
          status: r.status,
          content_type: ct,
          hint: stripHtmlHint(body),
          error: String(parseErr),
        });
        throw new Error(friendlyFetchError(parseErr, r.status, stripHtmlHint(body)));
      }
    });
  }

  function fetchJson(path, opts) {
    var apiBase = (root.TimeCircleData && root.TimeCircleData.CONFIG.apiBase) || "";
    var url = apiBase + path;
    var t0 = performance.now();
    log("DEBUG", "fetch_start", { url: url, method: (opts && opts.method) || "GET" });
    return fetch(url, opts || {}).then(function (r) {
      return parseFetchBody(r).then(function (j) {
        if (!r.ok) {
          var apiMsg = (j && (j.message || j.error)) || "";
          throw new Error(apiMsg ? "HTTP " + r.status + ": " + apiMsg : "HTTP " + r.status);
        }
        log("INFO", "fetch_ok", { url: url, ms: Math.round(performance.now() - t0), status: r.status });
        return j;
      });
    }).catch(function (err) {
      var msg = friendlyFetchError(err);
      log("ERROR", "fetch_failed", { url: url, error: msg, raw: String(err) });
      throw new Error(msg);
    });
  }

  function mediaCountForArchival(a) {
    if (!a) return 0;
    var n = parseInt(a.image_count, 10);
    if (!isNaN(n) && n > 0) return n;
    n = parseInt(a.media_count, 10);
    return !isNaN(n) && n > 0 ? n : 0;
  }

  function mediaBadgeHtml(a, compact) {
    var n = mediaCountForArchival(a);
    if (!n) return "";
    var label = n === 1 ? "1 photo" : n + " photos";
    return '<span class="graph-media-badge' + (compact ? " compact" : "") + '" title="' + escapeHtml(label) + '">' +
      '<span class="graph-media-icon" aria-hidden="true">📷</span>' +
      '<span class="graph-media-count">' + n + "</span></span>";
  }

  function renderArchiveProse(card, detail) {
    var apr = root.ArchiveProseRender;
    if (!apr) {
      return '<pre class="graph-pre graph-pre-fallback">' + escapeHtml((detail && detail.content) || "") + "</pre>";
    }
    return '<div class="graph-archive-prose">' + apr.buildArchiveModalInnerHtml(card || {}, detail || {}) + "</div>";
  }

  function archivalCardInner(a, previewLen) {
    var preview = (a.l1 || a.content_preview || "").substring(0, previewLen || 180);
    return mediaBadgeHtml(a) +
      '<span class="arch-id">' + escapeHtml((a.memory_id || "").slice(0, 12)) + "…</span>" +
      "<span class=\"arch-preview\">" + escapeHtml(preview) + "</span>";
  }

  function patchMemory(memoryId, body) {
    var mid = normMemoryId(memoryId);
    return fetchJson("/api/cascade/memory/" + encodeURIComponent(mid), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function patchPerson(personRef, body) {
    var ref = String(personRef || "").trim();
    return fetchJson("/api/cascade/person/" + encodeURIComponent(ref), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function showGraphToast(message, isOk) {
    var host = document.querySelector("#inlineTree");
    if (!host) return;
    var el = host.querySelector(".graph-save-toast");
    if (!el) {
      el = document.createElement("div");
      el.className = "graph-save-toast";
      host.appendChild(el);
    }
    el.textContent = message;
    el.classList.toggle("ok", !!isOk);
    el.classList.toggle("err", !isOk);
    el.classList.add("visible");
    clearTimeout(showGraphToast._tid);
    showGraphToast._tid = setTimeout(function () {
      el.classList.remove("visible");
    }, 2800);
    log(isOk ? "INFO" : "WARN", "graph_toast", { message: message, ok: !!isOk });
  }

  function aboutPersonsFromEdges(edges, memoryId) {
    var mid = normMemoryId(memoryId);
    var nid = memoryNodeId(mid);
    var out = [];
    var seen = {};
    var normPid = function (ref) {
      if (root.TimeCircleData && root.TimeCircleData.normalizePersonId) {
        return root.TimeCircleData.normalizePersonId(personIdFromRef(ref));
      }
      return personIdFromRef(ref);
    };
    (edges || []).forEach(function (e) {
      if (String(e.type || "") !== "ABOUT") return;
      var src = String(e.source || "");
      var tgt = String(e.target || "");
      var ref = null;
      if (src === nid || src === mid || src === "mem-" + mid) ref = parseTarget(tgt);
      else if (tgt === nid || tgt === mid || tgt === "mem-" + mid) ref = parseTarget(src);
      if (!ref || ref.kind !== "person") return;
      var canosamal = normPid(ref);
      if (!canosamal || seen[canosamal]) return;
      seen[canosamal] = true;
      if (root.TimeCircleData && root.TimeCircleData.personDisplayLabel) {
        ref.label = root.TimeCircleData.personDisplayLabel(canosamal);
      } else {
        ref.label = canosamal;
      }
      ref.canosamalId = canosamal;
      out.push(ref);
    });
    return out;
  }

  function normMemoryId(id) {
    return String(id || "").replace(/^mem-/, "");
  }

  function personIdFromRef(ref) {
    var id = String((ref && ref.id) || "");
    if (id.indexOf("person_") === 0) return id.replace(/^person_/, "");
    return id.replace(/_/g, " ").trim().toLowerCase();
  }

  function parseTimeKey(val) {
    var s = String(val || "").trim();
    if (!s) return "0000-00-00";
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    return s.slice(0, 19);
  }

  function compareTimeKeys(a, b) {
    return parseTimeKey(a).localeCompare(parseTimeKey(b));
  }

  function memoryNodeId(memoryId) {
    var mid = normMemoryId(memoryId);
    return mid ? "mem-" + mid : "";
  }

  function peerFromMemoryEdge(edge, memoryId) {
    var nid = memoryNodeId(memoryId);
    var mid = normMemoryId(memoryId);
    var src = String(edge.source || "");
    var tgt = String(edge.target || "");
    var peer = "";
    if (src === nid || src === mid || src === "mem-" + mid) peer = tgt;
    else if (tgt === nid || tgt === mid || tgt === "mem-" + mid) peer = src;
    else peer = tgt || src;
    return parseTarget(peer);
  }

  function archivalTimeKey(a) {
    var meta = (a && a.metadata) || {};
    return parseTimeKey(meta.episode_date || a.created_at);
  }

  function buildEdgeTimelineNodes(edges, memoryId) {
    var byKey = {};
    (edges || []).forEach(function (e) {
      var ref = peerFromMemoryEdge(e, memoryId);
      if (!ref || !ref.id) return;
      var key = ref.kind + ":" + ref.id;
      var timeKey = ref.kind === "day" ? parseTimeKey(ref.id) : parseTimeKey(e.created_at);
      if (!byKey[key] || compareTimeKeys(timeKey, byKey[key].timeKey) < 0) {
        byKey[key] = {
          id: ref.id,
          kind: ref.kind,
          label: formatLabel(ref),
          shortLabel: formatLabel(ref).slice(0, 10),
          color: edgeColor(e.type),
          edgeType: e.type || "LINK",
          timeKey: timeKey,
        };
      }
    });
    return Object.keys(byKey)
      .map(function (k) { return byKey[k]; })
      .sort(function (a, b) { return compareTimeKeys(a.timeKey, b.timeKey); });
  }

  function buildArchivalTimelineNodes(archivals, color) {
    return (archivals || [])
      .map(function (a) {
        var mid = normMemoryId(a.memory_id || "");
        return {
          id: mid,
          kind: "memory",
          label: (a.l1 || a.content_preview || "").slice(0, 18) || ("mem " + mid.slice(0, 6)),
          shortLabel: mid.slice(0, 6) + "…",
          color: color || "#fbbf24",
          edgeType: "ARCHIVAL",
          timeKey: archivalTimeKey(a),
        };
      })
      .sort(function (a, b) { return compareTimeKeys(a.timeKey, b.timeKey); });
  }

  function spiralXY(index, total, cx, cy) {
    var n = Math.max(1, total);
    var t = index / Math.max(1, n - 1);
    var theta = 0.35 + t * Math.PI * 1.65;
    var radius = 18 + t * 92;
    return {
      x: cx + Math.cos(theta) * radius,
      y: cy + Math.sin(theta) * radius,
      theta: theta,
      radius: radius,
    };
  }

  function formatSpiralRange(nodes) {
    if (!nodes || !nodes.length) return "";
    var first = parseTimeKey(nodes[0].timeKey).slice(0, 10);
    var last = parseTimeKey(nodes[nodes.length - 1].timeKey).slice(0, 10);
    if (first === last) return first;
    return first + " → " + last;
  }

  function parseTarget(target) {
    var t = String(target || "");
    if (t.indexOf("mem-") === 0) return { kind: "memory", id: normMemoryId(t), label: t };
    if (t.indexOf("day_") === 0) return { kind: "day", id: t.substring(4), label: t.substring(4) };
    if (t.indexOf("theme_") === 0) return { kind: "theme", id: t.substring(6), label: t };
    if (t.indexOf("person_") === 0) return { kind: "person", id: t, label: t.replace(/^person_/, "") };
    if (t.indexOf("tag_") === 0) return { kind: "tag", id: t.substring(4), label: t.substring(4).replace(/_/g, "-") };
    if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return { kind: "day", id: t, label: t };
    if (t.indexOf("week:") === 0 || t.indexOf("KW") === 0) return { kind: "week", id: t, label: t };
    return { kind: "node", id: t, label: t };
  }

  function edgeColor(type) {
    return EDGE_COLORS[type] || EDGE_COLORS.default;
  }

  function tagNameFromRef(memoryTags, ref) {
    var normalized = String(ref.id || "").toLowerCase().replace(/-/g, "_");
    if (memoryTags && memoryTags.length) {
      for (var i = 0; i < memoryTags.length; i++) {
        var t = String(memoryTags[i] || "");
        if (t.toLowerCase().replace(/[- ]/g, "_") === normalized) return t;
      }
    }
    return String(ref.label || ref.id || "").replace(/-/g, "_");
  }

  function formatLabel(ref) {
    if (root.TimeCircleData && root.TimeCircleData.formatThemeLabel && ref.kind === "theme") {
      return root.TimeCircleData.formatThemeLabel("theme_" + ref.id);
    }
    if (ref.kind === "person") return ref.label.replace(/_/g, " ");
    if (ref.kind === "day" && root.TimeCircleData) return root.TimeCircleData.formatDayLabel(ref.id, "short");
    if (ref.kind === "memory") return "mem " + ref.id.slice(0, 8) + "…";
    return ref.label;
  }

  function GraphNav(container) {
    this.container = container;
    this.stack = [];
    this.current = null;
    this.wheelIndex = null;
  }

  GraphNav.prototype._renderShell = function (title, breadcrumb) {
    this.container.classList.add("graph-explorer-open");
    this.container.setAttribute("aria-hidden", "false");
    this.container.innerHTML =
      '<button type="button" class="tree-close" id="graphNavClose">×</button>' +
      '<div class="graph-breadcrumb" id="graphBreadcrumb">' + breadcrumb + "</div>" +
      '<div class="graph-title" id="graphTitle">' + escapeHtml(title) + "</div>" +
      '<div class="graph-body" id="graphBody"><p class="graph-loading">Loading…</p></div>' +
      '<div class="graph-mini-wrap">' +
      '<div class="graph-mini-label" id="graphMiniLabel">Time · spiral</div>' +
      '<svg class="graph-mini" id="graphMini" viewBox="0 0 400 300" role="img" aria-labelledby="graphMiniLabel"></svg>' +
      "</div>";
    var self = this;
    this.container.querySelector("#graphNavClose").onclick = function () {
      if (root.__closeTree) root.__closeTree();
      else self.close();
    };
    var backBtn = this.container.querySelector("#graphNavBack");
    if (backBtn) backBtn.onclick = function () { self.back(); };
  };

  GraphNav.prototype._push = function (entry) {
    if (this.current) this.stack.push(this.current);
    this.current = entry;
  };

  GraphNav.prototype.close = function () {
    this.stack = [];
    this.current = null;
    this.container.innerHTML = "";
    this.container.classList.remove("graph-explorer-open");
    this.container.setAttribute("aria-hidden", "true");
    log("INFO", "explorer_closed");
  };

  GraphNav.prototype.back = function () {
    if (!this.stack.length) {
      if (this.wheelIndex != null && root.__restoreInlineTree) {
        root.__restoreInlineTree(this.wheelIndex);
        this.wheelIndex = null;
        log("INFO", "explorer_back_to_wheel");
        return;
      }
      if (root.__closeTree) root.__closeTree();
      else this.close();
      return;
    }
    var prev = this.stack.pop();
    this.current = prev;
    this._restore(prev);
    log("INFO", "explorer_back", { kind: prev.kind, id: prev.id });
  };

  GraphNav.prototype._breadcrumbHtml = function () {
    var parts = this.stack.map(function (s) {
      return '<span class="crumb">' + escapeHtml(s.shortTitle || s.title) + "</span>";
    });
    if (this.current) {
      parts.push('<span class="crumb active">' + escapeHtml(this.current.shortTitle || this.current.title) + "</span>");
    }
    var back = this.stack.length
      ? '<button type="button" class="graph-back" id="graphNavBack">← back</button>'
      : "";
    return back + parts.join('<span class="crumb-sep">›</span>');
  };

  GraphNav.prototype._restore = function (entry) {
    if (entry.kind === "memory") this.openMemory(entry.id, true);
    else if (entry.kind === "theme") this.openTheme(entry.id, true);
    else if (entry.kind === "person") this.openPerson(entry.id, true);
    else if (entry.kind === "day") this.openDay(entry.id, true);
  };

  GraphNav.prototype._drawTemporalSpiralGraph = function (spec) {
    spec = spec || {};
    var svg = this.container.querySelector("#graphMini");
    var labelEl = this.container.querySelector("#graphMiniLabel");
    if (!svg) return;
    var nodes = (spec.nodes || []).slice();
    if (!nodes.length) {
      svg.innerHTML = '<text x="200" y="150" text-anchor="middle" fill="rgba(255,255,255,.35)" font-size="10">no time nodes</text>';
      if (labelEl) labelEl.textContent = "Time · spiral";
      return;
    }
    nodes.sort(function (a, b) {
      var c = compareTimeKeys(a.timeKey, b.timeKey);
      if (c !== 0) return c;
      return String(a.label || "").localeCompare(String(b.label || ""));
    });
    var cx = 200;
    var cy = 148;
    var positions = nodes.map(function (_, i) {
      return spiralXY(i, nodes.length, cx, cy);
    });
    var parts = [];
    parts.push(
      '<path class="graph-spiral-guide" d="' +
      positions.map(function (p, i) {
        return (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1);
      }).join(" ") +
      '" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="1" stroke-dasharray="3 4" />'
    );
    if (positions.length > 1) {
      parts.push(
        '<path class="graph-spiral-spine" d="' +
        positions.map(function (p, i) {
          return (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1);
        }).join(" ") +
        '" fill="none" stroke="rgba(65,220,225,.35)" stroke-width="1.6" />'
      );
    }
    var focusIdx = -1;
    nodes.forEach(function (n, i) {
      if (n.isFocus) focusIdx = i;
    });
    if (focusIdx >= 0) {
      nodes.forEach(function (n, i) {
        if (i === focusIdx || n.isFocus) return;
        var fp = positions[focusIdx];
        var p = positions[i];
        parts.push(
          '<line x1="' + fp.x.toFixed(1) + '" y1="' + fp.y.toFixed(1) + '" x2="' + p.x.toFixed(1) + '" y2="' + p.y.toFixed(1) +
          '" stroke="' + (n.color || "#666") + '" stroke-width="1" opacity="0.28" />'
        );
      });
    }
    nodes.forEach(function (n, i) {
      var p = positions[i];
      var r = n.isFocus ? 8 : 5;
      var stroke = n.isFocus ? "#fff" : "rgba(255,255,255,.25)";
      var navKind = n.kind === "node" ? "" : n.kind;
      var navId = n.id || "";
      var title = (n.edgeType || "") + " · " + parseTimeKey(n.timeKey).slice(0, 10) + " · " + (n.label || "");
      parts.push(
        '<g class="graph-mini-node" data-graph-nav-mini="' + (navKind ? "1" : "0") + '"' +
        (navKind ? ' data-kind="' + escapeHtml(navKind) + '" data-id="' + escapeHtml(navId) + '"' : "") +
        ' role="button" tabindex="0" title="' + escapeHtml(title) + '">' +
        '<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + r + '" fill="' + (n.color || "#888") + '" stroke="' + stroke + '" stroke-width="1.4" />' +
        (n.isFocus
          ? '<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + (r + 4) + '" fill="none" stroke="#41dce1" stroke-width="1" opacity="0.55" />'
          : "") +
        "</g>"
      );
      if (i === 0 || i === nodes.length - 1 || n.isFocus) {
        parts.push(
          '<text x="' + p.x.toFixed(1) + '" y="' + (p.y + 16).toFixed(1) + '" text-anchor="middle" fill="rgba(255,255,255,.55)" font-size="7">' +
          escapeHtml((n.shortLabel || n.label || "").slice(0, 11)) +
          "</text>"
        );
      }
    });
    parts.push(
      '<text x="14" y="292" fill="rgba(255,255,255,.4)" font-size="8">older</text>' +
      '<text x="386" y="292" text-anchor="end" fill="rgba(255,255,255,.4)" font-size="8">newer ↻</text>'
    );
    svg.innerHTML = parts.join("");
    if (labelEl) {
      var title = spec.title ? String(spec.title).slice(0, 28) : "Time · spiral";
      var range = spec.subtitle || formatSpiralRange(nodes);
      labelEl.textContent = range ? title + " · " + range : title;
    }
    log("INFO", "temporal_spiral_drawn", { nodes: nodes.length, focus: focusIdx });
    this._wireMiniGraphNav();
  };

  GraphNav.prototype._drawMiniGraph = function (centerLabel, neighbors) {
    var nodes = (neighbors || []).map(function (nb, i) {
      return {
        label: "",
        shortLabel: String(i + 1),
        color: nb.color || "#888",
        kind: "node",
        id: String(i),
        timeKey: "2026-01-" + String((i % 28) + 1).padStart(2, "0"),
        edgeType: "LINK",
      };
    });
    this._drawTemporalSpiralGraph({ title: centerLabel, nodes: nodes });
  };

  GraphNav.prototype._wireMiniGraphNav = function () {
    var self = this;
    var svg = this.container.querySelector("#graphMini");
    if (!svg) return;
    svg.querySelectorAll("[data-graph-nav-mini='1']").forEach(function (el) {
      function go() {
        var kind = el.getAttribute("data-kind");
        var id = el.getAttribute("data-id") || "";
        if (kind === "memory") self.openMemory(id);
        else if (kind === "theme") self.openTheme(id);
        else if (kind === "person") self.openPerson(id);
        else if (kind === "day" || kind === "week") self.openDay(id);
      }
      el.addEventListener("click", go);
      el.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          go();
        }
      });
    });
  };

  GraphNav.prototype._wireNeighbors = function () {
    var self = this;
    var body = this.container.querySelector("#graphBody");
    if (!body) return;
    body.querySelectorAll("[data-graph-nav]").forEach(function (el) {
      el.addEventListener("click", function () {
        var kind = el.getAttribute("data-kind");
        var id = el.getAttribute("data-id") || "";
        if (kind === "memory") self.openMemory(id);
        else if (kind === "theme") self.openTheme(id);
        else if (kind === "person") self.openPerson(id);
        else if (kind === "day" || kind === "week") self.openDay(id);
        else if (kind === "tag") log("INFO", "tag_neighbor_click", { id: id });
        else if (kind === "node") log("WARN", "unsupported_graph_node", { kind: kind, id: id });
      });
    });
    body.querySelectorAll("[data-open-memory]").forEach(function (el) {
      el.addEventListener("click", function () {
        self.openMemory(el.getAttribute("data-open-memory") || "");
      });
    });
    body.querySelectorAll("[data-tag-edge-edit]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var mid = btn.getAttribute("data-memory-id") || "";
        var tag = btn.getAttribute("data-tag-name") || "";
        if (!mid || !tag) return;
        if (!window.confirm("Remove tag #" + tag + " from this archival?")) return;
        patchMemory(mid, { tags_remove: [tag], reviewed_by: "alex" })
          .then(function () {
            log("INFO", "tag_removed_via_graph", { memory_id: mid, tag: tag });
            self.openMemory(mid, true);
          })
          .catch(function (err) {
            log("ERROR", "tag_remove_failed", { memory_id: mid, tag: tag, error: String(err) });
          });
      });
    });
    body.querySelectorAll("[data-tag-add-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mid = btn.getAttribute("data-tag-add-btn") || "";
        var input = body.querySelector('[data-tag-add-input="' + mid + '"]');
        var tag = (input && input.value || "").trim().replace(/^#/, "");
        if (!tag) return;
        patchMemory(mid, { tags_add: [tag], reviewed_by: "alex" })
          .then(function () {
            if (input) input.value = "";
            self.openMemory(mid, true);
          })
          .catch(function (err) {
            log("ERROR", "tag_add_failed", { memory_id: mid, error: String(err) });
          });
      });
    });
    body.querySelectorAll("[data-mark-reviewed]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mid = btn.getAttribute("data-mark-reviewed") || "";
        patchMemory(mid, { mark_reviewed: true, reviewed_by: "alex" })
          .then(function () { self.openMemory(mid, true); })
          .catch(function (err) { log("ERROR", "mark_reviewed_failed", { memory_id: mid, error: String(err) }); });
      });
    });
    body.querySelectorAll("[data-person-edge-remove]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var mid = btn.getAttribute("data-memory-id") || "";
        var personRef = btn.getAttribute("data-person-ref") || "";
        var personLabel = btn.getAttribute("data-person-label") || personRef;
        if (!mid || !personRef) return;
        if (!window.confirm("Remove person \"" + personLabel + "\" from this archival?")) return;
        patchMemory(mid, { persons_remove: [personRef], reviewed_by: "alex" })
          .then(function () {
            log("INFO", "person_removed_via_graph", { memory_id: mid, person_ref: personRef });
            showGraphToast("Removed person \"" + personLabel + "\"", true);
            self.openMemory(mid, true);
          })
          .catch(function (err) {
            log("ERROR", "person_remove_failed", { memory_id: mid, person_ref: personRef, error: String(err) });
            showGraphToast("Save failed: " + err.message, false);
          });
      });
    });
    body.querySelectorAll("[data-person-add-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mid = btn.getAttribute("data-person-add-btn") || "";
        var input = body.querySelector('[data-person-add-input="' + mid + '"]');
        var raw = (input && input.value || "").trim().toLowerCase().replace(/^person[:_]/, "");
        if (!raw) return;
        patchMemory(mid, { persons_add: [raw], reviewed_by: "alex" })
          .then(function () {
            if (input) input.value = "";
            log("INFO", "person_added_via_graph", { memory_id: mid, person_id: raw });
            showGraphToast("Saved person \"" + raw + "\"", true);
            self.openMemory(mid, true);
          })
          .catch(function (err) {
            log("ERROR", "person_add_failed", { memory_id: mid, error: String(err) });
            showGraphToast("Save failed: " + err.message, false);
          });
      });
    });
    body.querySelectorAll("[data-person-save]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var personRef = btn.getAttribute("data-person-save") || "";
        var labelInput = body.querySelector('[data-person-label-input="' + personRef + '"]');
        var idInput = body.querySelector('[data-person-id-input="' + personRef + '"]');
        var label = labelInput ? String(labelInput.value || "").trim() : "";
        var personId = idInput ? String(idInput.value || "").trim().toLowerCase() : "";
        var payload = {};
        if (label) payload.label = label;
        if (personId) payload.person_id = personId;
        if (!payload.label && !payload.person_id) {
          showGraphToast("Enter a label or person_id", false);
          return;
        }
        patchPerson(personRef, payload)
          .then(function () {
            log("INFO", "person_node_saved", { person_ref: personRef, payload: payload });
            showGraphToast("Person saved", true);
            self.openPerson(personRef, true);
          })
          .catch(function (err) {
            log("ERROR", "person_save_failed", { person_ref: personRef, error: String(err) });
            showGraphToast("Save failed: " + err.message, false);
          });
      });
    });
    body.querySelectorAll("[data-about-flag]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var mid = btn.getAttribute("data-memory-id") || "";
        var personId = btn.getAttribute("data-person-id") || "";
        var comment = "Wrong ABOUT edge: " + personId + " on archival " + mid.slice(0, 8);
        fetchJson("/api/cascade/reviews", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_id: mid,
            target_kind: "memory",
            issue_type: "wrong_link",
            comment: comment,
            created_by: "alex",
          }),
        })
          .then(function () {
            log("INFO", "about_edge_flagged", { memory_id: mid, person_id: personId });
            alert("Saved review flag for ABOUT " + personId);
          })
          .catch(function (err) {
            log("ERROR", "about_flag_failed", { memory_id: mid, error: String(err) });
          });
      });
    });
  };

  GraphNav.prototype._personEditorSection = function (memoryId, edges) {
    var mid = normMemoryId(memoryId);
    var persons = aboutPersonsFromEdges(edges, mid);
    var chips = persons.map(function (ref) {
      var label = formatLabel(ref);
      return '<span class="graph-person-chip">' + escapeHtml(label) +
        '<button type="button" data-person-edge-remove data-memory-id="' + escapeHtml(mid) +
        '" data-person-ref="' + escapeHtml(ref.id) +
        '" data-person-label="' + escapeHtml(label) +
        '" title="Remove person">✎</button></span>';
    }).join("");
    return '<div class="graph-section"><div class="graph-section-title">People (ABOUT)</div>' +
      '<div class="graph-person-list">' + (chips || '<span class="graph-empty">No people</span>') + '</div>' +
      '<div class="graph-person-editor-row">' +
      '<input type="text" class="graph-person-input" placeholder="Person id (e.g. alex, sam)…" data-person-add-input="' + escapeHtml(mid) + '" list="graphPersonSuggest" />' +
      '<button type="button" class="graph-person-add-btn" data-person-add-btn="' + escapeHtml(mid) + '">+ Person</button>' +
      '</div></div>';
  };

  GraphNav.prototype._personNodeEditorSection = function (personRef, personNode) {
    var props = (personNode && personNode.properties) || {};
    var label = (personNode && personNode.label) || personRef.replace(/^person_/, "");
    var pid = String(props.person_id || personRef.replace(/^person_/, "")).trim();
    return '<div class="graph-section"><div class="graph-section-title">Edit person</div>' +
      '<div class="graph-person-form">' +
      '<label class="graph-person-field"><span>Label</span>' +
      '<input type="text" class="graph-person-input" data-person-label-input="' + escapeHtml(personRef) + '" value="' + escapeHtml(label) + '" /></label>' +
      '<label class="graph-person-field"><span>person_id</span>' +
      '<input type="text" class="graph-person-input" data-person-id-input="' + escapeHtml(personRef) + '" value="' + escapeHtml(pid) + '" /></label>' +
      '<button type="button" class="graph-person-add-btn" data-person-save="' + escapeHtml(personRef) + '">Save</button>' +
      '</div></div>';
  };

  GraphNav.prototype._tagEditorSection = function (memoryId, tags, reviewed) {
    var mid = normMemoryId(memoryId);
    var chips = (tags || []).map(function (tag) {
      return '<span class="graph-tag-chip">#' + escapeHtml(tag) +
        '<button type="button" data-tag-edge-edit data-memory-id="' + escapeHtml(mid) +
        '" data-tag-name="' + escapeHtml(tag) + '" title="Remove tag">✎</button></span>';
    }).join("");
    return '<div class="graph-section"><div class="graph-section-title">Tags (persistent)</div>' +
      '<div class="graph-tag-list">' + (chips || '<span class="graph-empty">No tags</span>') + '</div>' +
      '<div class="graph-tag-editor-row">' +
      '<input type="text" class="graph-tag-input" placeholder="New tag…" data-tag-add-input="' + escapeHtml(mid) + '" />' +
      '<button type="button" class="graph-tag-add-btn" data-tag-add-btn="' + escapeHtml(mid) + '">+ Tag</button>' +
      (reviewed ? '<span class="graph-reviewed-badge">✓ reviewed</span>' :
        '<button type="button" class="graph-tag-add-btn" data-mark-reviewed="' + escapeHtml(mid) + '">Mark reviewed</button>') +
      '</div></div>';
  };

  GraphNav.prototype._neighborRow = function (g, mid, memoryTags) {
    var col = edgeColor(g.edge.type);
    var editBtn = "";
    if (g.edge.type === "TAGGED_WITH" && mid && g.ref.kind === "tag") {
      var tagName = tagNameFromRef(memoryTags, g.ref);
      editBtn = '<button type="button" class="graph-neighbor-edit" data-tag-edge-edit data-memory-id="' +
        escapeHtml(mid) + '" data-tag-name="' + escapeHtml(tagName) +
        '" title="Remove tag">✎</button>';
    } else if (g.edge.type === "ABOUT" && mid && g.ref.kind === "person") {
      var personLabel = formatLabel(g.ref);
      editBtn = '<button type="button" class="graph-neighbor-edit" data-person-edge-remove data-memory-id="' +
        escapeHtml(mid) + '" data-person-ref="' + escapeHtml(g.ref.id) +
        '" data-person-label="' + escapeHtml(personLabel) +
        '" title="Remove person from archival">✎</button>';
    }
    return '<div class="graph-neighbor-row">' +
      '<button type="button" class="graph-neighbor" data-graph-nav data-kind="' + escapeHtml(g.ref.kind) +
      '" data-id="' + escapeHtml(g.ref.id) + '" style="--edge-color:' + col + '">' +
      '<span class="edge-type">' + escapeHtml(g.edge.type) + "</span>" +
      '<span class="edge-label">' + escapeHtml(formatLabel(g.ref)) + "</span>" +
      (g.count > 1 ? '<span class="edge-count">×' + g.count + "</span>" : "") +
      "</button>" + editBtn + "</div>";
  };

  GraphNav.prototype._neighborSection = function (edges, memoryId, memoryTags) {
    if (!edges || !edges.length) {
      return '<p class="graph-empty">No graph edges</p>';
    }
    var mid = normMemoryId(memoryId || "");
    var byType = {};
    edges.forEach(function (e) {
      var ref = parseTarget(e.target);
      var etype = e.type || "OTHER";
      var key = etype + ":" + ref.kind + ":" + ref.id;
      if (!byType[etype]) byType[etype] = {};
      if (!byType[etype][key]) {
        byType[etype][key] = { edge: e, ref: ref, count: 0 };
      }
      byType[etype][key].count += 1;
    });
    var typeKeys = Object.keys(byType);
    typeKeys.sort(function (a, b) {
      var ia = EDGE_SECTION_ORDER.indexOf(a);
      var ib = EDGE_SECTION_ORDER.indexOf(b);
      if (ia === -1) ia = 99;
      if (ib === -1) ib = 99;
      if (ia !== ib) return ia - ib;
      return a.localeCompare(b);
    });
    var html = '<div class="graph-section"><div class="graph-section-title">Graph links</div>';
    typeKeys.forEach(function (etype) {
      var label = EDGE_SECTION_LABELS[etype] || etype;
      var grouped = byType[etype];
      html += '<div class="graph-edge-group"><div class="graph-edge-group-title">' + escapeHtml(label) + '</div><div class="graph-neighbors">';
      Object.keys(grouped).forEach(function (key) {
        html += this._neighborRow(grouped[key], mid, memoryTags);
      }, this);
      html += "</div></div>";
    }, this);
    html += "</div>";
    return html;
  };

  GraphNav.prototype.openMemory = function (memoryId, restoring) {
    var self = this;
    var mid = normMemoryId(memoryId);
    if (!mid) return;
    if (!restoring) {
      this._push({ kind: "memory", id: mid, title: "Archival", shortTitle: mid.slice(0, 8) + "…" });
    }
    this._renderShell("Archival Memory", this._breadcrumbHtml());
    var body = this.container.querySelector("#graphBody");
    var t0 = performance.now();
    log("INFO", "open_memory_start", { memory_id: mid });
    fetchJson("/api/cascade/memory/" + encodeURIComponent(mid))
      .then(function (m) {
        var l1 = (m.metadata && m.metadata.recall_inject_l1) || "";
        var edges = m.edges || [];
        var spiralNodes = buildEdgeTimelineNodes(edges, mid);
        var focusTime = parseTimeKey(
          m.episode_date || (m.metadata && m.metadata.episode_date) || m.created_at
        );
        spiralNodes.push({
          id: mid,
          kind: "memory",
          label: l1.slice(0, 18) || mid.slice(0, 8),
          shortLabel: "here",
          color: "#41dce1",
          edgeType: "FOCUS",
          timeKey: focusTime,
          isFocus: true,
        });
        self._drawTemporalSpiralGraph({
          title: l1.slice(0, 22) || mid.slice(0, 8),
          nodes: spiralNodes,
        });
        var metaNote = (m.metadata && m.metadata.note != null) ? String(m.metadata.note) : "";
        var card = {
          note: m.note != null ? String(m.note) : metaNote,
          entry_title: m.entry_title || "",
          agent_id: m.agent_id || "",
          memory_id: mid,
          content: m.content || "",
        };
        var detail = {
          content: m.content || "",
          memory_id: mid,
          agent_id: m.agent_id || "",
          media: m.media || [],
        };
        var html =
          (l1 ? '<p class="graph-l1">' + escapeHtml(l1) + "</p>" : "") +
          self._tagEditorSection(mid, m.tags || [], !!m.reviewed) +
          self._personEditorSection(mid, edges) +
          self._neighborSection(edges, mid, m.tags || []) +
          renderArchiveProse(card, detail);
        if (m.metadata && m.metadata.theme_id) {
          html =
            '<button type="button" class="graph-link-btn" data-graph-nav data-kind="theme" data-id="' +
            escapeHtml(String(m.metadata.theme_id).replace(/^theme_/, "")) +
            '">→ Theme ' + escapeHtml(m.metadata.theme_id) + "</button>" + html;
        }
        body.innerHTML = html;
        self._wireNeighbors();
        log("INFO", "open_memory_done", { memory_id: mid, edges: edges.length, ms: Math.round(performance.now() - t0) });
      })
      .catch(function (err) {
        body.innerHTML = '<p class="graph-error">Error: ' + escapeHtml(err.message) + "</p>";
        log("ERROR", "open_memory_failed", { memory_id: mid, error: String(err) });
      });
  };

  GraphNav.prototype.openTheme = function (themeId, restoring) {
    var self = this;
    var tid = String(themeId || "").replace(/^theme_/, "");
    if (!tid) return;
    if (!restoring) {
      this._push({
        kind: "theme",
        id: tid,
        title: "Theme",
        shortTitle: root.TimeCircleData ? root.TimeCircleData.formatThemeLabel("theme_" + tid).slice(0, 12) : tid.slice(0, 12),
      });
    }
    this._renderShell("Theme · " + tid, this._breadcrumbHtml());
    var body = this.container.querySelector("#graphBody");
    fetchJson("/api/cascade/theme/" + encodeURIComponent(tid))
      .then(function (b) {
        var archs = b.archivals || [];
        var themeLabel = root.TimeCircleData
          ? root.TimeCircleData.formatThemeLabel("theme_" + tid).slice(0, 16)
          : tid.slice(0, 16);
        var spiralNodes = buildArchivalTimelineNodes(archs, "#fbbf24");
        if (spiralNodes.length) {
          spiralNodes.unshift({
            id: tid,
            kind: "theme",
            label: themeLabel,
            shortLabel: "theme",
            color: "#a855f7",
            edgeType: "THEME",
            timeKey: spiralNodes[0].timeKey,
          });
        } else {
          spiralNodes.push({
            id: tid,
            kind: "theme",
            label: themeLabel,
            shortLabel: "theme",
            color: "#a855f7",
            edgeType: "THEME",
            timeKey: parseTimeKey(new Date().toISOString()),
            isFocus: true,
          });
        }
        self._drawTemporalSpiralGraph({
          title: themeLabel,
          subtitle: (b.day_ids && b.day_ids.length) ? b.day_ids.length + " days" : "",
          nodes: spiralNodes.slice(0, 24),
        });
        var html = "";
        if (b.day_ids && b.day_ids.length) {
          html += '<div class="graph-section"><div class="graph-section-title">Days</div><div class="graph-neighbors">';
          b.day_ids.forEach(function (d) {
            html +=
              '<button type="button" class="graph-neighbor" data-graph-nav data-kind="day" data-id="' +
              escapeHtml(d) + '" style="--edge-color:#9dc76d"><span class="edge-type">DAY</span><span class="edge-label">' +
              escapeHtml(root.TimeCircleData ? root.TimeCircleData.formatDayLabel(d, "short") : d) + "</span></button>";
          });
          html += "</div></div>";
        }
        html += '<div class="graph-section"><div class="graph-section-title">Archivals (' + archs.length + ")</div>";
        archs.forEach(function (a) {
          html +=
            '<button type="button" class="graph-archival-card" data-open-memory="' + escapeHtml(a.memory_id || "") + '">' +
            archivalCardInner(a, 200) +
            "</button>";
        });
        if (!archs.length) html += '<p class="graph-empty">No archivals</p>';
        html += "</div>";
        body.innerHTML = html;
        self._wireNeighbors();
        log("INFO", "open_theme_done", { theme_id: tid, archivals: archs.length });
      })
      .catch(function (err) {
        body.innerHTML = '<p class="graph-error">Error: ' + escapeHtml(err.message) + "</p>";
      });
  };

  GraphNav.prototype.openPerson = function (personRef, restoring) {
    var self = this;
    var ref = String(personRef || "");
    if (!ref) return;
    if (!restoring) {
      this._push({ kind: "person", id: ref, title: "Person", shortTitle: ref.replace(/^person_/, "") });
    }
    this._renderShell("Person · " + ref.replace(/^person_/, ""), this._breadcrumbHtml());
    var body = this.container.querySelector("#graphBody");
    fetchJson("/api/cascade/person/" + encodeURIComponent(ref))
      .then(function (b) {
        var archs = (b.archivals || []).slice(0, 24);
        var personLabel = (b.person_node && b.person_node.label) ? b.person_node.label.slice(0, 16) : ref.replace(/^person_/, "");
        var spiralNodes = buildArchivalTimelineNodes(archs, "#41dce1");
        if (spiralNodes.length) {
          spiralNodes.unshift({
            id: ref,
            kind: "person",
            label: personLabel,
            shortLabel: "person",
            color: "#41dce1",
            edgeType: "ABOUT",
            timeKey: spiralNodes[0].timeKey,
          });
        }
        self._drawTemporalSpiralGraph({
          title: personLabel,
          nodes: spiralNodes,
        });
        var html = self._personNodeEditorSection(ref, b.person_node);
        if (b.themes && b.themes.length) {
          html += '<div class="graph-section"><div class="graph-section-title">Themes</div><div class="graph-neighbors">';
          b.themes.slice(0, 16).forEach(function (t) {
            var tid = t.theme_id || (t.node && t.node.id) || "";
            html +=
              '<button type="button" class="graph-neighbor" data-graph-nav data-kind="theme" data-id="' +
              escapeHtml(String(tid).replace(/^theme_/, "")) + '" style="--edge-color:#a855f7"><span class="edge-type">THEME</span><span class="edge-label">' +
              escapeHtml(root.TimeCircleData ? root.TimeCircleData.formatThemeLabel(tid) : tid) + "</span></button>";
          });
          html += "</div></div>";
        }
        html += '<div class="graph-section"><div class="graph-section-title">Archivals (ABOUT)</div>';
        archs.forEach(function (a) {
          html +=
            '<button type="button" class="graph-archival-card" data-open-memory="' + escapeHtml(a.memory_id || "") + '">' +
            archivalCardInner(a, 180) +
            "</button>";
        });
        if (!archs.length) html += '<p class="graph-empty">No archivals</p>';
        html += "</div>";
        body.innerHTML = html;
        self._wireNeighbors();
      })
      .catch(function (err) {
        body.innerHTML = '<p class="graph-error">Error: ' + escapeHtml(err.message) + "</p>";
      });
  };

  GraphNav.prototype.openDay = function (dayId, restoring) {
    var self = this;
    var id = String(dayId || "").replace(/^day_/, "");
    if (!id) return;
    if (!restoring) {
      this._push({
        kind: "day",
        id: id,
        title: "Day",
        shortTitle: root.TimeCircleData ? root.TimeCircleData.formatDayLabel(id, "short") : id,
      });
    }
    this._renderShell("Day · " + id, this._breadcrumbHtml());
    var body = this.container.querySelector("#graphBody");
    fetchJson("/api/cascade/day/" + encodeURIComponent(id))
      .then(function (b) {
        var themes = b.themes || [];
        var spiralNodes = themes.map(function (t, i) {
          var tid = String(t.theme_id || t.id || "").replace(/^theme_/, "");
          var archs = t.archivals || [];
          var tk = id + "T" + String(i).padStart(2, "0");
          if (archs.length) tk = archivalTimeKey(archs[archs.length - 1]) || tk;
          return {
            id: tid,
            kind: "theme",
            label: root.TimeCircleData ? root.TimeCircleData.formatThemeLabel(tid).slice(0, 14) : tid.slice(0, 14),
            shortLabel: String(i + 1),
            color: "#a855f7",
            edgeType: "THEME",
            timeKey: tk,
          };
        });
        if (!spiralNodes.length) {
          spiralNodes.push({
            id: id,
            kind: "day",
            label: id,
            shortLabel: "day",
            color: "#9dc76d",
            edgeType: "DAY",
            timeKey: parseTimeKey(id),
            isFocus: true,
          });
        } else {
          spiralNodes.unshift({
            id: id,
            kind: "day",
            label: id,
            shortLabel: "day",
            color: "#9dc76d",
            edgeType: "DAY",
            timeKey: parseTimeKey(id),
          });
        }
        self._drawTemporalSpiralGraph({
          title: id,
          nodes: spiralNodes,
        });
        var html = '<div class="graph-section"><div class="graph-section-title">Themes (' + themes.length + ")</div>";
        themes.forEach(function (t) {
          var tid = t.theme_id || t.id || "";
          var ac = (t.archivals || []).length;
          html +=
            '<button type="button" class="graph-neighbor" data-graph-nav data-kind="theme" data-id="' +
            escapeHtml(String(tid).replace(/^theme_/, "")) + '" style="--edge-color:#a855f7">' +
            '<span class="edge-type">' + ac + " arch</span>" +
            '<span class="edge-label">' + escapeHtml(root.TimeCircleData ? root.TimeCircleData.formatThemeLabel(tid) : tid) +
            "</span></button>";
          (t.archivals || []).slice(0, 4).forEach(function (a) {
            html +=
              '<button type="button" class="graph-archival-card nested" data-open-memory="' + escapeHtml(a.memory_id || "") + '">' +
              '<span class="arch-id">↳ ' + escapeHtml((a.memory_id || "").slice(0, 12)) + "…</span>" +
              mediaBadgeHtml(a, true) +
              "<span class=\"arch-preview\">" + escapeHtml((a.l1 || "").substring(0, 120)) + "</span></button>";
          });
        });
        if (!themes.length) html += '<p class="graph-empty">No themes</p>';
        html += "</div>";
        body.innerHTML = html;
        self._wireNeighbors();
      })
      .catch(function (err) {
        body.innerHTML = '<p class="graph-error">Error: ' + escapeHtml(err.message) + "</p>";
      });
  };

  root.TimeCircleGraphNav = {
    create: function (container) {
      return new GraphNav(container);
    },
    mediaBadgeHtml: mediaBadgeHtml,
    mediaCountForArchival: mediaCountForArchival,
    archivalCardInner: archivalCardInner,
    renderArchiveProse: renderArchiveProse,
  };
})(window);
