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

    con.commit()
    con.close()


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
    price_series = candidate["price_ct"]

    for start_idx in range(len(price_series)):
        cost = compute_cost_for_start(price_series.iloc[start_idx:], power_kw, runtime_h)
        if cost is None:
            break
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_start = price_series.index[start_idx]

    return best_start, best_cost


# =========================
# STREAMLIT UI
# =========================
init_db()

st.title("⚡EnergiX Planner⚡")

prices_df = fetch_market_data()
if not prices_df.empty:
    st.subheader("Strompreisverlauf")
    st.line_chart(prices_df["price_eur"])

    now = pd.Timestamp.now(tz=LOCAL_TZ)
    future_prices = prices_df[prices_df.index >= now]

    if future_prices.empty:
        st.warning("Es sind keine zukünftigen Preisintervalle verfügbar.")
    else:
        best_one_hour = future_prices["price_ct"].idxmin()
        best_price = future_prices.loc[best_one_hour, "price_eur"]
        st.info(
            f"Günstigster verfügbarer Startzeitraum (1 Std.): {best_one_hour.strftime('%d.%m.%Y %H:%M')} — "
            f"{(best_one_hour + pd.Timedelta(hours=1)).strftime('%H:%M')} ({best_price:.2f} €/kWh)"
        )
else:
    st.error("Preis-Daten konnten nicht angezeigt werden.")

# -------------------------
# ADD DEVICE
# -------------------------
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
            best_start, best_cost = find_cheapest_start(prices_df, row["power_kw"], row["runtime_h"], earliest=now)
            current_cost = None
            if not future_prices.empty:
                current_cost = compute_cost_for_start(future_prices["price_ct"], row["power_kw"], row["runtime_h"])

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