import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

AWATTAR_URL = "https://api.awattar.de/v1/marketdata"
DB_PATH = Path(__file__).resolve().parent / "pro_strom.db"
LOCAL_TZ = ZoneInfo("Europe/Berlin")


def fetch_market_data():
    try:
        response = requests.get(AWATTAR_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        st.error("Marktdaten konnten nicht geladen werden.")
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

# =========================
# DB LAYER
# =========================


# =========================
# DB LAYER
# =========================
def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    con = get_conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS appliances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        power_kw REAL NOT NULL,
        runtime_h REAL NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        start_ts INTEGER PRIMARY KEY,
        start_iso TEXT NOT NULL,
        date TEXT NOT NULL,
        weekday INTEGER NOT NULL,
        hour INTEGER NOT NULL,
        price_ct REAL NOT NULL,
        price_eur REAL NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recommendation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appliance_name TEXT NOT NULL,
        power_kw REAL NOT NULL,
        runtime_h REAL NOT NULL,
        start_ts INTEGER NOT NULL,
        end_ts INTEGER NOT NULL,
        start_iso TEXT NOT NULL,
        end_iso TEXT NOT NULL,
        estimated_cost REAL NOT NULL,
        computed_at TEXT NOT NULL
    )
    """)

    con.commit()
    con.close()


def store_price_history(df):
    if df.empty:
        return

    con = get_conn()
    cur = con.cursor()
    for idx, row in df.iterrows():
        start_ts = int(idx.timestamp())
        cur.execute(
            "INSERT OR IGNORE INTO price_history (start_ts, start_iso, date, weekday, hour, price_ct, price_eur) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                start_ts,
                idx.isoformat(),
                idx.date().isoformat(),
                idx.weekday(),
                idx.hour,
                float(row["price_ct"]),
                float(row["price_eur"]),
            ),
        )
    con.commit()
    con.close()


def store_recommendation(appliance_name, power_kw, runtime_h, start_time, end_time, estimated_cost):
    if start_time is None or estimated_cost is None:
        return

    con = get_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO recommendation_history (appliance_name, power_kw, runtime_h, start_ts, end_ts, start_iso, end_iso, estimated_cost, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            appliance_name,
            power_kw,
            runtime_h,
            int(start_time.timestamp()),
            int(end_time.timestamp()),
            start_time.isoformat(),
            end_time.isoformat(),
            estimated_cost,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    con.commit()
    con.close()


def get_average_price_per_weekday():
    con = get_conn()
    df = pd.read_sql(
        "SELECT weekday, AVG(price_eur) AS avg_price FROM price_history GROUP BY weekday ORDER BY weekday",
        con,
    )
    con.close()
    if df.empty:
        return df

    weekday_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    df["weekday_name"] = df["weekday"].apply(lambda w: weekday_names[w])
    return df


def get_recent_recommendations(limit=5):
    con = get_conn()
    df = pd.read_sql(
        "SELECT appliance_name, power_kw, runtime_h, start_iso, end_iso, estimated_cost, computed_at FROM recommendation_history ORDER BY id DESC LIMIT ?",
        con,
        params=(limit,),
    )
    con.close()
    return df


def find_cheapest_window_for_today(price_df, power_kw, runtime_h):
    if price_df.empty or runtime_h <= 0:
        return None, None

    now = pd.Timestamp.now(tz=LOCAL_TZ)
    today_end = now.normalize() + pd.Timedelta(days=1)
    latest_start = today_end - pd.Timedelta(hours=runtime_h)
    candidate = price_df[(price_df.index >= now) & (price_df.index <= latest_start)]
    if candidate.empty:
        return None, None

    return find_cheapest_start(candidate, power_kw, runtime_h, earliest=now)


def format_time_slot(start_time, runtime_h):
    if start_time is None:
        return "-"
    end_time = start_time + pd.Timedelta(hours=runtime_h)
    return f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}"


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
        95: ("Gewitter", "⛈️"),
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


# =========================
# CRUD FUNCTIONS
# =========================
def add_appliance(name, power_kw, runtime_h):
    con = get_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO appliances (name, power_kw, runtime_h) VALUES (?, ?, ?)",
        (name, power_kw, runtime_h)
    )
    con.commit()
    con.close()


def get_appliances():
    con = get_conn()
    df = pd.read_sql("SELECT * FROM appliances", con)
    con.close()
    return df


def delete_appliance(appliance_id):
    con = get_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM appliances WHERE id = ?", (appliance_id,))
    con.commit()
    con.close()


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


def get_dresden_consumption():
    # Ungefähre Koordinaten Dresdner Stadtteile mit geschätztem
    # täglichem Stromverbrauch (MWh) – dient als Demo-Datensatz.
    data = [
        ("Altstadt", 51.0493, 13.7381, 480),
        ("Neustadt", 51.0660, 13.7460, 360),
        ("Striesen", 51.0430, 13.7900, 290),
        ("Blasewitz", 51.0540, 13.8060, 250),
        ("Plauen", 51.0260, 13.7080, 210),
        ("Löbtau", 51.0420, 13.6960, 230),
        ("Pieschen", 51.0830, 13.7270, 240),
        ("Klotzsche", 51.1230, 13.7790, 180),
        ("Prohlis", 50.9990, 13.7990, 320),
        ("Cotta", 51.0560, 13.6700, 200),
        ("Leuben", 51.0140, 13.8290, 160),
        ("Gruna", 51.0330, 13.7860, 190),
    ]
    df = pd.DataFrame(data, columns=["district", "lat", "lon", "consumption_mwh"])

    lo, hi = df["consumption_mwh"].min(), df["consumption_mwh"].max()

    def to_color(value):
        t = (value - lo) / (hi - lo) if hi > lo else 0.0
        red = int(60 + t * 195)    # niedrig -> grünlich, hoch -> rot
        green = int(170 - t * 140)
        return f"#{red:02x}{green:02x}40"

    df["color"] = df["consumption_mwh"].apply(to_color)
    df["size"] = df["consumption_mwh"] * 4   # Radius in Metern
    return df


def fetch_life_expectancy_data():
    country_list = [
        ("DEU", "Europe", "Germany"),
        ("FRA", "Europe", "France"),
        ("ITA", "Europe", "Italy"),
        ("ESP", "Europe", "Spain"),
        ("SWE", "Europe", "Sweden"),
        ("USA", "North America", "United States"),
        ("CAN", "North America", "Canada"),
        ("MEX", "North America", "Mexico"),
        ("BRA", "South America", "Brazil"),
        ("ARG", "South America", "Argentina"),
        ("CHL", "South America", "Chile"),
        ("JPN", "Asia", "Japan"),
        ("CHN", "Asia", "China"),
        ("IND", "Asia", "India"),
        ("AUS", "Oceania", "Australia"),
        ("NZL", "Oceania", "New Zealand"),
        ("ZAF", "Africa", "South Africa"),
        ("EGY", "Africa", "Egypt"),
        ("NGA", "Africa", "Nigeria"),
        ("KEN", "Africa", "Kenya"),
    ]

    countries = ";".join(code for code, _, _ in country_list)
    try:
        response = requests.get(
            "https://api.worldbank.org/v2/country/" + countries + "/indicator/SP.DYN.LE00.IN",
            params={"format": "json", "date": "2022"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        df = pd.DataFrame(rows)
        if df.empty:
            raise ValueError("No rows returned")

        df = df[["country", "value"]].copy()
        df["country"] = df["country"].apply(lambda item: item.get("value") if isinstance(item, dict) else item)
        df = df.rename(columns={"country": "country_name", "value": "life_expectancy_years"})
        country_lookup = {name: continent for _, continent, name in country_list}
        df["continent"] = df["country_name"].map(country_lookup)
        df = df.dropna(subset=["continent", "life_expectancy_years"])
        df = df[["country_name", "continent", "life_expectancy_years"]]
        return df.sort_values(["continent", "life_expectancy_years"], ascending=[True, False])
    except Exception:
        fallback = pd.DataFrame(country_list, columns=["country_code", "continent", "country_name"])
        fallback["life_expectancy_years"] = [
            81.7, 82.5, 82.7, 83.1, 82.8,
            78.5, 82.0, 75.2,
            73.5, 76.0, 80.0,
            84.5, 77.2, 69.0,
            83.0, 82.5,
            63.0, 71.8, 62.0, 66.5,
        ]
        return fallback[["country_name", "continent", "life_expectancy_years"]]


def get_continent_life_expectancy():
    data = fetch_life_expectancy_data()
    if data.empty:
        return pd.DataFrame(columns=["continent", "avg_life_expectancy", "countries"])

    summary = (
        data.groupby("continent", as_index=False)["life_expectancy_years"]
        .mean()
        .rename(columns={"life_expectancy_years": "avg_life_expectancy"})
    )
    summary["countries"] = (
        data.groupby("continent")["country_name"]
        .apply(lambda values: ", ".join(values))
        .values
    )
    summary = summary.sort_values("avg_life_expectancy", ascending=False)
    return summary


def get_poorest_countries():
    data = fetch_life_expectancy_data()
    if data.empty:
        return pd.DataFrame(columns=["country_name", "continent", "life_expectancy_years"])
    return data.sort_values("life_expectancy_years", ascending=True).head(10)
# =========================
# STREAMLIT UI
# =========================
init_db()

st.title("⚡EnergiX Planner⚡")

with st.expander("🌦️ Wetter weltweit", expanded=False):
    st.caption("Suche eine Stadt und sieh dir das aktuelle Wetter an – als einfacher Wetterbericht wie sonnig, regnerisch oder windig.")
    weather_city = st.text_input("Stadt eingeben", value="Berlin", key="weather_city")
    weather_button = st.button("Wetter anzeigen", key="weather_lookup")

    if weather_button:
        with st.spinner("Wetter wird geladen..."):
            weather_data = fetch_weather(weather_city)
        if weather_data:
            st.success(f"{weather_data['emoji']} {weather_data['condition']} in {weather_data['city']}, {weather_data['country']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Temperatur", f"{weather_data['temperature']} {weather_data['temperature_unit']}")
            col2.metric("Wind", f"{weather_data['wind']} {weather_data['wind_unit']}")
            col3.metric("Luftfeuchtigkeit", f"{weather_data['humidity']} %")
            col4.metric("Niederschlag", f"{weather_data['precipitation']} {weather_data['precipitation_unit']}")
            st.caption(f"Letzter Stand: {weather_data['time']}")
        else:
            st.warning("Für diese Stadt wurden keine Wetterdaten gefunden.")

prices_df = fetch_market_data()
store_price_history(prices_df)
with st.expander("⚡ Strompreise und Empfehlungen", expanded=False):
    if not prices_df.empty:
        st.subheader("☀️ Solar-Option")
        solar_enabled = st.checkbox("Ich habe eine Solaranlage")
        solar_price_eur = 0.0
        self_consumption_pct = 0.0

        if solar_enabled:
            solar_price_eur = st.number_input("Solarstrompreis (€/kWh)", 0.0, 1.0, 0.08, step=0.01)
            self_consumption_pct = st.number_input("Eigenverbrauchsanteil (%)", 0, 100, 70, step=1)
            st.caption("Der effektive Strompreis wird für den Eigenverbrauch mit dem Solarpreis berechnet.")

        analysis_prices_df = (
            apply_solar_price_adjustment(prices_df, solar_price_eur, self_consumption_pct)
            if solar_enabled
            else prices_df
        )

        st.subheader("Strompreisverlauf")
        chart_series = analysis_prices_df["effective_price_eur"] if solar_enabled else analysis_prices_df["price_eur"]
        st.line_chart(chart_series)

        now = pd.Timestamp.now(tz=LOCAL_TZ)
        future_prices = analysis_prices_df[analysis_prices_df.index >= now]

        if future_prices.empty:
            st.warning("Es sind keine zukünftigen Preisintervalle verfügbar.")
        else:
            price_column = "effective_price_ct" if solar_enabled else "price_ct"
            best_one_hour = future_prices[price_column].idxmin()
            best_price = future_prices.loc[best_one_hour, "effective_price_eur"] if solar_enabled else future_prices.loc[best_one_hour, "price_eur"]
            st.info(
                f"Günstigster verfügbarer Startzeitraum (1 Std.): {best_one_hour.strftime('%d.%m.%Y %H:%M')} — "
                f"{(best_one_hour + pd.Timedelta(hours=1)).strftime('%H:%M')} ({best_price:.2f} €/kWh)"
            )

        st.subheader("Beste Waschmaschinen-Zeit heute")
        washing_power = 2.0
        washing_runtime = st.number_input("Waschdauer heute (h)", 0.5, 4.0, 1.5, step=0.5)
        best_start, best_cost = find_cheapest_window_for_today(analysis_prices_df, washing_power, washing_runtime)
        if best_start is not None and best_cost is not None:
            end_time = best_start + pd.Timedelta(hours=washing_runtime)
            st.success(
                f"Empfohlene Zeit: {format_time_slot(best_start, washing_runtime)} — geschätzte Kosten: {best_cost:.2f} €"
            )
            store_recommendation(
                "Waschmaschine",
                washing_power,
                washing_runtime,
                best_start,
                end_time,
                best_cost,
            )
        else:
            st.warning("Keine passende Waschmaschine-Zeit heute gefunden.")

        st.subheader("Historische Preis-Analytics")
        avg_prices = get_average_price_per_weekday()
        if not avg_prices.empty:
            avg_prices = avg_prices.set_index("weekday_name")
            st.bar_chart(avg_prices["avg_price"])
            st.table(avg_prices[["avg_price"]].rename(columns={"avg_price": "Durchschnittlicher Strompreis (€/kWh)"}))
        else:
            st.info("Noch keine historische Preisdaten gespeichert.")

        st.subheader("Letzte Empfehlungen")
        recent_recommendations = get_recent_recommendations(limit=5)
        if not recent_recommendations.empty:
            recent_recommendations["estimated_cost"] = recent_recommendations["estimated_cost"].map(lambda v: f"{v:.2f} €")
            st.table(recent_recommendations)
        else:
            st.info("Noch keine Empfehlungen gespeichert.")
    else:
        st.error("Preis-Daten konnten nicht angezeigt werden.")

# -------------------------
# DRESDEN CONSUMPTION MAP
# -------------------------
with st.expander("🗺️ Stromverbrauch in Dresden", expanded=False):
    st.caption(
        "Geschätzter täglicher Stromverbrauch je Stadtteil (MWh). "
        "Punktgröße und Farbe skalieren mit dem Verbrauch (grün = niedrig, rot = hoch)."
    )
    dresden_df = get_dresden_consumption()
    st.map(dresden_df, latitude="lat", longitude="lon", size="size", color="color", zoom=10)
    st.dataframe(
        dresden_df[["district", "consumption_mwh"]]
        .rename(columns={"district": "Stadtteil", "consumption_mwh": "Verbrauch (MWh/Tag)"})
        .sort_values("Verbrauch (MWh/Tag)", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("🔥 Günstigste Zeit für ein Gerät in jedem Stadtteil")
    st.caption("Hier siehst du pro Stadtteil die beste Startzeit für ein Gerät wie Herd oder Ofen, damit du Stromkosten sparen kannst.")
    appliance_power = st.number_input("Leistung des Geräts (kW)", 0.5, 10.0, 2.2, step=0.1)
    appliance_runtime = st.number_input("Betriebsdauer (h)", 0.5, 4.0, 1.5, step=0.5)

    if not prices_df.empty:
        price_source_df = analysis_prices_df if "analysis_prices_df" in locals() and not analysis_prices_df.empty else prices_df
        now = pd.Timestamp.now(tz=LOCAL_TZ)
        future_prices = price_source_df[price_source_df.index >= now]

        if future_prices.empty:
            st.info("Keine zukünftigen Preisintervalle verfügbar.")
        else:
            recommendations = []
            for _, row in dresden_df.iterrows():
                best_start, best_cost = find_cheapest_start(future_prices, appliance_power, appliance_runtime, earliest=now)
                if best_start is not None and best_cost is not None:
                    recommendations.append(
                        {
                            "Stadtteil": row["district"],
                            "Empfohlene Startzeit": best_start.strftime("%d.%m.%Y %H:%M"),
                            "Geschätzte Kosten": f"{best_cost:.2f} €",
                            "Tipp": f"Nutze das Gerät bis {format_time_slot(best_start, appliance_runtime)}",
                        }
                    )
                else:
                    recommendations.append(
                        {
                            "Stadtteil": row["district"],
                            "Empfohlene Startzeit": "Nicht verfügbar",
                            "Geschätzte Kosten": "-",
                            "Tipp": "Keine passende Zeit gefunden",
                        }
                    )

            rec_df = pd.DataFrame(recommendations)
            st.dataframe(
                rec_df.sort_values("Stadtteil"),
                hide_index=True,
                use_container_width=True,
            )
            if rec_df["Empfohlene Startzeit"].ne("Nicht verfügbar").any():
                first_reco = rec_df.loc[rec_df["Empfohlene Startzeit"] != "Nicht verfügbar"].iloc[0]
                st.success(
                    f"Am günstigsten startest du das Gerät um {first_reco['Empfohlene Startzeit']} und sparst damit gegenüber teureren Zeiten.")
    else:
        st.info("Keine Strompreisdaten verfügbar.")

# -------------------------
# LIFE EXPECTANCY BY CONTINENT
# -------------------------
with st.expander("🌍 Lebenserwartung nach Kontinenten", expanded=False):
    st.caption("Vergleich der jüngsten verfügbaren Lebenserwartung nach Kontinenten und Ländern.")
    life_df = get_continent_life_expectancy()
    if not life_df.empty:
        chart_df = life_df.rename(columns={"continent": "Kontinenten", "avg_life_expectancy": "Durchschnittliche Lebenserwartung"})
        st.bar_chart(chart_df.set_index("Kontinenten")["Durchschnittliche Lebenserwartung"])
        st.dataframe(
            chart_df.rename(columns={"countries": "Länder"})[["Kontinenten", "Durchschnittliche Lebenserwartung", "Länder"]],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Lebenserwartungsdaten konnten nicht geladen werden.")

    poor_df = get_poorest_countries()
    if not poor_df.empty:
        st.subheader("📉 Ärmste Länder")
        poor_display_df = poor_df.rename(columns={"country_name": "Land", "continent": "Kontinenten", "life_expectancy_years": "Lebenserwartung (Jahre)"})[["Kontinenten", "Land", "Lebenserwartung (Jahre)"]]
        st.dataframe(
            poor_display_df,
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Keine Daten für die ärmsten Länder verfügbar.")

# -------------------------
# DRESDEN CONSUMPTION MAP
# -------------------------
st.subheader("🗺️ Stromverbrauch in Dresden")
st.caption(
    "Geschätzter täglicher Stromverbrauch je Stadtteil (MWh). "
    "Punktgröße und Farbe skalieren mit dem Verbrauch (grün = niedrig, rot = hoch)."
)
dresden_df = get_dresden_consumption()
st.map(dresden_df, latitude="lat", longitude="lon", size="size", color="color", zoom=10)
st.dataframe(
    dresden_df[["district", "consumption_mwh"]]
    .rename(columns={"district": "Stadtteil", "consumption_mwh": "Verbrauch (MWh/Tag)"})
    .sort_values("Verbrauch (MWh/Tag)", ascending=False),
    hide_index=True,
    use_container_width=True,
)

# -------------------------
# ADD DEVICE
# -------------------------
with st.expander("🔧 Geräteverwaltung", expanded=False):
    st.subheader("Gerät hinzufügen")

    with st.form("add_form"):
        name = st.text_input("Name")
        power = st.number_input("Leistung (kW)", 0.1, 10.0, 2.0)
        runtime = st.number_input("Laufzeit (h)", 0.1, 24.0, 1.0)

        if st.form_submit_button("Speichern"):
            if name:
                add_appliance(name, power, runtime)
                st.success("Gespeichert!")
                st.rerun()
            else:
                st.error("Bitte Name eingeben")


    # -------------------------
    # LIST + DELETE
    # -------------------------
    st.subheader("Gespeicherte Geräte")

    df = get_appliances()

    if df.empty:
        st.info("Keine Geräte gespeichert")
    else:
        for _, row in df.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

            col1.write(row["name"])
            col2.write(f"{row['power_kw']} kW")
            col3.write(f"{row['runtime_h']} h")

            if col4.button("🗑️", key=f"del_{row['id']}"):
                delete_appliance(row["id"])
                st.rerun()

        if not prices_df.empty:
            st.subheader("Kostenberechnung & günstigste Startzeit")

            summary_rows = []
            now = pd.Timestamp.now(tz=LOCAL_TZ)
            future_prices = prices_df[prices_df.index >= now]

            for _, row in df.iterrows():
                best_start, best_cost = find_cheapest_start(analysis_prices_df, row["power_kw"], row["runtime_h"], earliest=now)
                current_cost = None
                if not future_prices.empty:
                    price_column = "effective_price_ct" if solar_enabled else "price_ct"
                    current_cost = compute_cost_for_start(future_prices[price_column], row["power_kw"], row["runtime_h"])

                summary_rows.append(
                    {
                        "Name": row["name"],
                        "Leistung (kW)": row["power_kw"],
                        "Laufzeit (h)": row["runtime_h"],
                        "Kosten bei nächstem Start": f"{current_cost:.2f} €" if current_cost is not None else "-",
                        "Günstigster Start": best_start.strftime("%d.%m.%Y %H:%M") if best_start is not None else "Nicht verfügbar",
                        "Kosten (günstig)": f"{best_cost:.2f} €" if best_cost is not None else "-",
                    }
                )

            st.table(pd.DataFrame(summary_rows))