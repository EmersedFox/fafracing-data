/* ═══════════════════════════════════════════════════════════════
   FAF RACING — DATA LOADER

   Reads data/index.json (the manifest), then pulls only the season
   files a page actually needs. Serves from GitHub when configured,
   falls back to the local data folder if that fails.
   ═══════════════════════════════════════════════════════════════ */

window.FAF = window.FAF || {};

(function (FAF) {
  'use strict';

  var CFG = window.FAF_CONFIG || {};
  var GH = CFG.github || {};

  var manifest = null;
  var seasons = {};        // seasonId -> events array
  var schedule = null;
  var inflight = {};       // de-duplicates concurrent requests

  /* ── URLS ───────────────────────────────────────────────────── */

  function githubConfigured() {
    return !!(GH.owner && GH.repo && GH.owner.indexOf('your-') !== 0);
  }

  function useGithub() {
    if (CFG.source === 'local') return false;
    if (CFG.source === 'github') return true;
    return githubConfigured();
  }

  function githubUrl(file) {
    var base = GH.provider === 'jsdelivr'
      ? 'https://cdn.jsdelivr.net/gh/' + GH.owner + '/' + GH.repo + '@' + (GH.branch || 'main')
      : 'https://raw.githubusercontent.com/' + GH.owner + '/' + GH.repo + '/' + (GH.branch || 'main');
    return base + '/' + (GH.path || 'data') + '/' + file;
  }

  function localUrl(file) {
    return (CFG.localPath || 'data') + '/' + file;
  }

  /* ── CACHE ──────────────────────────────────────────────────── */

  var TTL = (CFG.cacheMinutes || 0) * 60000;

  function cacheGet(file) {
    if (!TTL) return null;
    try {
      var raw = sessionStorage.getItem('faf:' + file);
      if (!raw) return null;
      var box = JSON.parse(raw);
      if (Date.now() - box.t > TTL) return null;
      return box.d;
    } catch (e) { return null; }
  }

  function cacheSet(file, data) {
    if (!TTL) return;
    try {
      sessionStorage.setItem('faf:' + file, JSON.stringify({ t: Date.now(), d: data }));
    } catch (e) { /* quota or private mode — caching is optional */ }
  }

  FAF.clearCache = function () {
    try {
      Object.keys(sessionStorage)
        .filter(function (k) { return k.indexOf('faf:') === 0; })
        .forEach(function (k) { sessionStorage.removeItem(k); });
    } catch (e) {}
    manifest = null; seasons = {}; schedule = null; inflight = {};
  };

  /* ── FETCH ──────────────────────────────────────────────────── */

  function getJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (res) {
      if (!res.ok) throw new Error(res.status + ' ' + url);
      return res.json();
    });
  }

  /* Try GitHub, then local. Whichever answers first wins. */
  function load(file) {
    var hit = cacheGet(file);
    if (hit) return Promise.resolve(hit);
    if (inflight[file]) return inflight[file];

    var chain = useGithub()
      ? getJSON(githubUrl(file)).catch(function (err) {
          if (CFG.source === 'github') throw err;
          FAF.usingFallback = true;
          return getJSON(localUrl(file));
        })
      : getJSON(localUrl(file));

    inflight[file] = chain.then(function (data) {
      cacheSet(file, data);
      delete inflight[file];
      return data;
    }, function (err) {
      delete inflight[file];
      throw err;
    });

    return inflight[file];
  }

  /* ── PUBLIC API ─────────────────────────────────────────────── */

  FAF.loadManifest = function () {
    if (manifest) return Promise.resolve(manifest);
    return load('index.json').then(function (data) {
      manifest = data;
      manifest.seasons = (manifest.seasons || []).slice().sort(function (a, b) {
        return String(b.lastDate).localeCompare(String(a.lastDate));
      });
      return manifest;
    });
  };

  FAF.loadSeason = function (seasonId) {
    if (seasons[seasonId]) return Promise.resolve(seasons[seasonId]);
    return FAF.loadManifest().then(function (m) {
      var meta = m.seasons.filter(function (s) { return s.id === seasonId; })[0];
      if (!meta) throw new Error('Unknown season: ' + seasonId);
      return load(meta.file).then(function (events) {
        events.forEach(function (e) {
          e.seasonId = meta.id;
          e.season = e.season || meta.season;
          e.seasonShort = e.seasonShort || meta.seasonShort;
          e.series = e.series || meta.series;
        });
        events.sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });
        seasons[seasonId] = events;
        return events;
      });
    });
  };

  /* Every season at once. Only used by the standings page. */
  FAF.loadAllSeasons = function () {
    return FAF.loadManifest().then(function (m) {
      return Promise.all(m.seasons.map(function (s) { return FAF.loadSeason(s.id); }));
    });
  };

  FAF.loadSchedule = function () {
    if (schedule) return Promise.resolve(schedule);
    return FAF.loadManifest().then(function (m) {
      return load(m.schedule || 'schedule.json').then(function (data) {
        schedule = data;
        return data;
      });
    });
  };

  /* The season containing the most recent completed event. */
  FAF.latestSeasonId = function () {
    return FAF.loadManifest().then(function (m) {
      return m.seasons.length ? m.seasons[0].id : null;
    });
  };

  /* Find an event by id without knowing which season holds it.
     Checks the manifest date ranges so it usually only downloads
     one file. */
  FAF.findEvent = function (eventId) {
    return FAF.loadManifest().then(function (m) {
      var order = m.seasons.slice();
      function tryNext(i) {
        if (i >= order.length) return null;
        return FAF.loadSeason(order[i].id).then(function (events) {
          var hit = events.filter(function (e) { return e.id === eventId; })[0];
          return hit ? { event: hit, seasonId: order[i].id, events: events } : tryNext(i + 1);
        });
      }
      return tryNext(0);
    });
  };

  FAF.dataOrigin = function () {
    if (!useGithub()) return 'local';
    return FAF.usingFallback ? 'local (GitHub unreachable)' : 'github';
  };

})(window.FAF);
