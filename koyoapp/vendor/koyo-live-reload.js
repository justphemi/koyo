(function () {
  "use strict";
  if (window.__koyoLiveStarted) return;
  window.__koyoLiveStarted = true;

  var RELOAD_URL = "/__koyo-reload";
  var KEY = "koyo-reload-token";
  var POLL_MS = 700;
  var last = sessionStorage.getItem(KEY) || "";

  function snapshotFormState() {
    var map = {};
    var els = document.querySelectorAll("input, textarea, select");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (!el.id) continue;
      map[el.id] = {
        value: el.value,
        checked: el.checked,
        selected: el.options
          ? Array.prototype.filter.call(el.options, function (o) { return o.selected; })
              .map(function (o) { return o.value; })
          : null,
      };
    }
    return map;
  }

  function restoreFormState(map) {
    for (var id in map) {
      var el = document.getElementById(id);
      if (!el) continue;
      var state = map[id];
      if (state.value !== undefined && el.value !== undefined) el.value = state.value;
      if (state.checked !== undefined && el.checked !== undefined) el.checked = state.checked;
      if (el.options && state.selected) {
        for (var i = 0; i < el.options.length; i++) {
          el.options[i].selected = state.selected.indexOf(el.options[i].value) !== -1;
        }
      }
    }
  }

  function refreshStylesheets() {
    var links = document.querySelectorAll('link[rel="stylesheet"]');
    for (var i = 0; i < links.length; i++) {
      var link = links[i];
      var href = link.getAttribute("href") || "";
      if (href.indexOf("?koyo=") === -1) {
        link.setAttribute("href", href + (href.indexOf("?") === -1 ? "?" : "&") + "koyo=" + Date.now());
      }
    }
  }

  function morph(html) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    var newTitle = doc.querySelector("title");
    if (newTitle && newTitle.textContent) document.title = newTitle.textContent;

    var state = snapshotFormState();
    var active = document.activeElement;
    var activeSnap =
      active && active.id
        ? {
            id: active.id,
            value: active.value,
            checked: active.checked,
            start: active.selectionStart,
            end: active.selectionEnd,
          }
        : null;

    morphdom(document.body, doc.body, {
      onBeforeNodeAdded: function (node) {
        if (node.tagName === "SCRIPT") return false;
      },
      onBeforeElUpdated: function (fromEl, toEl) {
        if (fromEl.id === "koyo-reload-script" || fromEl.tagName === "SCRIPT") {
          return false;
        }
        return true;
      },
      onNodeAdded: function (node) {
        if (window.htmx && node.nodeType === 1) {
          try {
            htmx.process(node);
          } catch (e) {
            /* ignore */
          }
        }
      },
    });

    restoreFormState(state);
    if (activeSnap) {
      var el = document.getElementById(activeSnap.id);
      if (el) {
        if (activeSnap.value !== undefined && el.value !== undefined) el.value = activeSnap.value;
        if (activeSnap.checked !== undefined && el.checked !== undefined) el.checked = activeSnap.checked;
        try {
          el.focus();
          if (el.setSelectionRange && activeSnap.start != null) {
            el.setSelectionRange(activeSnap.start, activeSnap.end);
          }
        } catch (e) {
          /* ignore */
        }
      }
    }
    refreshStylesheets();
  }

  function schedulePoll(ms) {
    setTimeout(poll, ms);
  }

  function applyChange() {
    fetch(window.location.href, { headers: { Accept: "text/html" }, cache: "no-store" })
      .then(function (r) {
        return r.text();
      })
      .then(morph)
      .catch(function () {
        schedulePoll(350);
      });
  }

  function poll() {
    fetch(RELOAD_URL + "?since=" + encodeURIComponent(last), { cache: "no-store" })
      .then(function (r) {
        last = r.headers.get("X-Koyo-Token") || last;
        sessionStorage.setItem(KEY, last);
        if (r.status === 200) {
          applyChange();
        } else {
          schedulePoll(POLL_MS);
        }
      })
      .catch(function () {
        schedulePoll(POLL_MS);
      });
  }

  poll();
})();