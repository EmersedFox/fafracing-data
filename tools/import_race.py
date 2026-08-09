#!/usr/bin/env python3
"""
import_race.py — add one race weekend to the site data.

A round is one event. If both cars land in the same split you have one
iRacing export; if they get drawn into different splits you have two.
Either way it becomes a single event with one session per split and one
entry per car.

  # both cars in the same split
  python tools/import_race.py \
      --season 2027-s1-global-endurance-tour \
      --session eventresult-84560263.json:2:5

  # cars split up
  python tools/import_race.py \
      --season 2027-s1-global-endurance-tour \
      --session eventresult-84560263.json:2:5 \
      --session eventresult-84560291.json:5:5

Options
  --season ID       season id from data/index.json (required)
  --session SPEC    path[:split[:totalSplits]], repeat once per split
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
        row["team"] = pick(r, "team_name", "display_name", default="")
        row["car"] = r.get("car_name")
        row["carNum"] = str(pick(r, "livery_car_number", "car_number", default=""))
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
    session["eventBestLap"] = min([r["bestLap"] for r in results if r["bestLap"] and r["bestLap"] > 0] or [-1])
    session["startTime"] = payload.get("start_time")
    session["endTime"] = payload.get("end_time")
    session["temp"] = weather.get("temp_value")
    session["multiclass"] = multiclass
    if classes:
        session["classes"] = classes
    session["results"] = results

    ours = [r for r in results if r["team"] in aliases]
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
    ap.add_argument("--season", required=True, help="season id from data/index.json")
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

    season_meta = next((s for s in index["seasons"] if s["id"] == args.season), None)
    if season_meta is None:
        sys.exit("Unknown season %r. Known: %s"
                 % (args.season, ", ".join(s["id"] for s in index["seasons"])))

    sessions, entries, payloads = [], [], []
    for spec in args.session:
        parts = spec.split(":")
        path = parts[0]
        split = int(parts[1]) if len(parts) > 1 and parts[1] else None
        total = int(parts[2]) if len(parts) > 2 and parts[2] else None
        if not os.path.exists(path):
            sys.exit("Missing file: %s" % path)

        payload = json.load(open(path, "r", encoding="utf-8"))
        payloads.append(payload)
        session, ours = build_session(payload, split, total, aliases)
        idx = len(sessions)
        sessions.append(session)

        if not ours:
            print("  ! No FAF car found in %s — session kept, no entry added." % os.path.basename(path))
        for row in ours:
            entries.append(build_entry(row, idx, session["multiclass"]))
            print("  + #%s  P%s from P%s  (split %s)"
                  % (row["carNum"], row["pos"], row["startPos"], split))

    if not entries:
        sys.exit("No FAF cars found in any file. Check the team name aliases in js/config.js.")

    head = payloads[0]
    track = (head.get("track") or {}).get("track_name") or "Unknown Track"
    config = (head.get("track") or {}).get("config_name") or ""
    date = str(head.get("start_time") or "")[:10]

    event = OrderedDict()
    event["id"] = args.id or "%s-%s" % (slugify(track), slugify(args.season))
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
