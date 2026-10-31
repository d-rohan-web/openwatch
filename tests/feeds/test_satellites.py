import json
from datetime import datetime, timezone
from pathlib import Path

from sgp4.api import jday
from sgp4.propagation import gstime

from apps.collector.feeds.satellites import gmst, load, positions, subpoint

FX = json.loads((Path(__file__).parent.parent / "fixtures" / "satellites.json").read_text())
NOW = datetime.fromtimestamp(1793395723, timezone.utc)  # 2026-10-31 02:48:43Z


def test_satellites():
    jd, fr = jday(2026, 10, 31, 3, 0, 0)
    assert abs(gmst(jd, fr) - gstime(jd + fr)) < 1e-9

    sats, owners = load(FX, FX["satcat"])
    assert [o["OBJECT_NAME"] for g, o, _ in sats if g == "active"] == ["CARTOSAT-3", "IRNSS-1B"]  # US one dropped

    # wheretheiss.at at the same instant said lon -157.210, lat -36.507, alt 431.72 km
    lon, lat, alt = subpoint(next(s for _, o, s in sats if o["NORAD_CAT_ID"] == 25544), NOW)
    assert abs(lon + 157.21) < 0.1 and abs(lat + 36.507) < 0.1 and abs(alt - 431.7) < 2

    recs = {r["title"]: r for r in positions(sats, owners, NOW)}
    assert "ISS (ZARYA)" not in recs  # over the Pacific, outside the region
    assert recs["PRAETORIAN SDA_604"]["kind"] == "military" and "SAR-LUPE 2" not in recs
    nav = recs["IRNSS-1B"]  # IGSO: the 24 h figure-of-eight, sampled every 20 min
    assert nav["kind"] == "navic" and len(nav["geometry"]["coordinates"]) == 73 and nav["attrs"]["track_step_s"] == 1200
    lats = [y for _, y in nav["geometry"]["coordinates"]]
    assert max(lats) > 25 and min(lats) < -25  # swings ~29° north and south of the equator
    c = recs["CARTOSAT-3"]
    assert c["kind"] == "indian" and c["attrs"]["owner"] == "IND" and 450 < c["attrs"]["alt_km"] < 550
    assert c["geometry"]["type"] == "LineString" and len(c["geometry"]["coordinates"]) == 53  # one revolution (~92 min) + 10 min, every 2 min


def test_mission_and_orbit():
    from apps.collector.feeds.satellites import mission, orbit
    assert mission("IRNSS-1I") == "Navigation (NavIC)" and mission("GSAT-7A") == "Strategic communication"
    assert mission("CARTOSAT-3") == "Earth observation" and mission("GSAT-30") == "Communication"
    assert mission("INSAT-3DR") == "Weather & ocean" and mission("FOO") == "Other"
    geo = orbit({"MEAN_MOTION": 1.0027, "ECCENTRICITY": 0.0002, "INCLINATION": 0.05})
    assert geo["orbit"] == "GEO" and 35700 < geo["apogee_km"] < 35900
    assert orbit({"MEAN_MOTION": 1.0027, "ECCENTRICITY": 0.001, "INCLINATION": 29})["orbit"] == "IGSO"
    assert orbit({"MEAN_MOTION": 15.5, "ECCENTRICITY": 0.0005, "INCLINATION": 51.6})["orbit"] == "LEO"
