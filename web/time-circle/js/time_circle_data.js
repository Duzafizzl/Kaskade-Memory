/**
 * time_circle_data.js – Lädt Kaskade-Tage oder MMA-Buckets für Kaska Time Circle.
 * Created: 2026-06-28
 * Last updated: 2026-06-30 (day/hour/memory deep-link params)
 */
(function (root) {
  "use strict";

  var params = new URLSearchParams(root.location.search);
  var CONFIG = {
    apiBase: (params.get("api") || "").replace(/\/$/, "") ||
      (root.location.port === "8777" ? "http://localhost:8080" : ""),
    source: (params.get("source") || "cascade").toLowerCase(),
    mmaWindow: params.get("window") || "last_30d",
    dayLimit: Number(params.get("limit") || 200),
    themeId: (params.get("theme") || params.get("theme_id") || "").trim().replace(/^theme_/, ""),
    personId: (params.get("person") || params.get("person_id") || "").trim().toLowerCase().replace(/^person_/, ""),
    dayId: (params.get("day") || params.get("day_id") || "").trim().replace(/^day_/, ""),
    hour: (params.get("hour") || "").trim(),
    memoryId: (params.get("memory") || params.get("memory_id") || "").trim().replace(/^mem-/, ""),
    agentId: (params.get("agent_id") || params.get("agent") || "").trim(),
    tz: params.get("tz") || "Europe/Berlin",
  };

  var resolvedAgentId = null;
  var agentResolvePromise = null;

  function log(level, message, ctx) {
    var payload = {
      timestamp: new Date().toISOString(),
      level: level,
      module: "time_circle_data",
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
    if (err && err.name === "AbortError") return "Timeout — Server antwortet samht rechtzeitig";
    if (/did not match the expected pattern/i.test(raw) || err instanceof SyntaxError) {
      return "API lieferte kein gültiges JSON" + (status ? " (HTTP " + status + ")" : "") +
        (hint ? ": " + hint : "");
    }
    if (status && raw.indexOf("HTTP") !== 0) return "HTTP " + status + (hint ? ": " + hint : "");
    return raw || "Unbekannter API-Fehler";
  }

  function parseFetchBody(r) {
    return r.text().then(function (text) {
      var body = String(text || "");
      if (!body.trim()) {
        throw new Error(friendlyFetchError(null, r.status, "leere Antwort"));
      }
      var ct = (r.headers.get("content-type") || "").toLowerCase();
      var looksJson = ct.indexOf("json") >= 0 || /^[\s[{]/.test(body);
      if (!looksJson) {
        throw new Error(friendlyFetchError(null, r.status, stripHtmlHint(body)));
      }
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

  function fetchJson(path, timeoutMs) {
    var url = CONFIG.apiBase + path;
    var ms = timeoutMs == null ? 15000 : timeoutMs;
    var t0 = performance.now();
    log("DEBUG", "fetch_start", { url: url, timeout_ms: ms });
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, ms) : null;
    return fetch(url, ctrl ? { signal: ctrl.signal } : undefined).then(function (r) {
      if (timer) clearTimeout(timer);
      return parseFetchBody(r).then(function (j) {
        if (!r.ok) {
          var apiMsg = (j && (j.message || j.error)) || "";
          throw new Error(apiMsg ? "HTTP " + r.status + ": " + apiMsg : "HTTP " + r.status);
        }
        log("INFO", "fetch_ok", { url: url, ms: Math.round(performance.now() - t0), status: r.status });
        return j;
      });
    }).catch(function (err) {
      if (timer) clearTimeout(timer);
      var msg = err && err.name === "AbortError"
        ? friendlyFetchError(err)
        : friendlyFetchError(err, null, null);
      log("ERROR", "fetch_failed", { url: url, error: msg, raw: String(err) });
      throw new Error(msg);
    });
  }

  function isIsoDay(id) {
    return /^\d{4}-\d{2}-\d{2}$/.test(String(id || ""));
  }

  function formatThemeLabel(themeId) {
    var t = String(themeId || "").replace(/^theme_/, "").replace(/_/g, " ");
    return t.length > 42 ? t.slice(0, 40) + "…" : t.toUpperCase();
  }

  function parseDayDate(dayId) {
    if (!isIsoDay(dayId)) return null;
    var p = String(dayId).split("-");
    return { y: Number(p[0]), m: Number(p[1]) - 1, d: Number(p[2]) };
  }

  function monthLabel(m) {
    return ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"][m] || "?";
  }

  function formatDayLabel(dayId, style) {
    var dt = parseDayDate(dayId);
    if (!dt) return String(dayId || "—");
    var dd = String(dt.d).padStart(2, "0");
    var ml = monthLabel(dt.m);
    if (style === "iso") return dayId;
    if (style === "short") return dd + " " + ml;
    return dd + ". " + ml + " " + dt.y;
  }

  function berlinOffsetForDay(dayId) {
    if (!isIsoDay(dayId)) return "+00:00";
    try {
      var probe = new Date(dayId + "T12:00:00Z");
      var parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: CONFIG.tz,
        timeZoneName: "longOffset",
      }).formatToParts(probe);
      var tz = parts.find(function (p) { return p.type === "timeZoneName"; });
      var raw = (tz && tz.value) || "GMT+1";
      var m = raw.match(/GMT([+-]\d{1,2})(?::?(\d{2}))?/i);
      if (!m) return "+01:00";
      var sign = m[1][0];
      var hh = String(Math.abs(parseInt(m[1], 10))).padStart(2, "0");
      var mm = m[2] || "00";
      return sign + hh + ":" + mm;
    } catch (e) {
      log("WARN", "berlin_offset_fallback", { day_id: dayId, error: String(e) });
      return "+02:00";
    }
  }

  function berlinPartsFromTs(ts) {
    if (!ts) return null;
    var d = new Date(ts);
    if (Number.isNaN(d.getTime())) return null;
    try {
      var fmt = new Intl.DateTimeFormat("en-GB", {
        timeZone: CONFIG.tz,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        hour12: false,
      });
      var parts = fmt.formatToParts(d);
      var get = function (type) {
        var p = parts.find(function (x) { return x.type === type; });
        return p ? Number(p.value) : 0;
      };
      var y = get("year");
      var mo = get("month");
      var da = get("day");
      return {
        year: y,
        month: mo,
        day: da,
        hour: get("hour"),
        dayId: y + "-" + String(mo).padStart(2, "0") + "-" + String(da).padStart(2, "0"),
      };
    } catch (e2) {
      return null;
    }
  }

  function resolveMmaAgentId(force) {
    if (CONFIG.agentId) return Promise.resolve(CONFIG.agentId);
    if (!force && resolvedAgentId) return Promise.resolve(resolvedAgentId);
    if (!force && agentResolvePromise) return agentResolvePromise;
    log("INFO", "resolve_mma_agent_start");
    agentResolvePromise = fetchJson("/api/mma/report/overview?time_window=last_7d&fast=1", 12000)
      .then(function (r) {
        var aid = (r.report && r.report.agent_id) ||
          (r.request_contract && r.request_contract.agent_id) || "";
        if (aid) {
          resolvedAgentId = aid;
          log("INFO", "resolve_mma_agent_ok", { agent_id_prefix: aid.slice(0, 20) });
        } else {
          log("WARN", "resolve_mma_agent_empty");
        }
        return aid || "default";
      })
      .catch(function (err) {
        log("ERROR", "resolve_mma_agent_failed", { error: String(err) });
        return "default";
      });
    return agentResolvePromise;
  }

  function parseHourFromTimestamp(ts) {
    var p = berlinPartsFromTs(ts);
    return p ? p.hour : null;
  }

  function buildPhaseDefs(events) {
    if (!events.length) return [];
    var defs = [];
    var i = 0;
    while (i < events.length) {
      var start = i;
      var key = events[i].phaseKey || events[i].year + "-00";
      while (i + 1 < events.length && (events[i + 1].phaseKey || "") === key) i += 1;
      var end = i;
      var first = events[start];
      var last = events[end];
      defs.push({
        start: start,
        end: end,
        year: first.yearNum || Number(first.year) || 0,
        von: first.phaseVon || first.monthLabel || "—",
        bis: last.phaseBis || last.monthLabel || "—",
        label: first.phaseLabel || (first.monthLabel + "–" + last.monthLabel),
      });
      i += 1;
    }
    return defs;
  }

  function buildMajorMarkers(events) {
    var major = [];
    var lastYear = null;
    events.forEach(function (ev, idx) {
      if (ev.year !== lastYear) {
        major.push(idx);
        lastYear = ev.year;
      }
    });
    return major.length ? major : [0];
  }

  function aggregateByMonth(dayEvents) {
    var byMonth = {};
    (dayEvents || []).forEach(function (d) {
      var key = d.phaseKey || d.year + "-00";
      if (!byMonth[key]) {
        byMonth[key] = {
          monthKey: key,
          days: [],
          themeCount: 0,
          yearNum: d.yearNum || 0,
          monthLabel: d.monthLabel || "—",
          year: d.year,
        };
      }
      byMonth[key].days.push(d);
      byMonth[key].themeCount += Number(d.themeCount || 0);
    });
    return Object.keys(byMonth).sort().map(function (key) {
      var m = byMonth[key];
      var y = String(m.yearNum || key.split("-")[0]);
      return {
        zoomLevel: "month",
        monthKey: key,
        dayId: null,
        year: y,
        yearNum: m.yearNum,
        monthLabel: m.monthLabel,
        phaseKey: key,
        phaseVon: m.monthLabel,
        phaseBis: m.monthLabel,
        phaseLabel: m.monthLabel + " " + y,
        title: m.monthLabel + " " + y,
        labelShort: m.monthLabel + " · " + y.slice(2),
        copy: m.days.length + " tage · " + m.themeCount + " theme(s)",
        childDayIds: m.days.map(function (x) { return x.dayId; }),
        themeCount: m.themeCount,
        dayCount: m.days.length,
        source: "cascade",
      };
    });
  }

  function daysInMonth(dayEvents, monthKey) {
    return (dayEvents || [])
      .filter(function (d) { return d.phaseKey === monthKey; })
      .map(function (d) {
        return Object.assign({}, d, {
          zoomLevel: "day",
          monthKey: monthKey,
          title: formatDayLabel(d.dayId, "short"),
          labelShort: formatDayLabel(d.dayId, "short"),
          copy: (d.themeCount || 0) + " theme(s) · " + formatDayLabel(d.dayId, "iso"),
        });
      });
  }

  function buildHourSlots(dayId) {
    var slots = [];
    for (var h = 0; h < 24; h += 1) {
      var label = String(h).padStart(2, "0") + ":00";
      slots.push({
        zoomLevel: "hour",
        monthKey: dayId ? dayId.slice(0, 7) : null,
        dayId: dayId,
        hour: h,
        hourLabel: label,
        title: label,
        labelShort: label,
        year: dayId ? dayId.slice(0, 4) : "—",
        yearNum: dayId ? Number(dayId.slice(0, 4)) : 0,
        monthLabel: dayId ? monthLabel(Number(dayId.slice(5, 7)) - 1) : "—",
        phaseKey: dayId + "-h" + h,
        phaseVon: label,
        phaseBis: label,
        copy: "ruhe · keine events",
        eventCount: 0,
        source: "hour",
      });
    }
    return slots;
  }

  function dayTsRange(dayId, hour) {
    if (!isIsoDay(dayId)) return { from: "", to: "" };
    var off = berlinOffsetForDay(dayId);
    if (hour == null || hour === undefined) {
      return {
        from: dayId + "T00:00:00.000" + off,
        to: dayId + "T23:59:59.999" + off,
      };
    }
    var h = String(hour).padStart(2, "0");
    return {
      from: dayId + "T" + h + ":00:00.000" + off,
      to: dayId + "T" + h + ":59:59.999" + off,
    };
  }

  function mmaEventsQuery(params) {
    var q = "/api/mma/events/search?limit=" + encodeURIComponent(String(params.limit || 500));
    if (params.agent_id) q += "&agent_id=" + encodeURIComponent(params.agent_id);
    if (params.from_ts) q += "&from_ts=" + encodeURIComponent(params.from_ts);
    if (params.to_ts) q += "&to_ts=" + encodeURIComponent(params.to_ts);
    if (params.event_type) q += "&event_type=" + encodeURIComponent(params.event_type);
    if (params.session_id) q += "&session_id=" + encodeURIComponent(params.session_id);
    (params.tags || []).forEach(function (t) {
      q += "&tag=" + encodeURIComponent(t);
    });
    return fetchJson(q);
  }

  function senderFromEvent(ev) {
    var parts = ev.participants || [];
    if (parts.length) {
      var p = parts[0];
      var label = p.display_name || p.persona || p.role || "unbekannt";
      var key = String(label).toLowerCase().replace(/\s+/g, "_");
      return { key: key, label: label, role: p.role || "", source: p.source || "" };
    }
    var meta = ev.metadata || {};
    var role = meta.role || ev.event_type || "event";
    return { key: String(role).toLowerCase(), label: role, role: role, source: meta.source || "" };
  }

  function roomFromEvent(ev) {
    var flags = ev.context_flags || {};
    var meta = ev.metadata || {};
    var name = flags.discord_channel_name || meta.channel_name || flags.channel_name || "";
    var id = String(flags.discord_channel_id || meta.channel_id || "");
    if (name) {
      var clean = String(name).replace(/^#/, "");
      return {
        key: clean.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
        label: clean,
        channelId: id,
      };
    }
    if (id) {
      return { key: "ch_" + id, label: "channel " + id.slice(0, 10), channelId: id };
    }
    var tags = ev.tags || [];
    for (var ti = 0; ti < tags.length; ti += 1) {
      if (String(tags[ti]).indexOf("channel:") === 0) {
        var ch = String(tags[ti]).slice(8);
        return { key: ch.toLowerCase().replace(/[^a-z0-9]+/g, "_"), label: ch, channelId: "" };
      }
    }
    return { key: "ohne_raum", label: "ohne raum", channelId: "" };
  }

  function normalizeMmaEvent(ev) {
    var sem = ev.extracted_semantics || {};
    var sender = senderFromEvent(ev);
    var room = roomFromEvent(ev);
    var ts = ev.timestamp || ev.created_at || "";
    return {
      id: ev.id || ev.event_id || "",
      eventId: ev.event_id || "",
      sessionId: ev.session_id || "",
      eventType: ev.event_type || "",
      timestamp: ts,
      hour: parseHourFromTimestamp(ts),
      senderKey: sender.key,
      senderLabel: sender.label,
      senderRole: sender.role,
      roomKey: room.key,
      roomLabel: room.label,
      channelId: room.channelId,
      summary: ev.content_summary || "",
      topics: sem.topics || [],
      insights: sem.extracted_insights || [],
      keyPhrases: sem.key_phrases || [],
      erip: sem.erip || null,
      valence: sem.emotional_valence || null,
      privacy_level: sem.privacy_level,
      tags: ev.tags || [],
      processingState: (ev.metadata && ev.metadata.processing_state) || "",
      role: (ev.metadata && ev.metadata.role) || sender.role,
      thinkingPreview: (ev.metadata && ev.metadata.thinking_preview) || "",
      raw: ev,
    };
  }

  function filterEventsByHour(events, hour) {
    return (events || []).filter(function (e) {
      return e.hour === hour;
    });
  }

  function filterEventsBySenders(events, senderKeys) {
    if (!senderKeys || !senderKeys.length) return events || [];
    var set = {};
    senderKeys.forEach(function (k) { set[k] = true; });
    return (events || []).filter(function (e) { return set[e.senderKey]; });
  }

  function collectRooms(events) {
    var map = {};
    (events || []).forEach(function (e) {
      if (!map[e.roomKey]) {
        map[e.roomKey] = { key: e.roomKey, label: e.roomLabel, count: 0 };
      }
      map[e.roomKey].count += 1;
    });
    return Object.keys(map).map(function (k) { return map[k]; })
      .sort(function (a, b) { return b.count - a.count; });
  }

  function filterEventsByRooms(events, roomKeys) {
    if (!roomKeys || !roomKeys.length) return events || [];
    var set = {};
    roomKeys.forEach(function (k) { set[k] = true; });
    return (events || []).filter(function (e) { return set[e.roomKey]; });
  }

  function groupEventsByRoom(events) {
    var rooms = {};
    (events || []).forEach(function (e) {
      if (!rooms[e.roomKey]) {
        rooms[e.roomKey] = { key: e.roomKey, label: e.roomLabel, events: [] };
      }
      rooms[e.roomKey].events.push(e);
    });
    return Object.keys(rooms).map(function (k) {
      var r = rooms[k];
      r.sessions = groupEventsBySession(r.events);
      r.count = r.events.length;
      return r;
    }).sort(function (a, b) { return b.count - a.count; });
  }

  function collectSenders(events) {
    var map = {};
    (events || []).forEach(function (e) {
      if (!map[e.senderKey]) {
        map[e.senderKey] = { key: e.senderKey, label: e.senderLabel, count: 0, role: e.senderRole };
      }
      map[e.senderKey].count += 1;
    });
    return Object.keys(map).map(function (k) { return map[k]; })
      .sort(function (a, b) { return b.count - a.count; });
  }

  function groupEventsBySession(events) {
    var groups = {};
    (events || []).forEach(function (e) {
      var sid = e.sessionId || ("solo-" + e.id);
      if (!groups[sid]) groups[sid] = { sessionId: sid, events: [], senders: {} };
      groups[sid].events.push(e);
      groups[sid].senders[e.senderKey] = e.senderLabel;
    });
    return Object.keys(groups).map(function (sid) {
      var g = groups[sid];
      g.events.sort(function (a, b) {
        return String(a.timestamp).localeCompare(String(b.timestamp));
      });
      g.participantLabels = Object.keys(g.senders).map(function (k) { return g.senders[k]; });
      g.isConversation = g.events.length > 1 || g.participantLabels.length > 1;
      return g;
    }).sort(function (a, b) {
      var ta = a.events[0] && a.events[0].timestamp || "";
      var tb = b.events[0] && b.events[0].timestamp || "";
      return String(ta).localeCompare(String(tb));
    });
  }

  var mmaDayCache = {};

  function loadMmaDayEvents(dayId, force) {
    if (!force && mmaDayCache[dayId]) {
      return Promise.resolve(mmaDayCache[dayId]);
    }
    var range = dayTsRange(dayId, null);
    var t0 = performance.now();
    log("INFO", "load_mma_day_start", { day_id: dayId, from: range.from, to: range.to });
    return resolveMmaAgentId().then(function (agentId) {
      return mmaEventsQuery({
        agent_id: agentId,
        from_ts: range.from,
        to_ts: range.to,
        limit: 500,
      }).then(function (r) {
        var events = (r.events || []).map(normalizeMmaEvent).filter(function (e) {
          var p = berlinPartsFromTs(e.timestamp);
          return p && p.dayId === dayId;
        });
        mmaDayCache[dayId] = events;
        log("INFO", "load_mma_day_done", {
          day_id: dayId,
          agent_id_prefix: String(agentId).slice(0, 20),
          count: events.length,
          raw_count: (r.events || []).length,
          ms: Math.round(performance.now() - t0),
        });
        return events;
      });
    }).catch(function (err) {
      log("WARN", "load_mma_day_failed", { day_id: dayId, error: String(err) });
      mmaDayCache[dayId] = [];
      return [];
    });
  }

  function loadHourEvents(dayId, hour) {
    return loadMmaDayEvents(dayId).then(function (all) {
      return filterEventsByHour(all, hour);
    });
  }

  function clearMmaDayCache() {
    mmaDayCache = {};
  }

  function loadHourBuckets(dayId) {
    var t0 = performance.now();
    log("INFO", "load_hours_start", { day_id: dayId });
    return loadMmaDayEvents(dayId).then(function (all) {
      var slots = buildHourSlots(dayId);
      all.forEach(function (ev) {
        var h = ev.hour;
        if (h == null || h < 0 || h > 23) return;
        slots[h].eventCount += 1;
      });
      slots.forEach(function (s) {
        s.copy = s.eventCount
          ? s.eventCount + " enrichment(s)"
          : "ruhe · " + formatDayLabel(dayId, "short");
      });
      log("INFO", "load_hours_done", {
        day_id: dayId,
        total_events: all.length,
        ms: Math.round(performance.now() - t0),
      });
      return slots;
    }).catch(function (err) {
      log("WARN", "load_hours_fallback", { day_id: dayId, error: String(err) });
      return buildHourSlots(dayId);
    });
  }

  function buildPhaseDefsForYear(events) {
    if (!events.length) return [];
    var defs = [];
    var i = 0;
    while (i < events.length) {
      var start = i;
      var y = events[i].yearNum || Number(events[i].year) || 0;
      while (i + 1 < events.length) {
        var ny = events[i + 1].yearNum || Number(events[i + 1].year) || 0;
        if (ny !== y) break;
        i += 1;
      }
      defs.push({
        start: start,
        end: i,
        year: y,
        von: String(y),
        bis: String(y),
        label: String(y),
      });
      i += 1;
    }
    return defs;
  }

  function isoWeekForDay(dayId) {
    if (!isIsoDay(dayId)) return { kw: 0, year: 0, key: "?" };
    var p = dayId.split("-");
    var y = Number(p[0]);
    var m = Number(p[1]);
    var d = Number(p[2]);
    var date = new Date(Date.UTC(y, m - 1, d));
    var dayNum = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - dayNum);
    var isoYear = date.getUTCFullYear();
    var yearStart = new Date(Date.UTC(isoYear, 0, 1));
    var kw = Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
    return {
      kw: kw,
      year: isoYear,
      key: isoYear + "-W" + String(kw).padStart(2, "0"),
    };
  }

  function buildPhaseDefsForCalendarWeeks(events) {
    if (!events.length) return [];
    var defs = [];
    var i = 0;
    while (i < events.length) {
      var start = i;
      var firstKw = isoWeekForDay(events[i].dayId);
      var key = firstKw.key;
      while (i + 1 < events.length) {
        var nextKw = isoWeekForDay(events[i + 1].dayId);
        if (nextKw.key !== key) break;
        i += 1;
      }
      var end = i;
      var kwLabel = "KW " + String(firstKw.kw).padStart(2, "0");
      defs.push({
        start: start,
        end: end,
        year: firstKw.year,
        kw: firstKw.kw,
        von: events[start].labelShort || events[start].title,
        bis: events[end].labelShort || events[end].title,
        label: kwLabel,
      });
      i += 1;
    }
    return defs;
  }

  function buildPhaseDefsForDayParts(events, parts) {
    if (!events.length) return [];
    var n = events.length;
    var chunk = Math.max(1, Math.ceil(n / parts));
    var defs = [];
    for (var c = 0; c < parts; c += 1) {
      var start = c * chunk;
      var end = Math.min(n - 1, (c + 1) * chunk - 1);
      if (start > end) break;
      defs.push({
        start: start,
        end: end,
        year: events[start].yearNum || 0,
        von: events[start].labelShort || events[start].title,
        bis: events[end].labelShort || events[end].title,
        label: "block " + (c + 1),
      });
    }
    return defs;
  }

  function buildPhaseDefsForHours() {
    return [
      { start: 0, end: 5, year: 0, von: "00", bis: "05", label: "nacht" },
      { start: 6, end: 11, year: 0, von: "06", bis: "11", label: "tag" },
      { start: 12, end: 17, year: 0, von: "12", bis: "17", label: "nachm" },
      { start: 18, end: 23, year: 0, von: "18", bis: "23", label: "abend" },
    ];
  }

  function mapCascadeDays(days) {
    var filtered = (days || []).filter(function (d) { return isIsoDay(d.day_id); });
    filtered.sort(function (a, b) {
      return String(a.day_id).localeCompare(String(b.day_id));
    });

    return filtered.map(function (d, idx) {
      var dt = parseDayDate(d.day_id);
      var y = dt ? String(dt.y) : "—";
      var ml = dt ? monthLabel(dt.m) : "—";
      var tc = Number(d.theme_count || 0);
      var title = tc ? tc + " THEME" + (tc === 1 ? "" : "S") : "TAG";
      return {
        index: idx,
        zoomLevel: "day",
        dayId: d.day_id,
        nodeId: d.node_id || ("day_" + d.day_id),
        year: y,
        yearNum: dt ? dt.y : 0,
        monthLabel: ml,
        monthKey: dt ? (dt.y + "-" + String(dt.m + 1).padStart(2, "0")) : y,
        phaseKey: dt ? (dt.y + "-" + String(dt.m + 1).padStart(2, "0")) : y,
        phaseVon: ml,
        phaseBis: ml,
        phaseLabel: ml,
        title: formatDayLabel(d.day_id, "short"),
        labelShort: formatDayLabel(d.day_id, "short"),
        copy: formatDayLabel(d.day_id, "iso") + " · " + tc + " theme(s)",
        themeCount: tc,
        source: "cascade",
        meta: d.properties || {},
      };
    });
  }

  function mapMmaBuckets(buckets) {
    var sorted = (buckets || []).slice().sort(function (a, b) {
      return String(a.bucket_id).localeCompare(String(b.bucket_id));
    });
    return sorted.map(function (b, idx) {
      var id = b.bucket_id || b.label || ("bucket-" + idx);
      var dt = parseDayDate(id);
      var y = dt ? String(dt.y) : String(id).slice(0, 4);
      var top = (b.pairs || []).slice(0, 2).map(function (p) {
        return (p.tag_a + "×" + p.tag_b).replace(/_/g, " ");
      }).join(" · ");
      return {
        index: idx,
        dayId: id,
        bucketId: id,
        year: y,
        yearNum: dt ? dt.y : Number(y) || 0,
        monthLabel: dt ? monthLabel(dt.m) : "—",
        phaseKey: dt ? (dt.y + "-" + String(dt.m + 1).padStart(2, "0")) : y,
        phaseVon: dt ? monthLabel(dt.m) : "—",
        phaseBis: dt ? monthLabel(dt.m) : "—",
        phaseLabel: b.label || id,
        title: (b.event_count || 0) + " EVENTS",
        copy: top || "mma tag bucket",
        eventCount: b.event_count || 0,
        pairs: b.pairs || [],
        source: "mma",
      };
    });
  }

  function buildMmaLinks(events) {
    var links = [];
    events.forEach(function (ev, idx) {
      (ev.pairs || []).slice(0, 4).forEach(function (_, pi) {
        var target = idx + pi + 1;
        if (target < events.length) links.push([idx, target]);
      });
    });
    return links;
  }

  function buildThemeLinks(events, bundles) {
    var themeToIdx = {};
    var links = [];
    events.forEach(function (ev, idx) {
      var pack = bundles[ev.dayId];
      if (!pack || !pack.themes) return;
      pack.themes.forEach(function (t) {
        var tid = t.theme_id || t.id || "";
        if (!tid) return;
        if (themeToIdx[tid] != null && themeToIdx[tid] !== idx) {
          links.push([themeToIdx[tid], idx]);
        } else {
          themeToIdx[tid] = idx;
        }
      });
    });
    return links.slice(0, 80);
  }

  var PERSON_ALIAS_MAP = { assistant: "agent", user: "alex", alex: "alex", sam: "sam", agent: "agent" };
  var PERSON_DISPLAY_LABELS = { agent: "Agent", alex: "Alex", sam: "Sam" };

  function applyPersonAliasConfig(cfg) {
    if (!cfg || typeof cfg !== "object") return;
    if (cfg.aliases && typeof cfg.aliases === "object") {
      PERSON_ALIAS_MAP = cfg.aliases;
    }
    if (cfg.display_labels && typeof cfg.display_labels === "object") {
      PERSON_DISPLAY_LABELS = cfg.display_labels;
    }
    log("INFO", "person_alias_config_applied", {
      alias_count: Object.keys(PERSON_ALIAS_MAP || {}).length,
      label_count: Object.keys(PERSON_DISPLAY_LABELS || {}).length,
    });
  }

  function loadPersonAliasConfig() {
    return fetchJson("/api/cascade/persons/aliases")
      .then(function (cfg) {
        applyPersonAliasConfig(cfg);
        return cfg;
      })
      .catch(function (err) {
        log("WARN", "person_alias_config_load_failed", { error: String(err) });
        return null;
      });
  }

  function normalizePersonId(raw) {
    var pid = String(raw || "").trim().toLowerCase().replace(/^person_/, "").replace(/ /g, "_");
    if (!pid) return "";
    return PERSON_ALIAS_MAP[pid] || pid;
  }

  function personDisplayLabel(personId) {
    var pid = normalizePersonId(personId);
    if (!pid) return "";
    return PERSON_DISPLAY_LABELS[pid] || pid.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function archivalMatchesFilters(a) {
    if (CONFIG.personId) {
      var meta = (a && a.metadata) || {};
      var want = CONFIG.personId;
      if (normalizePersonId(meta.person_id) === want) return true;
      var mentioned = meta.persons_mentioned || meta.mentioned_persons || [];
      for (var i = 0; i < mentioned.length; i++) {
        if (normalizePersonId(mentioned[i]) === want) return true;
      }
      return false;
    }
    return true;
  }

  function buildCascadeDaysUrl() {
    var url = "/api/cascade/days?limit=" + CONFIG.dayLimit;
    if (CONFIG.themeId) url += "&theme_id=" + encodeURIComponent(CONFIG.themeId);
    if (CONFIG.personId) url += "&person_id=" + encodeURIComponent(CONFIG.personId);
    return url;
  }

  function loadCascade() {
    var t0 = performance.now();
    log("INFO", "load_cascade_start", {
      limit: CONFIG.dayLimit,
      theme_id: CONFIG.themeId || null,
      person_id: CONFIG.personId || null,
    });
    return fetchJson(buildCascadeDaysUrl()).then(function (r) {
      var events = mapCascadeDays(r.days || []);
      var result = {
        source: "cascade",
        events: events,
        phaseDefs: buildPhaseDefs(events),
        major: buildMajorMarkers(events),
        links: [],
        bundles: {},
      };
      log("INFO", "load_cascade_done", { count: events.length, ms: Math.round(performance.now() - t0) });
      return result;
    });
  }

  function loadMma() {
    var t0 = performance.now();
    log("INFO", "load_mma_start", { window: CONFIG.mmaWindow });
    return fetchJson("/api/mma/spiral/buckets?time_window=" + encodeURIComponent(CONFIG.mmaWindow)).then(function (r) {
      var events = mapMmaBuckets(r.buckets || []);
      var result = {
        source: "mma",
        events: events,
        phaseDefs: buildPhaseDefs(events),
        major: buildMajorMarkers(events),
        links: buildMmaLinks(events),
        buckets: r.buckets || [],
      };
      log("INFO", "load_mma_done", { count: events.length, ms: Math.round(performance.now() - t0) });
      return result;
    });
  }

  function loadDayBundle(dayId) {
    return fetchJson("/api/cascade/day/" + encodeURIComponent(dayId)).then(function (b) {
      var themes = (b.themes || []).map(function (t) {
        return {
          theme_id: t.theme_id || t.id,
          archivals: t.archivals || [],
          label: formatThemeLabel(t.theme_id || t.id),
        };
      });
      if (CONFIG.themeId) {
        themes = themes.filter(function (t) {
          return String(t.theme_id || "").replace(/^theme_/, "") === CONFIG.themeId;
        });
      }
      themes = themes.map(function (t) {
        var archs = (t.archivals || []).filter(archivalMatchesFilters);
        return Object.assign({}, t, { archivals: archs });
      }).filter(function (t) {
        return !CONFIG.personId || (t.archivals && t.archivals.length);
      });
      return { dayId: dayId, themes: themes, archivals: b.archivals || [], raw: b };
    });
  }

  function loadMemory(memoryId) {
    return fetchJson("/api/cascade/memory/" + encodeURIComponent(memoryId));
  }

  function loadMmaTagEvents(tag, bucketId) {
    var q = "/api/mma/events/search?tag=" + encodeURIComponent(tag) +
      "&bucket_id=" + encodeURIComponent(bucketId) + "&limit=8";
    return fetchJson(q);
  }

  function fetchThemeSuggestions(q, limit) {
    var url = "/api/cascade/themes/suggest?limit=" + (limit || 12);
    if (q) url += "&q=" + encodeURIComponent(q);
    return fetchJson(url).then(function (r) {
      return r.themes || [];
    });
  }

  function fetchPersonSuggestions(q, limit) {
    var url = "/api/cascade/persons/suggest?limit=" + (limit || 12);
    if (q) url += "&q=" + encodeURIComponent(q);
    return fetchJson(url).then(function (r) {
      return r.persons || [];
    });
  }

  function setThemeFilter(themeId) {
    CONFIG.themeId = String(themeId || "").trim().replace(/^theme_/, "");
    log("INFO", "theme_filter_set", { theme_id: CONFIG.themeId || null });
  }

  function setPersonFilter(personId) {
    CONFIG.personId = normalizePersonId(personId);
    log("INFO", "person_filter_set", { person_id: CONFIG.personId || null });
  }

  function setCascadeFilters(themeId, personId) {
    setThemeFilter(themeId);
    setPersonFilter(personId);
  }

  function load() {
    var aliasReady = loadPersonAliasConfig();
    if (CONFIG.source === "mma") return aliasReady.then(function () { return loadMma(); });
    return aliasReady.then(function () { return loadCascade(); });
  }

  root.TimeCircleData = {
    CONFIG: CONFIG,
    log: log,
    load: load,
    loadPersonAliasConfig: loadPersonAliasConfig,
    normalizePersonId: normalizePersonId,
    personDisplayLabel: personDisplayLabel,
    fetchThemeSuggestions: fetchThemeSuggestions,
    fetchPersonSuggestions: fetchPersonSuggestions,
    setThemeFilter: setThemeFilter,
    setPersonFilter: setPersonFilter,
    setCascadeFilters: setCascadeFilters,
    loadDayBundle: loadDayBundle,
    loadMemory: loadMemory,
    loadMmaTagEvents: loadMmaTagEvents,
    loadHourBuckets: loadHourBuckets,
    loadHourEvents: loadHourEvents,
    loadMmaDayEvents: loadMmaDayEvents,
    resolveMmaAgentId: resolveMmaAgentId,
    normalizeMmaEvent: normalizeMmaEvent,
    collectSenders: collectSenders,
    collectRooms: collectRooms,
    filterEventsByRooms: filterEventsByRooms,
    groupEventsByRoom: groupEventsByRoom,
    isoWeekForDay: isoWeekForDay,
    buildPhaseDefsForCalendarWeeks: buildPhaseDefsForCalendarWeeks,
    buildThemeLinks: buildThemeLinks,
    formatThemeLabel: formatThemeLabel,
    formatDayLabel: formatDayLabel,
    aggregateByMonth: aggregateByMonth,
    daysInMonth: daysInMonth,
    buildHourSlots: buildHourSlots,
    buildPhaseDefs: buildPhaseDefs,
    buildPhaseDefsForYear: buildPhaseDefsForYear,
    filterEventsBySenders: filterEventsBySenders,
    groupEventsBySession: groupEventsBySession,
    buildPhaseDefsForHours: buildPhaseDefsForHours,
    buildMajorMarkers: buildMajorMarkers,
  };
})(window);
