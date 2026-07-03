import requests
import pandas as pd
from db import LOCAL_TZ

AWATTAR_URL = "https://api.awattar.de/v1/marketdata"


def fetch_market_data():
    try:
        response = requests.get(AWATTAR_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return pd.DataFrame()

    df = pd.DataFrame(data.get("data", []))
    if df.empty:
        return df

    if "start" not in df.columns and "start_timestamp" in df.columns:
        df["start"] = pd.to_datetime(df["start_timestamp"], unit="ms", utc=True)

    if "start" in df.columns:
        df = df.set_index("start").sort_index()
        df = df.tz_convert(LOCAL_TZ)

    if "price_ct" in df.columns:
        df["price_eur"] = df["price_ct"] / 100
    elif "marketprice" in df.columns:
        df["price_eur"] = df["marketprice"] / 100

    if "price_ct" not in df.columns:
        if "marketprice" in df.columns:
            df["price_ct"] = df["marketprice"]
        elif "price_eur" in df.columns:
            df["price_ct"] = (df["price_eur"] * 100).astype(float)

    return df


def map_weather_code(weather_code):
    weather_map = {
        0: ("Sonnig", "☀️"),
        1: ("Meist sonnig", "🌤️"),
        2: ("Teilweise bewölkt", "⛅"),
        3: ("Bewölkt", "☁️"),
        45: ("Nebel", "🌫️"),
        48: ("Nebel mit Reif", "🌫️"),
        51: ("Leichter Nieselregen", "🌦️"),
        53: ("Nieselregen", "🌦️"),
        55: ("Starker Nieselregen", "🌧️"),
        61: ("Leichter Regen", "🌧️"),
        63: ("Regen", "🌧️"),
        65: ("Starker Regen", "⛈️"),
        71: ("Leichter Schneefall", "🌨️"),
        73: ("Schneefall", "🌨️"),
        75: ("Starker Schneefall", "❄️"),
        80: ("Leichte Schauer", "🌦️"),
        81: ("Schauer", "🌧️"),
        82: ("Starke Schauer", "⛈️"),
        95: ("Gewitter", "⛅"),
        96: ("Gewitter mit Hagel", "⛈️"),
        99: ("Schweres Gewitter", "⛈️"),
    }
    return weather_map.get(weather_code, ("Unbekannt", "🌈"))


def fetch_weather(city):
    if not city:
        return None

    try:
        geo_response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "de", "format": "json"},
            timeout=10,
        )
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        results = geo_data.get("results") or []
        if not results:
            return None

        location = results[0]
        weather_response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
                "timezone": "auto",
            },
            timeout=10,
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        current = weather_data.get("current", {})
        current_units = weather_data.get("current_units", {})
        code = current.get("weather_code")
        condition, emoji = map_weather_code(code)

        return {
            "city": location.get("name", city),
            "country": location.get("country", ""),
            "temperature": current.get("temperature_2m"),
            "temperature_unit": current_units.get("temperature_2m", "°C"),
            "humidity": current.get("relative_humidity_2m"),
            "wind": current.get("wind_speed_10m"),
            "wind_unit": current_units.get("wind_speed_10m", "km/h"),
            "precipitation": current.get("precipitation"),
            "precipitation_unit": current_units.get("precipitation", "mm"),
            "condition": condition,
            "emoji": emoji,
            "time": current.get("time"),
        }
    except Exception:
        return None


def compute_cost_for_start(price_series, power_kw, runtime_h):
    if runtime_h <= 0 or price_series.empty:
        return None

    remaining = runtime_h
    total_cost_ct = 0.0
    for price_ct in price_series:
        duration = min(remaining, 1.0)
        total_cost_ct += price_ct * duration
        remaining -= duration
        if remaining <= 0:
            break

    if remaining > 0:
        return None
    return power_kw * total_cost_ct / 100


def find_cheapest_start(price_df, power_kw, runtime_h, earliest=None):
    if price_df.empty or runtime_h <= 0:
        return None, None

    candidate = price_df if earliest is None else price_df[price_df.index >= earliest]
    if candidate.empty:
        return None, None

    best_cost = None
    best_start = None
    price_column = "effective_price_ct" if "effective_price_ct" in candidate.columns else "price_ct"
    price_series = candidate[price_column]

    for start_idx in range(len(price_series)):
        cost = compute_cost_for_start(price_series.iloc[start_idx:], power_kw, runtime_h)
        if cost is None:
            break
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_start = price_series.index[start_idx]

    return best_start, best_cost


def apply_solar_price_adjustment(price_df, solar_price_eur, self_consumption_pct):
    if price_df.empty:
        return price_df.copy()

    adjusted = price_df.copy()
    solar_price_ct = solar_price_eur * 100
    adjusted["effective_price_ct"] = adjusted["price_ct"] * (1 - self_consumption_pct / 100) + solar_price_ct * (self_consumption_pct / 100)
    adjusted["effective_price_eur"] = adjusted["effective_price_ct"] / 100
    return adjusted


def get_price_summary(price_df):
    if price_df.empty or "price_eur" not in price_df.columns:
        return {}

    summary = {
        "current_price": float(price_df["price_eur"].iloc[0]),
        "cheapest_hour": price_df["price_eur"].idxmin(),
        "expensive_hour": price_df["price_eur"].idxmax(),
        "estimated_daily_cost": float(price_df["price_eur"].sum()),
    }
    return summary
