/**
 * time_circle_hour_panel.js – Stunden-Panel: MMA-Enrichment, Raum-Filter primär, Person optional.
 * Created: 2026-06-28
 * Last updated: 2026-06-28
 */
(function (root) {
  "use strict";

  var D = root.TimeCircleData;
  var filterStateByDay = {};

  function log(level, message, ctx) {
    var payload = {
      timestamp: new Date().toISOString(),
      level: level,
      module: "time_circle_hour_panel",
      message: message,
    };
    if (ctx) payload.context = ctx;
    var fn = level === "ERROR" ? console.error : level === "WARN" ? console.warn : console.log;
    fn(JSON.stringify(payload));
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatTime(ts) {
    if (!ts) return "—";
    var d = new Date(ts);
    if (Number.isNaN(d.getTime())) return String(ts).slice(11, 19) || "—";
    try {
      return new Intl.DateTimeFormat("de-DE", {
        timeZone: (D && D.CONFIG && D.CONFIG.tz) || "Europe/Berlin",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(d);
    } catch (e) {
      return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
    }
  }

  function getFilterState(dayId) {
    if (!filterStateByDay[dayId]) {
      filterStateByDay[dayId] = { rooms: [], persons: [] };
    }
    return filterStateByDay[dayId];
  }

  function roleClass(role) {
    var r = String(role || "").toLowerCase();
    if (r === "assistant" || r === "bot") return "role-assistant";
    if (r === "user") return "role-user";
    return "role-other";
  }

  function renderTopics(topics) {
    if (!topics || !topics.length) return "";
    return '<div class="hour-topics">' + topics.map(function (t) {
      return '<span class="hour-topic">' + escapeHtml(String(t).replace(/_/g, " ")) + "</span>";
    }).join("") + "</div>";
  }

  function renderErip(erip) {
    if (!erip) return "";
    return '<span class="hour-erip">E' + escapeHtml(erip.E) + " I" + escapeHtml(erip.I) +
      " P" + escapeHtml(erip.P) + " R" + escapeHtml(erip.R) + "</span>";
  }

  function renderInsights(insights) {
    if (!insights || !insights.length) return "";
    return '<ul class="hour-insights">' + insights.slice(0, 4).map(function (x) {
      return "<li>" + escapeHtml(String(x).substring(0, 180)) + "</li>";
    }).join("") + "</ul>";
  }

  function renderMessageCard(ev, color) {
    var stateBadge = ev.processingState
      ? '<span class="hour-state">' + escapeHtml(ev.processingState.replace(/_/g, " ")) + "</span>"
      : "";
    return (
      '<article class="hour-msg ' + roleClass(ev.role || ev.senderRole) + '" style="--c:' + escapeHtml(color) + '">' +
      '<header class="hour-msg-head">' +
      '<span class="hour-msg-time">' + escapeHtml(formatTime(ev.timestamp)) + "</span>" +
      '<span class="hour-msg-sender">' + escapeHtml(ev.senderLabel) + "</span>" +
      (ev.senderRole ? '<span class="hour-msg-role">' + escapeHtml(ev.senderRole) + "</span>" : "") +
      stateBadge +
      "</header>" +
      '<p class="hour-msg-text">' + escapeHtml(ev.summary || "(kein text)") + "</p>" +
      renderTopics(ev.topics) +
      renderInsights(ev.insights) +
      (ev.erip ? '<footer class="hour-msg-meta">' + renderErip(ev.erip) + "</footer>" : "") +
      "</article>"
    );
  }

  function renderConversationGroup(group, color) {
    var title = group.isConversation
      ? "↔ " + group.participantLabels.join(" · ") + " · " + group.events.length + " nachrichten"
      : "einzel · " + (group.participantLabels[0] || "event");
    var body = group.events.map(function (ev) {
      return renderMessageCard(ev, color);
    }).join("");
    return (
      '<section class="hour-conversation' + (group.isConversation ? " is-thread" : "") + '">' +
      '<div class="hour-conv-head">' + escapeHtml(title) + "</div>" +
      body +
      "</section>"
    );
  }

  function renderRoomBlock(room, color) {
    var sessions = room.sessions || [];
    var convCount = sessions.filter(function (g) { return g.isConversation; }).length;
    var inner = sessions.map(function (g) {
      return renderConversationGroup(g, color);
    }).join("");
    return (
      '<section class="hour-room-block">' +
      '<div class="hour-room-head">#' + escapeHtml(room.label) + " · " + room.count +
      " · " + sessions.length + " session(s)" +
      (convCount ? " · " + convCount + " konv." : "") +
      "</div>" +
      inner +
      "</section>"
    );
  }

  function wireFilterChips(wrap, kind, dayId, selected, onChange) {
    if (!wrap) return;
    wrap.querySelectorAll(".hour-sender-chip").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-filter-key");
        var state = getFilterState(dayId);
        var list = kind === "room" ? state.rooms.slice() : state.persons.slice();
        if (key === "__all__") {
          list = [];
        } else {
          var idx = list.indexOf(key);
          if (idx >= 0) list.splice(idx, 1);
          else list.push(key);
        }
        if (kind === "room") state.rooms = list;
        else state.persons = list;
        log("INFO", "hour_filter_changed", { day_id: dayId, kind: kind, selected: list });
        onChange();
      });
    });
  }

  function renderFilterRow(container, opts) {
    var wrap = container.querySelector(opts.targetId);
    if (!wrap) return;
    var selected = opts.selected || [];
    var allActive = !selected.length;
    var html = '<span class="hour-filter-label">' + escapeHtml(opts.label) + ":</span>";
    html +=
      '<button type="button" class="hour-sender-chip' + (allActive ? " active" : "") +
      '" data-filter-key="__all__">Alle (' + opts.total + ")</button>";
    (opts.items || []).forEach(function (item) {
      var active = selected.indexOf(item.key) >= 0;
      html +=
        '<button type="button" class="hour-sender-chip' + (active ? " active" : "") +
        '" data-filter-key="' + escapeHtml(item.key) + '" title="' + escapeHtml(item.role || item.label) + '">' +
        escapeHtml(item.label) + " (" + item.count + ")</button>";
    });
    wrap.innerHTML = html;
    wireFilterChips(wrap, opts.kind, opts.dayId, selected, opts.onChange);
  }

  function renderBody(container, events, color, dayId, hour) {
    var body = container.querySelector("#hourPanelBody");
    if (!body) return;
    var state = getFilterState(dayId);
    var filtered = D.filterEventsByRooms(events, state.rooms);
    filtered = D.filterEventsBySenders(filtered, state.persons);

    renderFilterRow(container, {
      targetId: "#hourRoomFilters",
      label: "Raum",
      kind: "room",
      dayId: dayId,
      total: events.length,
      selected: state.rooms,
      items: D.collectRooms(events),
      onChange: function () { renderBody(container, events, color, dayId, hour); },
    });
    renderFilterRow(container, {
      targetId: "#hourPersonFilters",
      label: "Person",
      kind: "person",
      dayId: dayId,
      total: filtered.length || events.length,
      selected: state.persons,
      items: D.collectSenders(D.filterEventsByRooms(events, state.rooms)),
      onChange: function () { renderBody(container, events, color, dayId, hour); },
    });

    if (!filtered.length) {
      body.innerHTML =
        '<p class="hour-empty">' +
        (events.length
          ? "Keine Einträge für die gewählten Räume/Personen in " + escapeHtml(String(hour).padStart(2, "0")) + ":00."
          : "Keine MMA-Enrichment-Einträge in dieser Stunde.") +
        "</p>";
      return;
    }

    var roomGroups = D.groupEventsByRoom(filtered);
    var stats = container.querySelector("#hourPanelStats");
    if (stats) {
      stats.textContent = filtered.length + " eintrag(e) · " + roomGroups.length + " raum/raum(e)";
    }

    body.innerHTML = roomGroups.map(function (room) {
      return renderRoomBlock(room, color);
    }).join("");
  }

  function render(container, opts) {
    if (!D) {
      container.innerHTML = '<p class="graph-error">TimeCircleData fehlt</p>';
      return Promise.resolve();
    }
    var dayId = opts.dayId;
    var hour = opts.hour;
    var color = opts.color || "#41dce1";
    var hourLabel = String(hour).padStart(2, "0") + ":00";

    container.classList.remove("graph-explorer-open");
    container.innerHTML =
      '<button type="button" class="tree-close" id="hourPanelClose">×</button>' +
      '<div class="tree-path">' +
      '<span><b>stunde</b> ' + escapeHtml(hourLabel) + " · " + escapeHtml(dayId) + "</span>" +
      "</div>" +
      '<div class="hour-panel-head">' +
      '<span class="hour-panel-title">MMA · enrichment · nach raum</span>' +
      '<span class="hour-panel-stats" id="hourPanelStats">Lade …</span>' +
      "</div>" +
      '<div class="hour-sender-filters" id="hourRoomFilters"></div>' +
      '<div class="hour-sender-filters hour-person-filters" id="hourPersonFilters"></div>' +
      '<div class="hour-panel-body" id="hourPanelBody"><p class="hour-loading">Lade enrichment …</p></div>';

    var closeBtn = container.querySelector("#hourPanelClose");
    if (closeBtn) {
      closeBtn.onclick = function () {
        if (root.__closeTree) root.__closeTree();
      };
    }

    var t0 = performance.now();
    log("INFO", "hour_panel_start", { day_id: dayId, hour: hour });

    return D.loadHourEvents(dayId, hour).then(function (events) {
      if (opts.genCheck && !opts.genCheck()) return;
      renderBody(container, events, color, dayId, hour);
      log("INFO", "hour_panel_done", {
        day_id: dayId,
        hour: hour,
        count: events.length,
        rooms: D.collectRooms(events).length,
        ms: Math.round(performance.now() - t0),
      });
    }).catch(function (err) {
      var bodyEl = container.querySelector("#hourPanelBody");
      if (bodyEl) bodyEl.innerHTML = '<p class="graph-error">Fehler: ' + escapeHtml(err.message) + "</p>";
      log("ERROR", "hour_panel_failed", { day_id: dayId, hour: hour, error: String(err) });
    });
  }

  root.TimeCircleHourPanel = {
    render: render,
    clearFilters: function (dayId) {
      if (dayId) delete filterStateByDay[dayId];
      else filterStateByDay = {};
    },
  };
})(window);
