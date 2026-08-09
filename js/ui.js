/* ═══════════════════════════════════════════════════════════════
   FAF RACING — SHARED UI
   Navigation, the car switcher, and the lane component that shows
   one car's race in one panel.
   ═══════════════════════════════════════════════════════════════ */

window.FAF = window.FAF || {};

(function (FAF) {
  'use strict';

  var CFG = window.FAF_CONFIG || {};
  var esc = FAF.esc;

  /* ── NAV ────────────────────────────────────────────────────── */

  FAF.initNav = function () {
    var burger = document.querySelector('.burger');
    var links = document.querySelector('.nav-links');
    var scrim = document.querySelector('.scrim');
    var nav = document.querySelector('.nav');

    if (burger && links) {
      var setOpen = function (open) {
        links.classList.toggle('is-open', open);
        burger.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (scrim) scrim.classList.toggle('is-open', open);
        document.body.style.overflow = open ? 'hidden' : '';
      };
      burger.addEventListener('click', function () {
        setOpen(burger.getAttribute('aria-expanded') !== 'true');
      });
      if (scrim) scrim.addEventListener('click', function () { setOpen(false); });
      links.querySelectorAll('a').forEach(function (a) {
        a.addEventListener('click', function () { setOpen(false); });
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') setOpen(false);
      });
    }

    if (nav) {
      var onScroll = function () { nav.classList.toggle('is-scrolled', window.scrollY > 40); };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }
  };

  FAF.initReveal = function (root) {
    var nodes = (root || document).querySelectorAll('.reveal:not(.is-visible)');
    if (!nodes.length) return;
    if (!('IntersectionObserver' in window)) {
      nodes.forEach(function (n) { n.classList.add('is-visible'); });
      return;
    }
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e, i) {
        if (!e.isIntersecting) return;
        setTimeout(function () { e.target.classList.add('is-visible'); }, i * 70);
        obs.unobserve(e.target);
      });
    }, { threshold: 0.1 });
    nodes.forEach(function (n) { obs.observe(n); });
  };

  /* ── CAR SWITCHER ───────────────────────────────────────────────
     Choice is remembered across pages. '' means show both cars. */

  var KEY = 'faf:car';

  FAF.getCarFilter = function () {
    try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; }
  };

  FAF.setCarFilter = function (num) {
    try { localStorage.setItem(KEY, num); } catch (e) {}
  };

  /* Build the switcher from the car numbers actually present in the
     data being shown. Hides itself when there's only ever one car. */
  FAF.initCarSwitch = function (carNums, onChange) {
    var host = document.getElementById('carSwitch');
    if (!host) return '';

    var nums = FAF.sortCarNums(Array.from(new Set(carNums.map(String))));
    if (nums.length < 2) { host.innerHTML = ''; host.hidden = true; return ''; }
    host.hidden = false;

    var current = FAF.getCarFilter();
    if (current && nums.indexOf(current) === -1) current = '';

    function paint() {
      var html = '<button type="button" data-accent="both" data-num="" aria-pressed="' +
        (current === '' ? 'true' : 'false') + '">Both</button>';
      nums.forEach(function (n) {
        html += '<button type="button" data-accent="' + FAF.accent(n) + '" data-num="' + esc(n) +
          '" aria-pressed="' + (current === n ? 'true' : 'false') + '">#' + esc(n) + '</button>';
      });
      host.innerHTML = html;
    }

    paint();
    host.addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      current = btn.getAttribute('data-num');
      FAF.setCarFilter(current);
      paint();
      if (onChange) onChange(current);
    });

    return current;
  };

  /* ── LANE ───────────────────────────────────────────────────────
     One car's race, in one panel: who, which split, start to
     finish, the numbers, and the driver stints. */

  FAF.lane = function (event, entry, opts) {
    opts = opts || {};
    var session = FAF.sessionFor(event, entry);
    var car = FAF.car(entry.carNum);
    var accent = car.accent;
    var gained = entry.gained;
    var mc = FAF.isMulticlass(session);

    var splitText = session && session.split
      ? 'Split <b>' + esc(session.split) + '</b>' +
        (session.totalSplits ? ' of ' + esc(session.totalSplits) : '')
      : 'Single split';
    var sofText = session && session.sof ? ' · SOF <b>' + esc(session.sof) + '</b>' : '';

    var head =
      '<div class="lane-head">' +
        '<div class="lane-id">' +
          '<div class="lane-num data">' + esc(entry.carNum) + '</div>' +
          '<div>' +
            (car.name ? '<div class="lane-name">' + esc(car.name) + '</div>' : '') +
            '<div class="lane-car">' + esc(entry.car || '') + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="split-chip">' + splitText + sofText + '</div>' +
      '</div>';

    var trace =
      '<div class="trace ' + FAF.gainClass(gained) + '">' +
        '<div class="trace-pos trace-from"><span class="label">Started</span>' +
          '<span class="trace-val">P' + esc(entry.startPos) + '</span></div>' +
        '<div class="trace-arrow">' +
          '<div class="trace-bar"></div>' +
          '<div class="trace-delta ' + FAF.gainClass(gained) + '">' + FAF.signed(gained) + '</div>' +
        '</div>' +
        '<div class="trace-pos trace-to"><span class="label">Finished</span>' +
          '<span class="trace-val">P' + esc(entry.pos) + '</span></div>' +
      '</div>';

    var stats = [];
    if (mc && entry.carClass) {
      stats.push(['Class', esc(entry.carClass)]);
      stats.push(['In class', 'P' + esc(entry.posInClass)]);
      stats.push(['Class +/-', FAF.signed(entry.gainedInClass)]);
    }
    stats.push(['Laps', esc(entry.laps)]);
    stats.push(['Best lap', FAF.lapShort(entry.bestLap)]);
    stats.push(['Incidents', esc(entry.incidents) + 'x']);
    if (entry.champPts !== null && entry.champPts !== undefined) stats.push(['Points', esc(entry.champPts)]);
    if (opts.showRaceTime && session) stats.push(['Race time', FAF.raceLength(session.startTime, session.endTime)]);

    var readout = '<div class="readout">' + stats.map(function (s) {
      return '<div><b>' + s[1] + '</b><span>' + s[0] + '</span></div>';
    }).join('') + '</div>';

    var stints = '';
    if (opts.stints !== false && entry.drivers && entry.drivers.length) {
      stints = '<div class="stints">' + entry.drivers.map(function (d) {
        return '<div class="stint">' +
          '<span class="stint-name">' + esc(FAF.driverName(d.name)) + '</span>' +
          '<span class="stint-num"><b>' + esc(d.laps) + '</b> laps · <b>' +
            FAF.lap(d.bestLap) + '</b> best · <b>' + esc(d.incidents) + 'x</b></span>' +
        '</div>';
      }).join('') + '</div>';
    }

    return '<article class="lane reveal" data-accent="' + accent + '" data-car="' + esc(entry.carNum) + '">' +
      head + trace + readout + stints + '</article>';
  };

  /* Render every entry in an event as lanes, honouring the car filter. */
  FAF.lanes = function (event, carFilter, opts) {
    var entries = FAF.entries(event);
    if (carFilter) {
      entries = entries.filter(function (e) { return String(e.carNum) === carFilter; });
    }
    if (!entries.length) return '';
    return '<div class="lanes' + (entries.length === 1 ? ' is-single' : '') + '">' +
      entries.map(function (e) { return FAF.lane(event, e, opts); }).join('') + '</div>';
  };

  /* ── STATES ─────────────────────────────────────────────────── */

  FAF.loadingHTML = function (msg) {
    return '<div class="loading"><i></i><span>' + esc(msg || 'Loading race data') + '</span></div>';
  };

  FAF.emptyHTML = function (title, msg) {
    return '<div class="state"><b>' + esc(title) + '</b>' + esc(msg || '') + '</div>';
  };

  FAF.errorHTML = function (msg) {
    return '<div class="state"><b>Race data didn\'t load</b>' + esc(msg || '') +
      '<button type="button" onclick="FAF.clearCache();location.reload()">Try again</button></div>';
  };

  /* ── BOOT ───────────────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    FAF.initNav();
    var y = document.getElementById('year');
    if (y) y.textContent = new Date().getFullYear();
  });

})(window.FAF);
