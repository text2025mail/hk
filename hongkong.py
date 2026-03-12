import requests
import re
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

URL = "https://www.cinema.com.hk/en/movie/ticketing"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

print("Fetching Hong Kong ticketing page...")

# ---------------- FETCH PAGE ---------------- #

def fetch_page():

    r = requests.get(URL, headers=HEADERS)
    return r.text


# ---------------- EXTRACT NEXTJS CHUNKS ---------------- #

def extract_chunks(html):

    chunks = []

    for m in re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.S):

        parts = m.split(",",1)

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


# ---------------- PARSE SHOWS ---------------- #

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

                "venue":"Cinema.com.hk",
                "movie":movie,

                "date":date,
                "time":time,

                # IMPORTANT FIX
                "perfIx":show_id,

                "total":seats,
                "available":seats - sold,
                "blocked":0,

                "sold":sold,

                "gross":sold * price,
                "gross_with_tax":sold * price,

                "per_ticket":{
                    "net":price,
                    "tax":0,
                    "fee":0,
                    "grand":price
                }

            })

    return shows


# ---------------- SAVE MULTI-DATE DATA ---------------- #

def save_results(data):

    out_dir = "HongKong Data"
    os.makedirs(out_dir, exist_ok=True)

    grouped = {}

    for d in data:

        date = d["date"]

        if date not in grouped:
            grouped[date] = []

        grouped[date].append(d)


    for date, shows in grouped.items():

        out_file = os.path.join(out_dir, f"{date}_json.json")
        log_file = os.path.join(out_dir, f"{date}_logs.json")

        if os.path.exists(out_file):

            with open(out_file) as f:
                old = json.load(f)

        else:
            old = []


        index = {(x["venue"],x["movie"],x["perfIx"],x["date"],x["time"]):x for x in old}

        for s in shows:

            key = (s["venue"],s["movie"],s["perfIx"],s["date"],s["time"])
            index[key] = s


        merged = list(index.values())

        with open(out_file,"w") as f:
            json.dump(merged,f,indent=2)


        total_gross = sum(x["gross"] for x in merged)
        sold = sum(x["sold"] for x in merged)
        capacity = sum(x["total"] for x in merged)

        log = {

            "time":datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %I:%M:%S %p"),
            "date":date,

            "total_gross_hkd":round(total_gross,2),
            "total_shows":len(merged),

            "avg_occupancy":round((sold/capacity)*100 if capacity else 0,2),

            "tickets_sold":sold,
            "unique_movies":len(set(x["movie"] for x in merged))

        }


        if os.path.exists(log_file):

            with open(log_file) as f:
                logs = json.load(f)

        else:
            logs = []


        logs.append(log)

        with open(log_file,"w") as f:
            json.dump(logs,f,indent=2)


        print("Saved:", out_file)


# ---------------- GENERATE BFILMY DASHBOARD ---------------- #

def generate_dashboard(data):

    movies = {}

    for d in data:

        movie = d["movie"]
        date = d["date"]

        if movie not in movies:

            movies[movie] = {
                "shows":0,
                "seats":0,
                "sold":0,
                "gross":0,
                "dates":defaultdict(lambda:{
                    "shows":0,
                    "seats":0,
                    "sold":0,
                    "gross":0
                })
            }

        movies[movie]["shows"] += 1
        movies[movie]["seats"] += d["total"]
        movies[movie]["sold"] += d["sold"]
        movies[movie]["gross"] += d["gross"]

        x = movies[movie]["dates"][date]

        x["shows"] += 1
        x["seats"] += d["total"]
        x["sold"] += d["sold"]
        x["gross"] += d["gross"]


    totalShows = sum(v["shows"] for v in movies.values())
    totalSeats = sum(v["seats"] for v in movies.values())
    totalSold = sum(v["sold"] for v in movies.values())
    totalGross = sum(v["gross"] for v in movies.values())

    avgOcc = round(totalSold/totalSeats*100,2)

    last_updated = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y • %H:%M IST")

    rows = ""

    for i,(movie,v) in enumerate(sorted(movies.items(),key=lambda x:x[1]["gross"],reverse=True)):

        occ = round(v["sold"]/v["seats"]*100,2)

        occClass="occ-low"
        if occ>=60: occClass="occ-high"
        elif occ>=40: occClass="occ-mid"

        sub=""

        for d,x in sorted(v["dates"].items()):

            o=round(x["sold"]/x["seats"]*100,2)

            sub+=f"""
<tr>
<td>{d}</td>
<td>{x['shows']}</td>
<td>{x['seats']}</td>
<td>{x['sold']}</td>
<td>{o}%</td>
<td>${x['gross']:,} HKD</td>
</tr>
"""

        rows+=f"""

<tr class="movie-row" onclick="toggleRow('s{i}')">
<td style="text-align:left">{movie}</td>
<td>{v['shows']}</td>
<td>{v['seats']}</td>
<td>{v['sold']}</td>
<td class="{occClass}">{occ}%</td>
<td>${v['gross']:,}</td>
</tr>

<tr id="s{i}" class="subtable">
<td colspan="6">

<table class="inner">

<thead>
<tr>
<th>Date</th>
<th>Shows</th>
<th>Seats</th>
<th>Sold</th>
<th>Occ%</th>
<th>Gross</th>
</tr>
</thead>

<tbody>

{sub}

</tbody>

</table>

</td>
</tr>
"""


    rows+=f"""
<tr class="total">
<td>TOTAL</td>
<td>{totalShows}</td>
<td>{totalSeats}</td>
<td>{totalSold}</td>
<td>{avgOcc}%</td>
<td>${totalGross:,}</td>
</tr>
"""


    html=f"""
<!DOCTYPE html>
<html>
<head>

<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">

<style>

body{{font-family:Poppins;background:#f4f6fb;padding:40px}}

.container{{max-width:1100px;margin:auto}}

.title{{font-size:32px;font-weight:800;text-align:center;margin-bottom:20px}}

table{{width:100%;border-collapse:collapse;background:white}}

th,td{{padding:10px;border-bottom:1px solid #eee;text-align:center}}

.movie-row{{cursor:pointer}}

.subtable{{display:none;background:#fafafa}}

.total{{background:#ffecec;font-weight:bold}}

.occ-high{{color:#16a34a}}
.occ-mid{{color:#f59e0b}}
.occ-low{{color:#dc2626}}

</style>

</head>

<body>

<div class="container">

<div class="title">Hong Kong Advance Sales</div>

<table>

<thead>
<tr>
<th>Movie</th>
<th>Shows</th>
<th>Seats</th>
<th>Sold</th>
<th>Occ%</th>
<th>Gross</th>
</tr>
</thead>

<tbody>

{rows}

</tbody>

</table>

</div>

<script>
function toggleRow(id){{
const r=document.getElementById(id);
r.style.display=r.style.display==="table-row"?"none":"table-row";
}}
</script>

</body>
</html>
"""

    open("HongKong.html","w",encoding="utf-8").write(html)

    print("Dashboard saved: HongKong.html")


# ---------------- MAIN ---------------- #

def main():

    html = fetch_page()

    chunks = extract_chunks(html)

    shows = parse_shows(chunks)

    print("Shows scraped:", len(shows))

    save_results(shows)

    generate_dashboard(shows)


if __name__ == "__main__":
    main()
