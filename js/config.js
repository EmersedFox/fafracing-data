/* ═══════════════════════════════════════════════════════════════
   FAF RACING — DATA SOURCE CONFIG
   This is the only file you need to edit to point the site at
   a different GitHub repo, branch, or folder.
   ═══════════════════════════════════════════════════════════════ */

window.FAF_CONFIG = {

  /* Where race data comes from.
     'auto'   — use GitHub when owner + repo are filled in, fall back
                to the local /data folder if GitHub can't be reached
     'github' — GitHub only
     'local'  — the /data folder next to these pages only            */
  source: 'auto',

  github: {
    owner:  'emersedfox',      // ← your GitHub username or org
    repo:   'fafracing-data',  // ← the repo holding the data folder
    branch: 'main',
    path:   'data',            // folder inside the repo

    /* 'raw'      — raw.githubusercontent.com. Updates go live in about
                    five minutes. Best for race results.
       'jsdelivr' — cdn.jsdelivr.net. Faster worldwide and it serves
                    real JavaScript with the right content type, but a
                    branch reference is cached for up to 12 hours.     */
    provider: 'raw'
  },

  /* Folder used for local data and as the fallback when GitHub fails. */
  localPath: 'data',

  /* Keep downloaded season files in the browser for this many minutes
     so moving between pages doesn't re-download everything.
     Set to 0 to always fetch fresh.                                   */
  cacheMinutes: 10,

  /* Team name as it appears in iRacing results, plus any older names
     still present in archived seasons. Used to find our cars in a
     classification table.

     The trailing car number is stripped before matching, so
     'Furred and Feathers Racing' on its own covers
     '... - 337', '... - 338' and any future car. Only add a new line
     here if the team name itself changes.                             */
  teamAliases: [
    'Furred and Feathers Racing',
    'Furry Temptations Racing',
    'FAF Racing'
  ],

  /* The current two-car line-up. Car numbers not listed here still
     display correctly — they just use the neutral accent colour.      */
  cars: [
    { num: '337', name: 'Furred',   accent: 'fur' },
    { num: '338', name: 'Feathers', accent: 'feather' }
  ],

  /* Shorter labels for long series names, used on pills and badges.   */
  seriesShort: {
    'GT Endurance Series by Simucube': 'GT Endurance',
    'Global Endurance Tour': 'Global Endurance',
    'Special Races': 'Specials'
  },

  /* iRacing name → the name shown on the site.                        */
  driverNames: {
    'Caoimhe Harleman': 'Caoimhe Harleman (Emersed Fox)',
    'Matthew Lutz2': 'Matthew Lutz (Firey Leader)',
    'Gregory Grantham': 'Gregory Grantham (LoneWolf631)'
  }
};
