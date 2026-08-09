#!/usr/bin/env python3
"""
import_race.py — add one race weekend to the site data.

A round is one event. If both cars land in the same split you have one
iRacing export; if they get drawn into different splits you have two.
Either way it becomes a single event with one session per split and one
entry per car.

Split number, total splits, season and event id are all read straight
out of the export. Usually you just point it at the files.

  # both cars in the same split
  python tools/import_race.py --session eventresult-87810489.json

  # cars split up — one export per split
  python tools/import_race.py \
      --session eventresult-87810488.json \
      --session eventresult-87810489.json

Options
  --season ID       season id from data/index.json; auto-detected from
                    the export's season name when omitted
  --session SPEC    path[:split[:totalSplits]], repeat once per split.
                    The :split:total part is only needed when the export
                    has no session_splits list.
  --id SLUG         override the generated event id
  --event-name TEXT label for one-off races, e.g. "6 Hours of the Glen"
  --data DIR        data folder (default: data)
  --dry-run         print what would be written and stop
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ALIASES = [
    "Furred and Feathers Racing",
    "Furry Temptations Racing",
    "FAF Racing",
]


# ── helpers ──────────────────────────────────────────────────────────

def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s or "event"


def team_aliases(data_dir):
    """Read the team aliases out of js/config.js so there's one source."""
    cfg = os.path.join(os.path.dirname(data_dir.rstrip("/")), "js", "config.js")
    try:
        text = open(cfg, "r", encoding="utf-8").read()
        block = re.search(r"teamAliases\s*:\s*\[(.*?)\]", text, re.S)
        if block:
            names = re.findall(r"'([^']+)'|\"([^\"]+)\"", block.group(1))
            found = [a or b for a, b in names]
            if found:
                return found
    except Exception:
        pass
    return DEFAULT_ALIASES


def unwrap(payload):
    """iRacing exports wrap the real payload in {"type":..., "data":{...}}."""
    if isinstance(payload, dict) and "data" in payload and "session_results" not in payload:
        return payload["data"]
    return payload


def detect_split(payload):
    """Work out which split this is from the session_splits list.

    iRacing orders the splits by strength of field, top split first, so
    the position of our subsession in that list is the split number.
    Returns (split, total) or (None, None) if the export doesn't say.
    """
    splits = payload.get("session_splits") or []
    me = payload.get("subsession_id")
    ids = [s.get("subsession_id") for s in splits]
    if me in ids:
        return ids.index(me) + 1, len(ids)
    return (None, len(ids) or None)


def car_number(row):
    """The car number lives inside the livery object."""
    livery = row.get("livery") or {}
    return str(pick(livery, "car_number", default="") or
               pick(row, "livery_car_number", "car_number", default=""))


def clean_team(name):
    """Strip the ' - 337' style car suffix iRacing team names carry."""
    return re.sub(r"\s*[-–—]\s*#?\d{1,3}\s*$", "", str(name or "")).strip()


def matches_team(name, aliases):
    """Alias match that tolerates the car-number suffix, so a new car
    number works without editing config.js."""
    raw = str(name or "").strip()
    bare = clean_team(raw)
    for a in aliases:
        if raw == a or bare == a or bare == clean_team(a):
            return True
    return False


def race_session(payload):
    """The RACE block inside an iRacing event result export."""
    blocks = payload.get("session_results") or []
    for block in blocks:
        name = str(block.get("simsession_name", "")).upper()
        if name == "RACE" or block.get("simsession_type_name") == "Race":
            return block
    return blocks[-1] if blocks else {}


def pick(d, *keys, **kw):
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return kw.get("default")


# ── conversion ───────────────────────────────────────────────────────

def build_session(payload, split, total_splits, aliases):
    block = race_session(payload)
    rows = block.get("results") or []

    classes = []
    for c in payload.get("car_classes") or []:
        classes.append(OrderedDict([
            ("shortName", c.get("short_name") or c.get("name")),
            ("name", c.get("name")),
            ("numEntries", c.get("num_entries")),
        ]))
    multiclass = len(classes) > 1

    results = []
    for r in rows:
        row = OrderedDict()
        row["pos"] = (r.get("finish_position") or 0) + 1
        row["startPos"] = (r.get("starting_position") or 0) + 1
        row["teamRaw"] = pick(r, "team_name", "display_name", default="")
        row["team"] = clean_team(row["teamRaw"])
        row["car"] = r.get("car_name")
        row["carNum"] = car_number(r)
        row["laps"] = r.get("laps_complete")
        row["bestLap"] = pick(r, "best_lap_time", default=-1)
        row["avgLap"] = pick(r, "average_lap", default=0)
        row["interval"] = pick(r, "interval", default=-1)
        row["incidents"] = r.get("incidents")
        row["reasonOut"] = r.get("reason_out") or "Running"
        row["lapsLead"] = r.get("laps_lead") or 0
        row["champPts"] = r.get("champ_points") or 0
        if multiclass:
            row["carClass"] = r.get("car_class_short_name")
            row["posInClass"] = (r.get("finish_position_in_class") or 0) + 1
            row["startPosInClass"] = (r.get("starting_position_in_class") or 0) + 1
            row["classInterval"] = pick(r, "class_interval", default=-1)
        drivers = []
        for d in r.get("driver_results") or []:
            drivers.append(OrderedDict([
                ("name", d.get("display_name")),
                ("laps", d.get("laps_complete")),
                ("avgLap", pick(d, "average_lap", default=0)),
                ("bestLap", pick(d, "best_lap_time", default=-1)),
                ("incidents", d.get("incidents")),
            ]))
        if not drivers:
            drivers = [OrderedDict([
                ("name", r.get("display_name")),
                ("laps", r.get("laps_complete")),
                ("avgLap", pick(r, "average_lap", default=0)),
                ("bestLap", pick(r, "best_lap_time", default=-1)),
                ("incidents", r.get("incidents")),
            ])]
        row["drivers"] = drivers
        results.append(row)

    results.sort(key=lambda x: x["pos"])

    weather = payload.get("weather") or {}
    session = OrderedDict()
    session["subsessionId"] = payload.get("subsession_id")
    session["split"] = split
    session["totalSplits"] = total_splits
    session["sof"] = payload.get("event_strength_of_field")
    session["numTeams"] = len(results)
    session["numDrivers"] = payload.get("num_drivers") or sum(len(r["drivers"]) for r in results)
    session["laps"] = payload.get("event_laps_complete")
    session["leadChanges"] = payload.get("num_lead_changes") or 0
    session["eventBestLap"] = payload.get("event_best_lap_time") or \
        min([r["bestLap"] for r in results if r["bestLap"] and r["bestLap"] > 0] or [-1])
    session["startTime"] = payload.get("start_time")
    session["endTime"] = payload.get("end_time")
    session["temp"] = weather.get("temp_value")
    session["multiclass"] = multiclass
    if classes:
        session["classes"] = classes
    session["results"] = results

    ours = [r for r in results if matches_team(r.get("teamRaw"), aliases)]
    for r in results:
        r.pop("teamRaw", None)
    return session, ours


def build_entry(row, session_index, multiclass):
    entry = OrderedDict()
    entry["carNum"] = row["carNum"]
    entry["session"] = session_index
    entry["car"] = row["car"]
    entry["teamName"] = row["team"]
    entry["pos"] = row["pos"]
    entry["startPos"] = row["startPos"]
    entry["gained"] = row["startPos"] - row["pos"]
    entry["laps"] = row["laps"]
    entry["bestLap"] = row["bestLap"]
    entry["avgLap"] = row["avgLap"]
    entry["incidents"] = row["incidents"]
    entry["champPts"] = row["champPts"]
    entry["interval"] = row["interval"]
    entry["lapsLead"] = row["lapsLead"]
    entry["reasonOut"] = row["reasonOut"]
    if multiclass and row.get("carClass"):
        entry["carClass"] = row["carClass"]
        entry["posInClass"] = row["posInClass"]
        entry["startPosInClass"] = row["startPosInClass"]
        entry["gainedInClass"] = row["startPosInClass"] - row["posInClass"]
        entry["classInterval"] = row.get("classInterval")
    entry["drivers"] = row["drivers"]
    return entry


# ── main ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Add a race to the FAF Racing site data.")
    ap.add_argument("--season", help="season id from data/index.json; auto-detected from the export when omitted")
    ap.add_argument("--session", action="append", required=True,
                    metavar="PATH[:SPLIT[:TOTAL]]", help="one iRacing export per split")
    ap.add_argument("--id", help="override the generated event id")
    ap.add_argument("--event-name", help="label for one-off races")
    ap.add_argument("--data", default="data", help="data folder (default: data)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    aliases = team_aliases(args.data)

    index_path = os.path.join(args.data, "index.json")
    if not os.path.exists(index_path):
        sys.exit("No %s — run tools/migrate.py first." % index_path)
    index = json.load(open(index_path, "r", encoding="utf-8"))

    sessions, entries, payloads = [], [], []
    for spec in args.session:
        parts = spec.split(":")
        path = parts[0]
        split = int(parts[1]) if len(parts) > 1 and parts[1] else None
        total = int(parts[2]) if len(parts) > 2 and parts[2] else None
        if not os.path.exists(path):
            sys.exit("Missing file: %s" % path)

        payload = unwrap(json.load(open(path, "r", encoding="utf-8")))
        payloads.append(payload)

        # The export usually knows its own split. Anything given on the
        # command line wins.
        auto_split, auto_total = detect_split(payload)
        if split is None:
            split = auto_split
        if total is None:
            total = auto_total
        if split is None:
            print("  ! %s doesn't say which split it is — add :SPLIT:TOTAL to the "
                  "--session value." % os.path.basename(path))

        session, ours = build_session(payload, split, total, aliases)
        idx = len(sessions)
        sessions.append(session)

        if not ours:
            names = sorted({r["team"] for r in session["results"]})
            print("  ! No FAF car found in %s." % os.path.basename(path))
            print("    Teams in this split: %s" % ", ".join(names[:8]))
            print("    Check teamAliases in js/config.js.")
        for row in ours:
            entries.append(build_entry(row, idx, session["multiclass"]))
            print("  + #%s  P%s from P%s  (split %s of %s)"
                  % (row["carNum"], row["pos"], row["startPos"], split, total))

    head = payloads[0]

    # Season: use --season if given, otherwise match the export's own
    # season name against the manifest.
    season_meta = None
    if args.season:
        season_meta = next((s for s in index["seasons"] if s["id"] == args.season), None)
        if season_meta is None:
            sys.exit("Unknown season %r. Known: %s"
                     % (args.season, ", ".join(s["id"] for s in index["seasons"])))
    else:
        want = head.get("season_name")
        season_meta = next((s for s in index["seasons"] if s.get("season") == want), None)
        if season_meta is None:
            sys.exit("Couldn't match season %r from the export. Pass --season with one of: %s"
                     % (want, ", ".join(s["id"] for s in index["seasons"])))
        print("  season: %s (matched %r)" % (season_meta["id"], want))

    if not entries:
        sys.exit("No FAF cars found in any file. Check the team name aliases in js/config.js.")

    track = (head.get("track") or {}).get("track_name") or "Unknown Track"
    config = (head.get("track") or {}).get("config_name") or ""
    date = str(head.get("start_time") or "")[:10]

    event = OrderedDict()
    if args.id:
        event["id"] = args.id
    elif head.get("season_year") and head.get("season_quarter") is not None:
        event["id"] = "%s-%s-s%s-r%s" % (slugify(track), head["season_year"],
                                         head["season_quarter"],
                                         (head.get("race_week_num") or 0) + 1)
    else:
        event["id"] = "%s-%s" % (slugify(track), slugify(season_meta["id"]))
    event["date"] = date
    event["track"] = track
    event["config"] = config
    event["series"] = season_meta["series"]
    event["season"] = season_meta["season"]
    event["seasonShort"] = season_meta["seasonShort"]
    event["seasonId"] = season_meta["id"]
    if args.event_name:
        event["eventName"] = args.event_name
    event["sessions"] = sessions
    event["entries"] = entries

    season_file = os.path.join(args.data, season_meta["file"])
    events = json.load(open(season_file, "r", encoding="utf-8")) if os.path.exists(season_file) else []

    if any(e["id"] == event["id"] for e in events):
        print("  ! %s already exists — replacing it." % event["id"])
        events = [e for e in events if e["id"] != event["id"]]
    events.append(event)
    events.sort(key=lambda e: e["date"])

    print("\n%s — %s, %d split%s, %d car%s"
          % (event["id"], date, len(sessions), "" if len(sessions) == 1 else "s",
             len(entries), "" if len(entries) == 1 else "s"))

    if args.dry_run:
        print("Dry run — nothing written.")
        return

    with open(season_file, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)

    season_meta["events"] = len(events)
    season_meta["firstDate"] = events[0]["date"]
    season_meta["lastDate"] = events[-1]["date"]
    season_meta["cars"] = sorted({en["carNum"] for e in events for en in e["entries"]})
    index["seasons"].sort(key=lambda s: s["lastDate"], reverse=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print("Wrote %s and updated index.json." % season_file)
    print("Commit and push, and the site picks it up within a few minutes.")


if __name__ == "__main__":
    main()
