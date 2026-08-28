/**
 * time_circle_index.js – Trading-style Index, Label-Kollision, Index-Dashboard.
 * Created: 2026-06-30
 * Last updated: 2026-06-30
 */
(function (root) {
  "use strict";

  var STEP_DEG = 3.58;
  var ORIGIN_DEG = -115;
  var CX = 500;
  var CY = 500;
  var MIN_LEN_PX = 22;
  var MAX_LEN_PX = 118;

  function log(level, message, ctx) {
    var payload = {
      timestamp: new Date().toISOString(),
      level: level,
      module: "time_circle_index",
      message: message,
    };
    if (ctx) payload.context = ctx;
    var fn = level === "ERROR" ? console.error : level === "WARN" ? console.warn : console.log;
    fn(JSON.stringify(payload));
  }

  function segAngleRad(index) {
    return (ORIGIN_DEG + index * STEP_DEG) * Math.PI / 180;
  }

  function segAngleDeg(index) {
    return ORIGIN_DEG + index * STEP_DEG;
  }

  function eventIndexValue(ev, zoomLevel) {
    if (!ev) return 0;
    if (zoomLevel === "hour") return Number(ev.eventCount || 0);
    if (zoomLevel === "month") return Number(ev.dayCount || ev.themeCount || 0);
    if (ev.source === "mma") return Number(ev.eventCount || 0);
    return Number(ev.themeCount || ev.eventCount || 0);
  }

  function formatIndexLabel(value) {
    var n = Number(value);
    if (!Number.isFinite(n)) return "—";
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
    if (Number.isInteger(n)) return String(n);
    return n.toFixed(1);
  }

  function timeLabelForEvent(ev, zoomLevel) {
    if (!ev) return "—";
    if (zoomLevel === "hour") return ev.hourLabel || ev.title || "—";
    if (zoomLevel === "month") return ev.labelShort || ev.title || "—";
    if (ev.dayId) {
      var D = root.TimeCircleData;
      return D ? D.formatDayLabel(ev.dayId, "short") : ev.dayId;
    }
    return ev.title || ev.labelShort || "—";
  }

  function metaLineForEvent(ev, zoomLevel) {
    if (!ev) return "";
    if (zoomLevel === "month") return (ev.dayCount || 0) + " tage · " + (ev.themeCount || 0) + " themes";
    if (zoomLevel === "hour") return (ev.eventCount || 0) + " enrich";
    if (zoomLevel === "day") {
      var tc = ev.themeCount != null ? ev.themeCount : 0;
      return tc + " theme(s)";
    }
    if (ev.copy) return String(ev.copy).split(" · ")[0];
    return "";
  }

  function formatLabelText(ev, mode, zoomLevel) {
    if (!ev || mode === "hidden") return "";
    var main = ev.labelShort || ev.title || ev.dayId || "—";
    if (mode === "full") {
      var meta = metaLineForEvent(ev, zoomLevel);
      return meta ? main + "\n" + meta : main;
    }
    if (mode === "meta") return main + "\n" + metaLineForEvent(ev, zoomLevel);
    return main;
  }

  function estimateLabelArcDeg(text, radiusPx) {
    var lines = String(text || "").split("\n");
    var maxLen = 0;
    lines.forEach(function (ln) { maxLen = Math.max(maxLen, ln.length); });
    var charW = lines.length > 1 ? 6.2 : 6.8;
    var widthPx = maxLen * charW + (lines.length > 1 ? 8 : 0);
    var r = Math.max(80, radiusPx);
    return (widthPx / r) * (180 / Math.PI);
  }

  function computeRingLabelPlans(events, activeIndex, zoomLevel) {
    var n = (events || []).length;
    var plans = [];
    var dense = n > 16;
    var m = wheelMetrics();
    var radiusPx = m.dockPx + MAX_LEN_PX + 24;
    var i;

    for (i = 0; i < n; i++) {
      var dist = Math.abs(i - activeIndex);
      var mode = "hidden";
      if (i === activeIndex) mode = "full";
      else if (dist === 1) mode = dense ? "title" : "meta";
      else if (dist === 2) mode = "title";
      else if (dist <= 3 && !dense) mode = "title";
      else if (dist <= 4 && zoomLevel !== "day") mode = "title";
      plans.push({
        mode: mode,
        staggerPx: 0,
        hidden: mode === "hidden",
        compact: false,
      });
    }

    var priority = plans.map(function (p, idx) {
      return {
        i: idx,
        p: p,
        score: idx === activeIndex ? 1000 : 100 - Math.abs(idx - activeIndex) * 12,
      };
    }).sort(function (a, b) { return b.score - a.score; });

    var placed = [];
    priority.forEach(function (entry) {
      if (entry.p.hidden) return;
      var ev = events[entry.i];
      var text = formatLabelText(ev, entry.p.mode, zoomLevel);
      var arc = estimateLabelArcDeg(text, radiusPx);
      var ang = segAngleDeg(entry.i);
      var overlap = placed.some(function (pl) {
        var dAng = Math.abs(ang - pl.ang);
        if (dAng > 180) dAng = 360 - dAng;
        return dAng < (arc + pl.arc) * 0.52;
      });
      if (overlap && entry.i !== activeIndex) {
        entry.p.mode = "title";
        entry.p.compact = true;
        text = formatLabelText(ev, "title", zoomLevel);
        arc = estimateLabelArcDeg(text, radiusPx);
        overlap = placed.some(function (pl) {
          var dAng = Math.abs(ang - pl.ang);
          if (dAng > 180) dAng = 360 - dAng;
          return dAng < (arc + pl.arc) * 0.48;
        });
        if (overlap) {
          entry.p.hidden = true;
          entry.p.mode = "hidden";
          return;
        }
      }
      entry.p.staggerPx = entry.i > activeIndex ? 6 : entry.i < activeIndex ? -6 : 0;
      placed.push({ ang: ang, arc: arc });
    });

    log("DEBUG", "ring_label_plans", {
      segments: n,
      active: activeIndex,
      visible: plans.filter(function (p) { return !p.hidden; }).length,
      zoom: zoomLevel,
    });
    return plans;
  }

  function applyRingLabelPlan(el, plan, text) {
    if (!el || !plan) return;
    el.textContent = text || "";
    el.classList.toggle("label-hidden", !!plan.hidden);
    el.classList.toggle("label-compact", !!plan.compact);
    el.classList.toggle("label-near", plan.mode === "meta" || plan.mode === "full");
    el.classList.toggle("label-full", plan.mode === "full");
    el.style.setProperty("--label-stagger", (plan.staggerPx || 0) + "px");
  }

  function computeBarPack(events, zoomLevel) {
    var values = (events || []).map(function (ev) {
      return eventIndexValue(ev, zoomLevel);
    });
    var max = Math.max.apply(null, values.concat([1]));
    var min = Math.min.apply(null, values.concat([0]));
    var span = Math.max(1, max - min);
    var lengths = values.map(function (v) {
      var t = (v - min) / span;
      return Math.round(MIN_LEN_PX + t * (MAX_LEN_PX - MIN_LEN_PX));
    });
    return { values: values, lengths: lengths, min: min, max: max };
  }

  function wheelMetrics() {
    var docEl = root.document.documentElement;
    var wheel = root.document.querySelector(".wheel");
    if (!wheel || !wheel.offsetWidth) {
      return { wheelHalf: 400, dockPx: 220, outerPx: 320, vmin: 8 };
    }
    var vmin = Math.min(root.innerWidth, root.innerHeight) / 100;
    var wheelHalf = wheel.offsetWidth / 2;
    var dockVmin = parseFloat(getComputedStyle(docEl).getPropertyValue("--bar-dock")) || 59.3;
    var outerVmin = parseFloat(getComputedStyle(docEl).getPropertyValue("--ring-outer")) || 42.6;
    var dotsVmin = 73.5;
    return {
      wheelHalf: wheelHalf,
      dockPx: dockVmin * vmin,
      outerPx: outerVmin * vmin,
      perimeterOuterPx: dotsVmin * vmin,
      vmin: vmin,
    };
  }

  function pxToSvg(px, wheelHalf) {
    return (px / wheelHalf) * 500;
  }

  function barTipSvg(index, lenPx, focus) {
    var m = wheelMetrics();
    var f = focus == null ? 1 : Number(focus);
    var r = pxToSvg(m.dockPx + lenPx * f, m.wheelHalf);
    var a = segAngleRad(index);
    return {
      x: CX + Math.cos(a) * r,
      y: CY + Math.sin(a) * r,
      angleDeg: segAngleDeg(index),
      radiusSvg: r,
    };
  }

  function svgEl(tag) {
    return root.document.createElementNS("http://www.w3.org/2000/svg", tag);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function positionFloatingReadout(el, clientX, clientY) {
    if (!el) return;
    var pad = 12;
    var offsetX = 16;
    var offsetY = -10;
    var vw = root.innerWidth;
    var vh = root.innerHeight;
    el.style.position = "fixed";
    el.style.transform = "none";
    el.hidden = false;
    var w = el.offsetWidth || 168;
    var h = el.offsetHeight || 72;
    var lx = clientX + offsetX;
    var ly = clientY + offsetY - h;
    if (lx + w > vw - pad) lx = clientX - w - offsetX;
    if (lx < pad) lx = pad;
    if (ly < pad) ly = clientY + 22;
    if (ly + h > vh - pad) ly = vh - h - pad;
    el.style.left = lx + "px";
    el.style.top = ly + "px";
  }

  function resolveBarEndLabelPlans(tips, activeIndex, events, zoomLevel) {
    var plans = [];
    var placed = [];
    var priority = tips.map(function (tip, i) {
      var dist = Math.abs(i - activeIndex);
      var show = i === activeIndex || dist <= 1;
      return { i: i, tip: tip, show: show, score: i === activeIndex ? 1000 : 100 - dist * 20 };
    }).filter(function (x) { return x.show; })
      .sort(function (a, b) { return b.score - a.score; });

    tips.forEach(function (_, i) {
      plans[i] = { visible: false, stagger: 0, showMeta: false, fontScale: 1 };
    });

    priority.forEach(function (entry) {
      var i = entry.i;
      var ev = events[i];
      var meta = metaLineForEvent(ev, zoomLevel);
      var arc = estimateLabelArcDeg(timeLabelForEvent(ev, zoomLevel) + (i === activeIndex ? meta : ""), 120);
      var ang = entry.tip.angleDeg;
      var overlap = placed.some(function (pl) {
        var dAng = Math.abs(ang - pl.ang);
        if (dAng > 180) dAng = 360 - dAng;
        return dAng < (arc + pl.arc) * 0.5;
      });
      if (overlap && i !== activeIndex) return;
      plans[i] = {
        visible: true,
        stagger: i > activeIndex ? 8 : -8,
        showMeta: i === activeIndex,
        fontScale: i === activeIndex ? 1 : 0.85,
      };
      placed.push({ ang: ang, arc: arc });
    });
    return plans;
  }

  function renderIndexOverlay(svgRoot, events, pack, activeIndex, zoomLevel) {
    if (!svgRoot) return;
    svgRoot.innerHTML = "";
    if (!events || !events.length || !pack) return;

    var tips = events.map(function (_, i) {
      var focus = i === activeIndex ? 1.08 : 1;
      return barTipSvg(i, pack.lengths[i] || MIN_LEN_PX, focus);
    });

    var endPlans = resolveBarEndLabelPlans(tips, activeIndex, events, zoomLevel);

    if (tips.length > 1) {
      var line = svgEl("path");
      line.setAttribute("class", "index-perimeter-line");
      line.setAttribute(
        "d",
        tips.map(function (p, i) {
          return (i === 0 ? "M" : "L") + p.x.toFixed(2) + " " + p.y.toFixed(2);
        }).join(" ") + " Z"
      );
      line.setAttribute("fill", "none");
      line.setAttribute("stroke", "#ef597a");
      line.setAttribute("stroke-width", "1.4");
      line.setAttribute("stroke-linejoin", "round");
      line.setAttribute("opacity", "0.82");
      line.setAttribute("pointer-events", "none");
      svgRoot.appendChild(line);
    }

    events.forEach(function (ev, i) {
      var tip = tips[i];
      var val = pack.values[i];
      var plan = endPlans[i] || { visible: false };
      if (!plan.visible && i !== activeIndex && val <= 0) return;

      var g = svgEl("g");
      g.setAttribute("class", "index-bar-label" + (plan.visible ? "" : " index-bar-label-min"));
      g.dataset.index = String(i);

      var hit = svgEl("circle");
      hit.setAttribute("class", "index-bar-hit");
      hit.setAttribute("cx", tip.x.toFixed(2));
      hit.setAttribute("cy", tip.y.toFixed(2));
      hit.setAttribute("r", "18");
      hit.setAttribute("fill", "transparent");
      hit.setAttribute("stroke", "transparent");
      g.appendChild(hit);

      var ox = Math.cos(segAngleRad(i)) * (6 + (plan.stagger || 0) * 0.15);
      var oy = Math.sin(segAngleRad(i)) * (6 + (plan.stagger || 0) * 0.15);

      var tick = svgEl("line");
      tick.setAttribute("x1", tip.x.toFixed(2));
      tick.setAttribute("y1", tip.y.toFixed(2));
      tick.setAttribute("x2", (tip.x + ox).toFixed(2));
      tick.setAttribute("y2", (tip.y + oy).toFixed(2));
      tick.setAttribute("stroke", i === activeIndex ? "#fff" : "rgba(255,255,255,.45)");
      tick.setAttribute("stroke-width", i === activeIndex ? "1.2" : "0.8");
      tick.setAttribute("pointer-events", "none");
      g.appendChild(tick);

      if (plan.visible || i === activeIndex) {
        var text = svgEl("text");
        var tx = tip.x + ox * 2.4;
        var ty = tip.y + oy * 2.4;
        text.setAttribute("x", tx.toFixed(2));
        text.setAttribute("y", ty.toFixed(2));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("dominant-baseline", "middle");
        text.setAttribute(
          "class",
          "index-value-text" + (i === activeIndex ? " active" : "") +
          (plan.showMeta ? " has-meta" : "")
        );
        text.setAttribute("pointer-events", "none");
        if (plan.fontScale && plan.fontScale < 1) {
          text.setAttribute("font-size", (7.5 * plan.fontScale).toFixed(1) + "px");
        }

        var tspanVal = svgEl("tspan");
        tspanVal.setAttribute("x", tx.toFixed(2));
        tspanVal.setAttribute("dy", "0");
        tspanVal.textContent = formatIndexLabel(val);
        text.appendChild(tspanVal);

        if (plan.showMeta || i === activeIndex) {
          var tspanTime = svgEl("tspan");
          tspanTime.setAttribute("x", tx.toFixed(2));
          tspanTime.setAttribute("dy", "1.15em");
          tspanTime.setAttribute("class", "index-time-sub");
          tspanTime.textContent = timeLabelForEvent(ev, zoomLevel);
          text.appendChild(tspanTime);
        }
        g.appendChild(text);
      }

      svgRoot.appendChild(g);
    });

    log("DEBUG", "index_overlay_rendered", {
      segments: events.length,
      active: activeIndex,
      zoom: zoomLevel,
      bar_labels: endPlans.filter(function (p) { return p.visible; }).length,
    });
  }

  function trendLabel(values, idx) {
    if (!values || idx < 1) return "—";
    var cur = Number(values[idx] || 0);
    var prev = Number(values[idx - 1] || 0);
    if (cur > prev) return "▲ " + (cur - prev);
    if (cur < prev) return "▼ " + (prev - cur);
    return "→ flat";
  }

  function openDashboard(container, opts) {
    opts = opts || {};
    var idx = opts.index;
    var events = opts.events || [];
    var pack = opts.pack;
    var zoomLevel = opts.zoomLevel || "month";
    var ev = events[idx];
    if (!container || !ev) return;

    var val = pack && pack.values ? pack.values[idx] : eventIndexValue(ev, zoomLevel);
    var timeLbl = timeLabelForEvent(ev, zoomLevel);
    var meta = metaLineForEvent(ev, zoomLevel);
    var trend = pack ? trendLabel(pack.values, idx) : "—";
    var coord = barTipSvg(idx, (pack && pack.lengths[idx]) || MIN_LEN_PX, 1);

    container.innerHTML =
      '<header class="idx-dash-head">' +
      '<span class="idx-dash-badge">INDEX DASHBOARD</span>' +
      '<button type="button" class="idx-dash-close" aria-label="Schließen">×</button>' +
      "</header>" +
      '<div class="idx-dash-body">' +
      '<div class="idx-dash-row idx-dash-time"><span>ZEIT</span><strong>' + escapeHtml(timeLbl) + "</strong></div>" +
      '<div class="idx-dash-row idx-dash-idx"><span>IDX</span><strong class="idx-dash-value">' + escapeHtml(formatIndexLabel(val)) + "</strong></div>" +
      '<div class="idx-dash-row"><span>META</span><strong>' + escapeHtml(meta || "—") + "</strong></div>" +
      '<div class="idx-dash-row"><span>TREND</span><strong>' + escapeHtml(trend) + "</strong></div>" +
      '<div class="idx-dash-row idx-dash-coords"><span>2D</span><strong>' +
      escapeHtml(coord.x.toFixed(1) + " · " + coord.y.toFixed(1)) + " · " + coord.angleDeg.toFixed(1) + "°</strong></div>" +
      (ev.dayId ? '<div class="idx-dash-row"><span>TAG</span><strong>' + escapeHtml(ev.dayId) + "</strong></div>" : "") +
      "</div>" +
      '<footer class="idx-dash-foot">' +
      '<button type="button" class="idx-dash-detail">↳ Themes / Archivals öffnen</button>' +
      "</footer>";

    container.hidden = false;
    container.setAttribute("aria-hidden", "false");
    container.dataset.index = String(idx);

    container.querySelector(".idx-dash-close").addEventListener("click", function () {
      closeDashboard(container);
      if (typeof opts.onClose === "function") opts.onClose();
    });
    container.querySelector(".idx-dash-detail").addEventListener("click", function () {
      log("INFO", "index_dashboard_open_detail", { index: idx });
      if (typeof opts.onOpenDetail === "function") opts.onOpenDetail(idx);
    });

    log("INFO", "index_dashboard_opened", {
      index: idx,
      source: opts.source || "unknown",
      zoom: zoomLevel,
      idx_value: val,
      time: timeLbl,
    });
  }

  function closeDashboard(container) {
    if (!container) return;
    container.hidden = true;
    container.setAttribute("aria-hidden", "true");
    container.innerHTML = "";
    log("INFO", "index_dashboard_closed");
  }

  function buildPerimeterRing(svgRoot) {
    if (!svgRoot) return null;
    var m = wheelMetrics();
    var rIn = pxToSvg(m.dockPx + MIN_LEN_PX, m.wheelHalf);
    var rOut = pxToSvg(m.perimeterOuterPx || m.dockPx + MAX_LEN_PX + 40, m.wheelHalf);
    var ring = svgEl("circle");
    ring.setAttribute("class", "index-perimeter-hit");
    ring.setAttribute("cx", String(CX));
    ring.setAttribute("cy", String(CY));
    ring.setAttribute("r", String((rIn + rOut) / 2));
    ring.setAttribute("fill", "transparent");
    ring.setAttribute("stroke", "transparent");
    ring.setAttribute("stroke-width", String(Math.max(12, rOut - rIn)));
    ring.style.cursor = "crosshair";
    svgRoot.appendChild(ring);
    return { rIn: rIn, rOut: rOut, ring: ring };
  }

  function rebuildPerimeterHit(svgRoot) {
    if (!svgRoot) return;
    var hit = svgRoot.querySelector(".index-perimeter-hit");
    if (hit) hit.remove();
    buildPerimeterRing(svgRoot);
  }

  function pointerToSegment(svgRoot, clientX, clientY) {
    var rect = svgRoot.getBoundingClientRect();
    if (!rect.width) return null;
    var sx = ((clientX - rect.left) / rect.width) * 1000;
    var sy = ((clientY - rect.top) / rect.height) * 1000;
    var dx = sx - CX;
    var dy = sy - CY;
    var dist = Math.sqrt(dx * dx + dy * dy);
    var m = wheelMetrics();
    var rIn = pxToSvg(m.dockPx, m.wheelHalf);
    var rOut = pxToSvg(m.perimeterOuterPx || m.dockPx + MAX_LEN_PX + 50, m.wheelHalf);
    if (dist < rIn * 0.92 || dist > rOut * 1.08) return null;
    var ang = Math.atan2(dy, dx) * 180 / Math.PI;
    var rel = ang - ORIGIN_DEG;
    while (rel < 0) rel += 360;
    while (rel >= 360) rel -= 360;
    var idx = Math.round(rel / STEP_DEG);
    return { index: idx, distSvg: dist, sx: sx, sy: sy };
  }

  function fireIndexSelect(opts, idx, meta) {
    if (typeof opts.onSelect !== "function") return;
    var st = (opts.getState && opts.getState()) || {};
    var events = st.events || [];
    var zoomLevel = st.zoomLevel || "month";
    var ev = events[idx];
    log("INFO", "index_diagram_select", {
      index: idx,
      source: (meta && meta.source) || "unknown",
      zoom: zoomLevel,
      time: timeLabelForEvent(ev, zoomLevel),
      day_id: ev && ev.dayId ? ev.dayId : null,
      action: "open_index_dashboard",
    });
    opts.onSelect(idx, meta || {});
  }

  function wireIndexOverlayClicks(opts) {
    var overlaySvg = opts.overlaySvg;
    if (!overlaySvg) return;
    if (overlaySvg.dataset.tcIndexBarWired === "1") return;
    overlaySvg.dataset.tcIndexBarWired = "1";
    overlaySvg.addEventListener("click", function (e) {
      var g = e.target.closest && e.target.closest(".index-bar-label");
      if (!g) return;
      e.preventDefault();
      e.stopPropagation();
      var idx = parseInt(g.dataset.index, 10);
      if (!Number.isFinite(idx)) return;
      fireIndexSelect(opts, idx, {
        clientX: e.clientX,
        clientY: e.clientY,
        source: "index_bar",
      });
      if (opts.readoutEl) opts.readoutEl.hidden = true;
      if (opts.crosshairEl) opts.crosshairEl.hidden = true;
    });
    log("INFO", "index_bar_clicks_wired");
  }

  function wirePerimeterCrosshair(opts) {
    opts = opts || {};
    var hitSvg = opts.hitSvg;
    var readoutEl = opts.readoutEl;
    var crosshairEl = opts.crosshairEl;
    var getState = opts.getState || function () { return {}; };
    if (!hitSvg || !readoutEl) return;

    if (hitSvg.dataset.tcPerimeterWired === "1") {
      rebuildPerimeterHit(hitSvg);
      wireIndexOverlayClicks(opts);
      return;
    }
    hitSvg.dataset.tcPerimeterWired = "1";
    rebuildPerimeterHit(hitSvg);
    wireIndexOverlayClicks(opts);

    function showAt(clientX, clientY, persist) {
      var hit = pointerToSegment(hitSvg, clientX, clientY);
      if (!hit) {
        if (!persist) readoutEl.hidden = true;
        if (crosshairEl) crosshairEl.hidden = true;
        return null;
      }
      var st = getState();
      var events = st.events || [];
      var pack = st.pack;
      var zoomLevel = st.zoomLevel || "month";
      var idx = Math.max(0, Math.min(events.length - 1, hit.index));
      var ev = events[idx];
      var val = pack && pack.values ? pack.values[idx] : eventIndexValue(ev, zoomLevel);
      var timeLbl = timeLabelForEvent(ev, zoomLevel);

      readoutEl.innerHTML =
        '<span class="tc-2d-axis tc-2d-time">ZEIT · ' + timeLbl + "</span>" +
        '<span class="tc-2d-axis tc-2d-index">IDX · ' + formatIndexLabel(val) + "</span>" +
        '<span class="tc-2d-meta">' + (ev && ev.copy ? String(ev.copy).slice(0, 64) : "") + "</span>";
      positionFloatingReadout(readoutEl, clientX, clientY);

      if (crosshairEl) {
        var stage = hitSvg.closest(".stage");
        var baseRect = stage ? stage.getBoundingClientRect() : hitSvg.getBoundingClientRect();
        var lx = clientX - baseRect.left;
        var ly = clientY - baseRect.top;
        crosshairEl.hidden = false;
        crosshairEl.style.left = lx + "px";
        crosshairEl.style.top = ly + "px";
        crosshairEl.setAttribute("aria-label", "Zeit " + timeLbl + ", Index " + formatIndexLabel(val));
      }

      return { index: idx, value: val, timeLabel: timeLbl };
    }

    hitSvg.addEventListener("mousemove", function (e) {
      if (e.buttons) return;
      showAt(e.clientX, e.clientY, false);
    });
    hitSvg.addEventListener("click", function (e) {
      var res = showAt(e.clientX, e.clientY, false);
      if (!res) return;
      e.preventDefault();
      e.stopPropagation();
      fireIndexSelect(opts, res.index, {
        clientX: e.clientX,
        clientY: e.clientY,
        source: "perimeter_crosshair",
      });
      readoutEl.hidden = true;
      if (crosshairEl) crosshairEl.hidden = true;
    });
    hitSvg.addEventListener("mouseleave", function () {
      readoutEl.hidden = true;
      if (crosshairEl) crosshairEl.hidden = true;
    });

    log("INFO", "perimeter_crosshair_wired");
  }

  function wireIndexDiagram(opts) {
    wirePerimeterCrosshair(opts);
  }

  root.TimeCircleIndex = {
    STEP_DEG: STEP_DEG,
    ORIGIN_DEG: ORIGIN_DEG,
    MIN_LEN_PX: MIN_LEN_PX,
    MAX_LEN_PX: MAX_LEN_PX,
    log: log,
    eventIndexValue: eventIndexValue,
    formatIndexLabel: formatIndexLabel,
    timeLabelForEvent: timeLabelForEvent,
    metaLineForEvent: metaLineForEvent,
    formatLabelText: formatLabelText,
    computeRingLabelPlans: computeRingLabelPlans,
    applyRingLabelPlan: applyRingLabelPlan,
    computeBarPack: computeBarPack,
    barTipSvg: barTipSvg,
    renderIndexOverlay: renderIndexOverlay,
    rebuildPerimeterHit: rebuildPerimeterHit,
    wirePerimeterCrosshair: wirePerimeterCrosshair,
    wireIndexDiagram: wireIndexDiagram,
    openDashboard: openDashboard,
    closeDashboard: closeDashboard,
    positionFloatingReadout: positionFloatingReadout,
    pointerToSegment: pointerToSegment,
  };
})(window);
