/**
 * archive_prose_render.js – Gemeinsame Archiv-Lesetypografie (/stream/archive + Zeitkreis).
 * Created: 2026-06-29
 * Last updated: 2026-06-29
 */
(function (root) {
  "use strict";

  var ERIP_BLOCK_MARKER = "**ERIP (required):**";
  var MEINE_NOTIZ_HDR = "**Meine Notiz:**";

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
  }

  function splitArchiveNoteAndBody(content, apiNote) {
    var c = content || "";
    var displayNote = apiNote != null && String(apiNote).trim() ? String(apiNote).trim() : "";
    if (displayNote === "(keine Notiz)") displayNote = "";
    var idx = c.indexOf(MEINE_NOTIZ_HDR);
    var bodyMain = c;
    if (idx >= 0) {
      var start = idx + MEINE_NOTIZ_HDR.length;
      var rest = c.slice(start);
      if (rest.charAt(0) === "\n") rest = rest.slice(1);
      var epos = rest.indexOf(ERIP_BLOCK_MARKER);
      var parsedNote = (epos >= 0 ? rest.slice(0, epos) : rest).trim();
      if (!displayNote) displayNote = parsedNote;
      var before = c.slice(0, idx).replace(/\s+$/, "");
      if (epos >= 0) {
        bodyMain = (before ? before + "\n\n" : "") + rest.slice(epos);
      } else {
        bodyMain = before;
      }
    }
    if (displayNote === "(keine Notiz)") displayNote = "";
    return { displayNote: displayNote, bodyMain: (bodyMain || "").trim() };
  }

  /** Einfaches Lesen: Überschriften, **fett**, Absätze (Inhalt vorher escapen). */
  function renderArchivedMarkdown(raw) {
    if (!raw) return '<p class="amd-p amd-empty">—</p>';
    var t = escapeHtml(raw);
    t = t.replace(/^#### (.+)$/gm, '<h4 class="amd-h">$1</h4>');
    t = t.replace(/^### (.+)$/gm, '<h3 class="amd-h">$1</h3>');
    t = t.replace(/^## (.+)$/gm, '<h2 class="amd-h">$1</h2>');
    t = t.replace(/^# (.+)$/gm, '<h1 class="amd-h">$1</h1>');
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong class="amd-strong">$1</strong>');
    var parts = t.split(/\n\n+/);
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].trim();
      if (!p) continue;
      if (/^<h[1-4]/.test(p)) {
        out.push(p);
        continue;
      }
      out.push('<p class="amd-p">' + p.replace(/\n/g, "<br>") + "</p>");
    }
    return out.length ? out.join("") : '<p class="amd-p amd-empty">—</p>';
  }

  function mediaImgSrc(item, agentId, preferFull) {
    var rel = (preferFull ? item.preview_url_full || item.preview_url : item.preview_url || item.preview_url_full) || "";
    if (rel && rel.charAt(0) === "/") {
      var url = rel;
      if (agentId) {
        url += (url.indexOf("?") >= 0 ? "&" : "?") + "agent_id=" + encodeURIComponent(agentId);
      }
      return url;
    }
    var abs = item.preview_url_absolute || item.preview_url_full_absolute || "";
    if (!abs) return "";
    try {
      var parsed = new URL(abs, root.location ? root.location.origin : "");
      if (parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost") {
        return (root.location ? root.location.origin : "") + parsed.pathname + parsed.search;
      }
      return parsed.href;
    } catch (e) {
      return abs;
    }
  }

  function buildArchiveMediaHtml(detail) {
    if (!detail || !detail.media || !detail.media.length) return "";
    var agentId = (detail.agent_id || "").trim();
    var html = '<section class="archive-modal-media" aria-label="Verknüpfte Bilder">';
    html += '<div class="archive-modal-media-kicker">Verknüpftes Bild</div>';
    detail.media.forEach(function (item, idx) {
      var src = mediaImgSrc(item, agentId, false);
      if (!src) return;
      var fullSrc = mediaImgSrc(item, agentId, true);
      html += '<a href="' + escapeHtml(fullSrc || src) + '" target="_blank" rel="noopener" title="Vollbild öffnen">';
      html +=
        '<img class="archive-modal-media-img" src="' +
        escapeHtml(src) +
        '" alt="Archiv-Bild ' +
        (idx + 1) +
        '" loading="lazy" decoding="async" onerror="this.style.display=\'none\';var e=this.nextElementSibling;if(e)e.style.display=\'block\'" />';
      html += "</a>";
      html +=
        '<div class="archive-modal-media-meta" style="margin-top:6px"><a href="' +
        escapeHtml(fullSrc || src) +
        '" target="_blank" rel="noopener">Vollbild</a> · Vorschau komprimiert</div>';
      html +=
        '<div class="archive-modal-media-err" style="display:none">Bild konnte samht geladen werden. <a href="' +
        escapeHtml(src) +
        '" target="_blank" rel="noopener">Direkt öffnen</a></div>';
      var meta = [];
      if (item.media_asset_id) meta.push("media: " + item.media_asset_id);
      if (item.provenance && item.provenance.source_username) meta.push(item.provenance.source_username);
      if (item.semantic_description) meta.push(String(item.semantic_description).slice(0, 180));
      if (meta.length) {
        html += '<div class="archive-modal-media-meta">' + escapeHtml(meta.join(" · ")) + "</div>";
      }
    });
    html += "</section>";
    return html;
  }

  function entryTitleFromTags(tags) {
    if (!tags || !tags.length) return "";
    for (var i = 0; i < tags.length; i++) {
      var t = tags[i];
      if (typeof t === "string" && t.indexOf("Title:") === 0) {
        return t.substring(6).trim();
      }
    }
    return "";
  }

  function buildArchiveModalInnerHtml(m, detail) {
    m = m || {};
    detail = detail || {};
    var disp = (m.agent_name || m.owner_name || "").trim();
    var aid = (m.memory_owner_agent_id || detail.agent_id || m.agent_id || "").trim();
    var primary = disp || aid;
    var apiNote = m.note != null ? String(m.note) : "";
    var contentSrc = detail.content != null ? detail.content : m.content || "";
    var split = splitArchiveNoteAndBody(contentSrc, apiNote);
    var displayNote = split.displayNote;
    var bodyMain = split.bodyMain;
    var memId = detail.memory_id || m.id || m.memory_id || "";

    var html = "";
    if (memId) {
      html += '<div class="archive-modal-memory-id"><strong>memory_id</strong> · ' + escapeHtml(memId) + "</div>";
    }
    html += buildArchiveMediaHtml(detail);
    if (primary) {
      html += '<div class="archive-modal-agent">';
      html += "<strong>Agent</strong> · " + escapeHtml(primary);
      if (aid && disp && disp !== aid) {
        html +=
          '<br><span style="opacity:0.88">' +
          escapeHtml(aid.length > 72 ? aid.slice(0, 68) + "…" : aid) +
          "</span>";
      }
      html += "</div>";
    }
    if (displayNote) {
      html +=
        '<section class="archive-modal-note-card" aria-label="Notiz">' +
        '<div class="archive-modal-note-kicker">Notiz</div>' +
        '<div class="archive-modal-note-text">' +
        renderArchivedMarkdown(displayNote) +
        "</div></section>";
    }
    html += '<div class="archive-modal-prose">' + renderArchivedMarkdown(bodyMain) + "</div>";
    return html;
  }

  root.ArchiveProseRender = {
    escapeHtml: escapeHtml,
    splitArchiveNoteAndBody: splitArchiveNoteAndBody,
    renderArchivedMarkdown: renderArchivedMarkdown,
    mediaImgSrc: mediaImgSrc,
    buildArchiveMediaHtml: buildArchiveMediaHtml,
    buildArchiveModalInnerHtml: buildArchiveModalInnerHtml,
    entryTitleFromTags: entryTitleFromTags,
  };
})(window);
