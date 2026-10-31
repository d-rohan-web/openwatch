"""Current weather for state/UT capitals and metros from Open-Meteo, one batched request."""
from __future__ import annotations

from apps.collector.feed import Feed
from packages.contracts.record import record

# name, state/UT, lat, lon
CITIES = [
    ("Delhi", "Delhi", 28.61, 77.21), ("Mumbai", "Maharashtra", 19.08, 72.88), ("Kolkata", "West Bengal", 22.57, 88.36),
    ("Chennai", "Tamil Nadu", 13.08, 80.27), ("Bengaluru", "Karnataka", 12.97, 77.59), ("Hyderabad", "Telangana", 17.39, 78.49),
    ("Ahmedabad", "Gujarat", 23.02, 72.57), ("Pune", "Maharashtra", 18.52, 73.86), ("Surat", "Gujarat", 21.17, 72.83),
    ("Kanpur", "Uttar Pradesh", 26.45, 80.33), ("Nagpur", "Maharashtra", 21.15, 79.09), ("Visakhapatnam", "Andhra Pradesh", 17.69, 83.22),
    ("Kochi", "Kerala", 9.93, 76.27), ("Amaravati", "Andhra Pradesh", 16.51, 80.52), ("Itanagar", "Arunachal Pradesh", 27.08, 93.61),
    ("Dispur", "Assam", 26.14, 91.79), ("Patna", "Bihar", 25.59, 85.14), ("Raipur", "Chhattisgarh", 21.25, 81.63),
    ("Panaji", "Goa", 15.50, 73.83), ("Gandhinagar", "Gujarat", 23.22, 72.65), ("Chandigarh", "Chandigarh", 30.73, 76.78),
    ("Shimla", "Himachal Pradesh", 31.10, 77.17), ("Ranchi", "Jharkhand", 23.34, 85.31), ("Thiruvananthapuram", "Kerala", 8.52, 76.94),
    ("Bhopal", "Madhya Pradesh", 23.26, 77.41), ("Imphal", "Manipur", 24.82, 93.94), ("Shillong", "Meghalaya", 25.58, 91.89),
    ("Aizawl", "Mizoram", 23.73, 92.72), ("Kohima", "Nagaland", 25.67, 94.11), ("Bhubaneswar", "Odisha", 20.30, 85.82),
    ("Jaipur", "Rajasthan", 26.91, 75.79), ("Gangtok", "Sikkim", 27.33, 88.61), ("Agartala", "Tripura", 23.83, 91.29),
    ("Lucknow", "Uttar Pradesh", 26.85, 80.95), ("Dehradun", "Uttarakhand", 30.32, 78.03), ("Srinagar", "Jammu and Kashmir", 34.08, 74.80),
    ("Jammu", "Jammu and Kashmir", 32.73, 74.86), ("Leh", "Ladakh", 34.16, 77.58), ("Puducherry", "Puducherry", 11.94, 79.81),
    ("Port Blair", "Andaman and Nicobar Islands", 11.62, 92.73), ("Kavaratti", "Lakshadweep", 10.57, 72.64),
    ("Daman", "Dadra and Nagar Haveli and Daman and Diu", 20.40, 72.83),
]
VARS = "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,weather_code"
URL = ("https://api.open-meteo.com/v1/forecast?timezone=GMT&current=" + VARS
       + "&latitude=" + ",".join(str(c[2]) for c in CITIES) + "&longitude=" + ",".join(str(c[3]) for c in CITIES))

WMO = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
       61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
       71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Light showers", 81: "Showers",
       82: "Violent showers", 85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
       96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"}


def severity(apparent: float | None, temp: float | None, rate_mm_h: float) -> str:
    if (apparent or 0) >= 45 or rate_mm_h >= 20:
        return "warning"
    if (apparent or 0) >= 40 or (temp is not None and temp <= 2):
        return "advisory"
    return "info"


def parse(rows: list[dict]) -> list[dict]:
    out = []
    for (name, state, lat, lon), d in zip(CITIES, rows):
        c = d["current"]
        t, app = c.get("temperature_2m"), c.get("apparent_temperature")
        rate = (c.get("precipitation") or 0) * 3600 / (c.get("interval") or 3600)  # interval is usually 15 min
        text = WMO.get(c.get("weather_code"), "")
        out.append(record(name.lower().replace(" ", "_"), title=f"{name} {t:.0f}°C {text}".strip(), kind="weather",
                          lon=lon, lat=lat, observed_at=c["time"], severity=severity(app, t, rate), city=name,
                          state=state, temp_c=t, apparent_c=app, humidity=c.get("relative_humidity_2m"),
                          wind_kmh=c.get("wind_speed_10m"), wind_dir=c.get("wind_direction_10m"),
                          precip_mm=c.get("precipitation"), precip_mm_h=round(rate, 2),
                          weather_code=c.get("weather_code"), weather=text))
    return out


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL)).json())


FEED = Feed(id="city_weather", label="City weather (Open-Meteo)", section="hazards", homepage="https://open-meteo.com/",
            terms="Open-Meteo free API, CC BY 4.0 (attribute Open-Meteo); non-commercial use without key",
            every=900, fetch=fetch)
