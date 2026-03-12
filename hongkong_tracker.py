import requests
import re
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

URL = "https://www.cinema.com.hk/en/movie/ticketing"

HEADERS = {"User-Agent": "Mozilla/5.0"}

HK_TZ = ZoneInfo("Asia/Hong_Kong")
IST_TZ = ZoneInfo("Asia/Kolkata")

RUN_TIME = datetime.now(IST_TZ).strftime("%Y-%m-%d %I:%M:%S %p IST")

print("Run Time:", RUN_TIME)


# ---------------------------------------------------
# FETCH PAGE
# ---------------------------------------------------

def fetch_page():
    r = requests.get(URL, headers=HEADERS)
    return r.text


# ---------------------------------------------------
# EXTRACT NEXTJS CHUNKS
# ---------------------------------------------------

def extract_chunks(html):

    chunks = []

    for m in re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.S):

        parts = m.split(",", 1)

        if len(parts) < 2:
            continue

        try:
            s = parts[1].strip()

            if s.startswith('"') and s.endswith('"'):
                decoded = json.loads(s)
                chunks.append(decoded)

        except:
            pass

    return chunks


# ---------------------------------------------------
# PARSE SHOWS
# ---------------------------------------------------

def parse_shows(chunks):

    shows = []

    pattern = re.compile(
        r'"id":(\d+)[\s\S]*?"date":"([^"]+)"[\s\S]*?"time":"([^"]+)"[\s\S]*?"price":(\d+)[\s\S]*?"seats":(\d+)[\s\S]*?"movie":\{[\s\S]*?"name":"([^"]+)"[\s\S]*?"sold":(\d+)',
        re.S
    )

    for chunk in chunks:

        for m in pattern.findall(chunk):

            show_id = int(m[0])
            date = m[1][:10]
            time = m[2][11:16]

            price = int(m[3])
            seats = int(m[4])
            movie = m[5]
            sold = int(m[6])

            shows.append({

                "perfIx": show_id,
                "movie": movie,
                "venue": "Cinema.com.hk",

                "date": date,
                "time": time,

                "total": seats,
                "available": seats - sold,
                "blocked": 0,

                "sold": sold,
                "gross": sold * price,
                "price": price,

                "last_updated": RUN_TIME

            })

    return shows


# ---------------------------------------------------
# SAVE DAILY DATA
# ---------------------------------------------------

def save_daily(shows):

    grouped = defaultdict(list)

    for s in shows:
        grouped[s["date"]].append(s)

    for date, data in grouped.items():

        year = date[:4]
        mmdd = date[5:]

        path = f"Hongkong Data/{year}"
        os.makedirs(path, exist_ok=True)

        file = f"{path}/{mmdd}.json"

        if os.path.exists(file):
            old = json.load(open(file))
        else:
            old = []

        index = {d["perfIx"]: d for d in old}

        for s in data:
            index[s["perfIx"]] = s

        merged = list(index.values())

        json.dump(merged, open(file, "w"), indent=2)

        print("Saved:", file)


# ---------------------------------------------------
# SAVE LOGS
# ---------------------------------------------------

def save_logs(shows):

    grouped = defaultdict(list)

    for s in shows:
        grouped[s["date"]].append(s)

    for date, data in grouped.items():

        year = date[:4]
        mmdd = date[5:]

        path = f"Hongkong Data/{year}"

        log_file = f"{path}/{mmdd}_logs.json"

        total_shows = len(data)
        sold = sum(x["sold"] for x in data)
        capacity = sum(x["total"] for x in data)
        gross = sum(x["gross"] for x in data)

        log = {

            "time": RUN_TIME,
            "date": date,

            "total_shows": total_shows,
            "tickets_sold": sold,
            "total_gross_hkd": gross,

            "avg_occupancy": round((sold / capacity) * 100 if capacity else 0, 2),

            "unique_movies": len(set(x["movie"] for x in data))

        }

        if os.path.exists(log_file):
            logs = json.load(open(log_file))
        else:
            logs = []

        logs.append(log)

        json.dump(logs, open(log_file, "w"), indent=2)

        print("Log updated:", log_file)


# ---------------------------------------------------
# GENERATE MONTHLY SUMMARY (FIXED)
# ---------------------------------------------------

def generate_monthly():

    monthly = defaultdict(lambda: defaultdict(lambda: {

        "shows": 0,
        "seats": 0,
        "sold": 0,
        "gross": 0,

        "dates": defaultdict(lambda: {
            "shows": 0,
            "seats": 0,
            "sold": 0,
            "gross": 0
        })

    }))

    for root, _, files in os.walk("Hongkong Data"):

        for f in files:

            if not f.endswith(".json") or "_logs" in f:
                continue

            data = json.load(open(os.path.join(root, f)))

            for d in data:

                date = d["date"]
                ym = date[:7]   # YYYY-MM

                movie = d["movie"]

                x = monthly[ym][movie]

                x["shows"] += 1
                x["seats"] += d["total"]
                x["sold"] += d["sold"]
                x["gross"] += d["gross"]

                dd = x["dates"][date]

                dd["shows"] += 1
                dd["seats"] += d["total"]
                dd["sold"] += d["sold"]
                dd["gross"] += d["gross"]

    os.makedirs("Hongkong Summary", exist_ok=True)

    for ym, data in monthly.items():

        out = f"Hongkong Summary/{ym}.json"

        json.dump(data, open(out, "w"), indent=2)

        print("Monthly summary:", out)


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

def main():

    html = fetch_page()

    chunks = extract_chunks(html)

    shows = parse_shows(chunks)

    print("Shows scraped:", len(shows))

    save_daily(shows)

    save_logs(shows)

    generate_monthly()


if __name__ == "__main__":
    main()
