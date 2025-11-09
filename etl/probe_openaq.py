import os, datetime as dt
from etl.sources.openaq import get_locations_near, get_sensors_for_location, get_hours

CITY = ("Bucharest", 44.4268, 26.1025)
RADIUS = int(os.getenv("OPENAQ_RADIUS_M", "20000"))

def main():
    city, lat, lon = CITY
    locs = get_locations_near(lat, lon, radius_m=RADIUS, limit=40)
    print(f"[probe] locations near {city}: {len(locs)}")

    if not locs:
        print("[probe] 0 локаций — проверь OPENAQ_API_KEY и радиус.")
        return

    now = dt.datetime.now(dt.timezone.utc)
    frm = now - dt.timedelta(days=365)

    total_sensors = 0
    sensors_with_hours = 0

    for loc in locs[:10]:
        loc_id = loc.get("id")
        sensors = get_sensors_for_location(loc_id)
        total_sensors += len(sensors)
        for s in sensors[:20]:
            sid = s.get("id")
            p = (s.get("parameter") or {}).get("name")
            rows = get_hours(sid, frm, now, per_page=50, max_pages=1)
            if rows:
                sensors_with_hours += 1
            print(f"  sensor {sid} param={p} hours_page1={len(rows)}")

    print(f"[probe] sensors total={total_sensors}, with_hours>0={sensors_with_hours}")

if __name__ == "__main__":
    main()
