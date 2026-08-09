#!/usr/bin/env python3
"""
migrate.py — one-time converter from the old single-car races.json
into the new multi-car, per-season data layout.

  data/races.json  ->  data/index.json
                       data/seasons/<season-id>.json

Run once. After this, use tools/import_race.py to add new events.
"""

import json
import os
import re
import sys
from collections import OrderedDict

TEAM_NAMES = ["Furred and Feathers Racing", "Furry Temptations Racing", "FAF Racing"]

# Old `season` value  ->  (season id, canonical season, short label, series, kind)
SEASON_MAP = {
    "GT Endurance Series by Simucube - 2026 Season 2": (
        "2026-s2-gt-endurance",
        "GT Endurance Series by Simucube - 2026 Season 2",
        "2026 Season 2",
        "GT Endurance Series by Simucube",
        "championship",
    ),
    "Global Endurance Tour - 2026 Season 3": (
        "2026-s3-global-endurance-tour",
        "Global Endurance Tour - 2026 Season 3",
        "2026 Season 3",
        "Global Endurance Tour",
        "championship",
    ),
    "2026 6 Hours of the Glen Powered by VCO": (
        "2026-special-events",
        "2026 Special Events",
        "2026 Specials",
        "Special Races",
        "special",
    ),
    "2026 6 Hours of Road America": (
        "2026-special-events",
        "2026 Special Events",
        "2026 Specials",
        "Special Races",
        "special",
    ),
}


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "unknown"


def find_our_row(race):
    """Locate our car in the classification array."""
    car_num = str(race.get("ftCarNum", ""))
    for row in race.get("results", []):
        if row.get("team") in TEAM_NAMES and str(row.get("carNum")) == car_num:
            return row
    for row in race.get("results", []):
        if row.get("team") in TEAM_NAMES:
            return row
    return None


def convert(race):
    """Old race object -> new event object with one session and one entry."""
    old_season = race.get("season")
    if old_season not in SEASON_MAP:
        raise SystemExit("Unmapped season: %r (race %s)" % (old_season, race.get("id")))
    season_id, season, season_short, series, kind = SEASON_MAP[old_season]

    row = find_our_row(race)
    if row is None:
        raise SystemExit("Could not find our car in race %s" % race.get("id"))

    session = OrderedDict()
    session["key"] = "split-%s" % race.get("split", 1)
    session["split"] = race.get("split")
    session["totalSplits"] = race.get("totalSplits")
    session["sof"] = race.get("sof")
    session["numTeams"] = race.get("numTeams")
    session["numDrivers"] = race.get("numDrivers")
    session["laps"] = race.get("laps")
    session["leadChanges"] = race.get("leadChanges")
    session["eventBestLap"] = race.get("eventBestLap")
    session["startTime"] = race.get("startTime")
    session["endTime"] = race.get("endTime")
    session["temp"] = race.get("temp")
    session["multiclass"] = bool(race.get("multiclass"))
    if race.get("classes"):
        session["classes"] = race["classes"]
    session["results"] = race.get("results", [])

    entry = OrderedDict()
    entry["carNum"] = str(race.get("ftCarNum"))
    entry["session"] = 0
    entry["car"] = race.get("ftCar")
    entry["teamName"] = row.get("team")
    entry["pos"] = race.get("ftPos")
    entry["startPos"] = race.get("ftStartPos")
    entry["gained"] = race.get("ftGained")
    entry["laps"] = race.get("ftLaps")
    entry["bestLap"] = race.get("ftBestLap")
    entry["avgLap"] = row.get("avgLap")
    entry["incidents"] = race.get("ftIncidents")
    entry["champPts"] = race.get("ftChampPts")
    entry["interval"] = row.get("interval")
    entry["lapsLead"] = row.get("lapsLead", 0)
    entry["reasonOut"] = row.get("reasonOut", "Running")
    if race.get("ftClass"):
        entry["carClass"] = race.get("ftClass")
        entry["posInClass"] = race.get("ftPosInClass")
        entry["startPosInClass"] = race.get("ftStartPosInClass")
        entry["gainedInClass"] = race.get("ftGainedInClass")
        entry["classInterval"] = row.get("classInterval")
    entry["drivers"] = race.get("ftDrivers", [])

    event = OrderedDict()
    event["id"] = race.get("id")
    event["date"] = race.get("date")
    event["track"] = race.get("track")
    event["config"] = race.get("config")
    event["series"] = series
    event["season"] = season
    event["seasonShort"] = season_short
    event["seasonId"] = season_id
    if kind == "special":
        event["eventName"] = old_season
    event["sessions"] = [session]
    event["entries"] = [entry]
    return event, (season_id, season, season_short, series, kind)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "data/races.json"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "data"

    with open(src, "r", encoding="utf-8") as f:
        races = json.load(f)

    buckets = OrderedDict()
    meta = {}
    for race in races:
        event, info = convert(race)
        season_id = info[0]
        buckets.setdefault(season_id, []).append(event)
        meta[season_id] = info

    os.makedirs(os.path.join(out_dir, "seasons"), exist_ok=True)

    seasons_index = []
    for season_id, events in buckets.items():
        events.sort(key=lambda e: e["date"])
        path = os.path.join(out_dir, "seasons", season_id + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=1)

        _, season, season_short, series, kind = meta[season_id]
        cars = sorted({en["carNum"] for e in events for en in e["entries"]})
        seasons_index.append(
            OrderedDict(
                [
                    ("id", season_id),
                    ("season", season),
                    ("seasonShort", season_short),
                    ("series", series),
                    ("kind", kind),
                    ("year", int(events[0]["date"][:4])),
                    ("file", "seasons/%s.json" % season_id),
                    ("events", len(events)),
                    ("cars", cars),
                    ("firstDate", events[0]["date"]),
                    ("lastDate", events[-1]["date"]),
                ]
            )
        )
        print("  %-32s %2d events  %6.1f KB  cars=%s"
              % (season_id, len(events), os.path.getsize(path) / 1024, ",".join(cars)))

    seasons_index.sort(key=lambda s: s["lastDate"], reverse=True)

    index = OrderedDict(
        [
            (
                "team",
                OrderedDict(
                    [
                        ("name", "Furred and Feathers Racing"),
                        ("short", "FAF Racing"),
                        ("aliases", TEAM_NAMES),
                    ]
                ),
            ),
            (
                "cars",
                [
                    OrderedDict([("num", "337"), ("name", "Furred"), ("accent", "fur")]),
                    OrderedDict([("num", "338"), ("name", "Feathers"), ("accent", "feather")]),
                ],
            ),
            ("schedule", "schedule.json"),
            ("seasons", seasons_index),
        ]
    )
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print("\nWrote %s/index.json with %d seasons." % (out_dir, len(seasons_index)))


if __name__ == "__main__":
    main()
