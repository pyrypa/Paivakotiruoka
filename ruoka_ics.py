#!/usr/bin/env python3
"""Hakee Helsingin paivakotiruokalistan Aromi-rajapinnasta ja kirjoittaa ruoka.ics."""

import json
import urllib.request
from datetime import date, datetime, timedelta, timezone

# --- Asetukset ---------------------------------------------------------------

RESTAURANT_ID = "d0b180f3-9496-4d03-a59e-b485573ad054"  # paivakoti
DAYS_BACK = 7
DAYS_AHEAD = 60
OUTPUT = "ruoka.ics"
CALENDAR_NAME = "Paivakodin ruoka"

# Otsikkoon nostettava ateria. Muut menevat kuvaukseen.
HEADLINE_MEAL = "Lounas"

BASE = "https://aromi.hel.fi/AromieMenus/FI/Default/PALKE/PKeMenu/api/Common/Restaurant/RestaurantMeals"

PAYLOAD = {
    "Id": "b1f23081-2bdf-43e7-a8c7-0f1803db1833",
    "DinerGroupId": "7c7f4abb-5459-48bc-b211-72573511a250",
    "NutrientGroupId": "0ea0ee0d-22c9-4e49-8a7b-8de201ddaf84",
    "DietGroupId": "0943dc9b-5775-4fd2-b319-571cefb15fd5",
    "FilterDietGroupId": None,
    "DietId": None,
    "ConceptId": "ce1f12ed-e8e7-42f1-a365-ffc69477534d",
    "Name": "Päiväkoti ",
    "Code": "PK",
    "RestaurantId": RESTAURANT_ID,
    "UniqueCode": "PK",
    "IndexNumber": 11,
    "NameOrCode": "Päiväkoti ",
    "WeekDays": ["1", "2", "3", "4", "5"],
    "WeekDay0": False,
    "WeekDay1": True,
    "WeekDay2": True,
    "WeekDay3": True,
    "WeekDay4": True,
    "WeekDay5": True,
    "WeekDay6": False,
    "DietType": None,
    "IsActiveSuitability": False,
    "SuitabilityDietIds": [],
}


# --- Haku --------------------------------------------------------------------


def fetch(start: date, end: date) -> list:
    url = (
        f"{BASE}?Id={RESTAURANT_ID}"
        f"&StartDate={start.isoformat()}T00:00:00.000Z"
        f"&EndDate={end.isoformat()}T00:00:00.000Z"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(PAYLOAD).encode("utf-8"),
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "ruoka-ics/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


# --- Jasennys ----------------------------------------------------------------


def parse_day(entry: dict):
    """Palauttaa (date, {ateria: [ruoat]}) tai None jos paiva on tyhja."""
    try:
        day = datetime.fromisoformat(entry["Date"]).date()
    except (KeyError, ValueError):
        return None

    meals = {}
    for meal in entry.get("Meals") or []:
        name = (meal.get("MealName") or "").strip()
        dishes = [
            (d.get("DishName") or "").strip()
            for d in (meal.get("Dishes") or [])
            if (d.get("DishName") or "").strip()
        ]
        if name and dishes:
            meals[name] = dishes

    return (day, meals) if meals else None


def summary_for(meals: dict) -> str:
    for name, dishes in meals.items():
        if name.lower().startswith(HEADLINE_MEAL.lower()):
            return ", ".join(dishes)
    # Ei lounasta -> kaytetaan ensimmaista ateriaa
    first = next(iter(meals.values()))
    return ", ".join(first)


def description_for(meals: dict) -> str:
    return "\n".join(f"{name}: {', '.join(dishes)}" for name, dishes in meals.items())


# --- ICS ---------------------------------------------------------------------


def esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """RFC 5545 rivinkatkaisu 75 oktettiin."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, chunk = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74
        if len(chunk) + len(b) > limit:
            out.append(chunk.decode("utf-8"))
            chunk = b
        else:
            chunk += b
    out.append(chunk.decode("utf-8"))
    return "\r\n ".join(out)


def build_ics(days: list) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ruoka-ics//FI",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(CALENDAR_NAME)}",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for day, meals in days:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{day.isoformat()}-paivakotiruoka@aromi.hel.fi",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            "TRANSP:TRANSPARENT",
            f"SUMMARY:{esc(summary_for(meals))}",
            f"DESCRIPTION:{esc(description_for(meals))}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


# --- Main --------------------------------------------------------------------


def main():
    today = date.today()
    data = fetch(today - timedelta(days=DAYS_BACK), today + timedelta(days=DAYS_AHEAD))

    days = [parsed for entry in data if (parsed := parse_day(entry))]
    days.sort(key=lambda d: d[0])

    if not days:
        raise SystemExit("Rajapinta palautti nolla paivaa - ei kirjoiteta tyhjaa .ics")

    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        f.write(build_ics(days))

    print(f"{OUTPUT}: {len(days)} paivaa ({days[0][0]} - {days[-1][0]})")


if __name__ == "__main__":
    main()
