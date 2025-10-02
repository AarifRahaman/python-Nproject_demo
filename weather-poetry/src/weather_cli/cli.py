import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime

WMO_TEXT = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

def _get_json(url: str):
    try:
        with urllib.request.urlopen(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            return json.load(resp)
    except Exception as e:
        raise RuntimeError(f"Network/API error: {e}")

def geocode(place: str, language: str = "en"):
    params = urllib.parse.urlencode({
        "name": place,
        "count": 1,
        "language": language,
        "format": "json",
    })
    url = f"https://geocoding-api.open-meteo.com/v1/search?{params}"
    data = _get_json(url)
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    return {
        "name": r.get("name"),
        "country": r.get("country"),
        "lat": r["latitude"],
        "lon": r["longitude"],
        "tz": r.get("timezone", "auto"),
    }

def fetch_weather(lat: float, lon: float, days: int, unit: str, tz: str = "auto"):
    temp_unit = "fahrenheit" if unit == "imperial" else "celsius"
    wind_unit = "mph" if unit == "imperial" else "kmh"

    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": tz or "auto",
        "forecast_days": max(1, min(days, 16)),
        "temperature_unit": temp_unit,
        "wind_speed_unit": wind_unit,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    return _get_json(url)

def format_current(current: dict, unit: str) -> str:
    if not current:
        return "Current: (no data)"
    code = int(current.get("weathercode", -1))
    desc = WMO_TEXT.get(code, f"WMO {code}")
    temp = current.get("temperature")
    wind = current.get("windspeed")
    time_str = current.get("time")
    try:
        when = datetime.fromisoformat(time_str).strftime("%Y-%m-%d %H:%M")
    except Exception:
        when = str(time_str)
    u_temp = "°F" if unit == "imperial" else "°C"
    u_wind = "mph" if unit == "imperial" else "km/h"
    return f"Current ({when}): {desc}, {temp}{u_temp}, wind {wind} {u_wind}"

def format_daily(daily: dict, unit: str, days: int) -> str:
    if not daily:
        return "Forecast: (no data)"
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    pop = daily.get("precipitation_probability_max", [])
    u_temp = "°F" if unit == "imperial" else "°C"
    lines = ["Forecast:"]
    for i in range(min(days, len(dates))):
        lines.append(
            f"  {dates[i]}  min {tmin[i]}{u_temp} / max {tmax[i]}{u_temp}"
            + (f"  (rain prob {pop[i]}%)" if i < len(pop) and pop[i] is not None else "")
        )
    return "\n".join(lines)

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="weather",
        description="Simple Weather CLI using Open-Meteo (no API key).",
    )
    parser.add_argument("place", help='City or place name, e.g. "Berlin" or "Cottbus"')
    parser.add_argument("--days", type=int, default=3, help="How many forecast days (1–16). Default: 3")
    parser.add_argument("--unit", choices=["metric", "imperial"], default="metric", help="Units: metric or imperial")
    parser.add_argument("--lang", default="en", help="Geocoding language (default: en)")

    args = parser.parse_args(argv)

    where = geocode(args.place, language=args.lang)
    if not where:
        print(f"Could not find a place named '{args.place}'. Try a more specific name.", file=sys.stderr)
        return 2

    data = fetch_weather(where["lat"], where["lon"], args.days, args.unit, tz=where["tz"])

    header = f"{where['name']}, {where.get('country','')}".strip().strip(',')
    print(f"{header}  (lat {where['lat']}, lon {where['lon']})")
    print(format_current(data.get("current_weather"), args.unit))
    print(format_daily(data.get("daily"), args.unit, args.days))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
