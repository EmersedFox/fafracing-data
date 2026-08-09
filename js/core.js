/* ═══════════════════════════════════════════════════════════════
   FAF RACING — CORE HELPERS
   Formatting, car identity, and small shared utilities.
   ═══════════════════════════════════════════════════════════════ */

window.FAF = window.FAF || {};

(function (FAF) {
  'use strict';

  var CFG = window.FAF_CONFIG || {};

  /* ── TIME FORMATTING ────────────────────────────────────────────
     iRacing stores lap times in ten-thousandths of a second.        */

  FAF.lap = function (t) {
    if (!t || t < 0) return '—';
    var s = t / 10000;
    return Math.floor(s / 60) + ':' + (s % 60).toFixed(3).padStart(6, '0');
  };

  FAF.lapShort = function (t) {
    if (!t || t < 0) return '—';
    var s = t / 10000;
    return Math.floor(s / 60) + ':' + (s % 60).toFixed(1).padStart(4, '0');
  };

  FAF.interval = function (t) {
    if (t === 0) return 'WINNER';
    if (t === null || t === undefined || t < 0) return '—';
    var s = t / 10000;
    if (s >= 60) return '+' + Math.floor(s / 60) + ':' + (s % 60).toFixed(3).padStart(6, '0');
    return '+' + s.toFixed(3);
  };

  FAF.date = function (ds) {
    return FAF.dateOnly(ds).toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric'
    });
  };

  FAF.dateShort = function (ds) {
    return FAF.dateOnly(ds).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  };

  FAF.dateDay = function (ds) {
    return FAF.dateOnly(ds).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric'
    });
  };

  FAF.dateOnly = function (ds) {
    var p = String(ds || '').split('-');
    return new Date(+p[0], (+p[1] || 1) - 1, +p[2] || 1);
  };

  FAF.today = function () {
    var n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), n.getDate());
  };

  FAF.raceLength = function (start, end) {
    if (!start || !end) return '—';
    var mins = (new Date(end) - new Date(start)) / 60000;
    if (!isFinite(mins) || mins <= 0) return '—';
    return Math.floor(mins / 60) + ':' + String(Math.round(mins % 60)).padStart(2, '0');
  };

  FAF.countdown = function (ds) {
    var days = Math.round((FAF.dateOnly(ds) - FAF.today()) / 86400000);
    if (days < 0) return '';
    if (days === 0) return 'Today';
    if (days === 1) return 'Tomorrow';
    if (days < 7) return 'In ' + days + ' days';
    if (days < 14) return 'In 1 week';
    return 'In ' + Math.floor(days / 7) + ' weeks';
  };

  /* ── TEXT ───────────────────────────────────────────────────── */

  FAF.esc = function (s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };

  FAF.driverName = function (name) {
    return (CFG.driverNames && CFG.driverNames[name]) || name;
  };

  FAF.seriesShort = function (series) {
    return (CFG.seriesShort && CFG.seriesShort[series]) || series;
  };

  FAF.signed = function (n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return (n > 0 ? '+' : '') + n;
  };

  FAF.gainClass = function (n) {
    return n > 0 ? 'is-gain' : n < 0 ? 'is-loss' : 'is-flat';
  };

  /* ── CAR IDENTITY ────────────────────────────────────────────
     Each car number maps to an accent so #337 and #338 stay
     visually distinct everywhere on the site. Numbers that
     aren't in the current line-up use the neutral accent.       */

  var CAR_BY_NUM = {};
  (CFG.cars || []).forEach(function (c) { CAR_BY_NUM[String(c.num)] = c; });

  FAF.car = function (num) {
    var key = String(num);
    return CAR_BY_NUM[key] || { num: key, name: '', accent: 'legacy' };
  };

  FAF.accent = function (num) {
    return FAF.car(num).accent;
  };

  /* Sort so the current line-up leads, lowest number first. */
  FAF.sortCarNums = function (nums) {
    return nums.slice().sort(function (a, b) {
      var ka = CAR_BY_NUM[String(a)] ? 0 : 1;
      var kb = CAR_BY_NUM[String(b)] ? 0 : 1;
      if (ka !== kb) return ka - kb;
      return String(a).localeCompare(String(b), undefined, { numeric: true });
    });
  };

  /* ── EVENT SHAPE ──────────────────────────────────────────────
     An event is one round. It holds one session per split we
     entered, and one entry per car. Two cars in the same split
     both point at the same session index.                        */

  FAF.entries = function (event) {
    return (event && event.entries) || [];
  };

  FAF.entryFor = function (event, carNum) {
    var list = FAF.entries(event);
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].carNum) === String(carNum)) return list[i];
    }
    return null;
  };

  FAF.sessionFor = function (event, entry) {
    if (!event || !entry) return null;
    return (event.sessions || [])[entry.session || 0] || null;
  };

  FAF.carNums = function (event) {
    return FAF.entries(event).map(function (e) { return String(e.carNum); });
  };

  /* True when every car in the event shared one split. */
  FAF.sameSplit = function (event) {
    var list = FAF.entries(event);
    if (list.length < 2) return true;
    var first = list[0].session || 0;
    return list.every(function (e) { return (e.session || 0) === first; });
  };

  /* Sessions that at least one of our cars actually ran in, each
     tagged with the cars that were in it. */
  FAF.usedSessions = function (event) {
    var out = [];
    (event.sessions || []).forEach(function (s, i) {
      var cars = FAF.entries(event)
        .filter(function (e) { return (e.session || 0) === i; })
        .map(function (e) { return String(e.carNum); });
      if (cars.length) out.push({ index: i, session: s, cars: cars });
    });
    return out;
  };

  FAF.isMulticlass = function (session) {
    return !!(session && session.multiclass && session.classes && session.classes.length > 1);
  };

  FAF.classIndex = function (session, className) {
    if (!session || !session.classes) return 0;
    for (var i = 0; i < session.classes.length; i++) {
      if (session.classes[i].shortName === className) return i % 4;
    }
    return 0;
  };

  /* iRacing team names carry the car number as a suffix, e.g.
     "Furred and Feathers Racing - 337". Strip it so the table shows a
     clean name and a new car number works without a config edit. */
  FAF.cleanTeam = function (name) {
    return String(name || '').replace(/\s*[-–—]\s*#?\d{1,3}\s*$/, '').trim();
  };

  function isOurTeam(name) {
    var aliases = CFG.teamAliases || [];
    var raw = String(name || '').trim();
    var bare = FAF.cleanTeam(raw);
    for (var i = 0; i < aliases.length; i++) {
      if (raw === aliases[i] || bare === aliases[i] || bare === FAF.cleanTeam(aliases[i])) return true;
    }
    return false;
  }

  /* Is this classification row one of ours? Returns the car number
     if so, otherwise null. Matches on car number first because two
     FAF cars in one split share a team name. */
  FAF.ourRow = function (event, session, row) {
    if (!isOurTeam(row.team)) return null;
    var nums = FAF.entries(event)
      .filter(function (e) { return FAF.sessionFor(event, e) === session; })
      .map(function (e) { return String(e.carNum); });
    var num = String(row.carNum);
    return nums.indexOf(num) !== -1 ? num : (nums.length === 1 ? nums[0] : null);
  };

  /* ── SCHEDULE ────────────────────────────────────────────────── */

  FAF.flattenSchedule = function (seasons) {
    var out = [];
    (seasons || []).forEach(function (s) {
      (s.rounds || []).forEach(function (r) {
        out.push({
          round: r.round, date: r.date, track: r.track, config: r.config,
          time: r.time, raceId: r.raceId, length: r.length,
          confirmed: r.confirmed, cars: r.cars || null,
          series: r.series || s.series,
          season: s.season, seasonShort: s.seasonShort
        });
      });
    });
    return out;
  };

  FAF.roundStatus = function (round) {
    if (round.raceId) return 'completed';
    return FAF.dateOnly(round.date) < FAF.today() ? 'completed' : 'upcoming';
  };

  FAF.nextRound = function (seasons) {
    var today = FAF.today();
    var upcoming = FAF.flattenSchedule(seasons).filter(function (r) {
      return FAF.dateOnly(r.date) >= today;
    });
    upcoming.sort(function (a, b) { return FAF.dateOnly(a.date) - FAF.dateOnly(b.date); });
    return upcoming[0] || null;
  };

})(window.FAF);
