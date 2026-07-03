import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "pro_strom.db"
LOCAL_TZ = ZoneInfo("Europe/Berlin")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    con = get_conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS appliances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        icon TEXT,
        power_kw REAL NOT NULL,
        runtime_h REAL NOT NULL
    )
    """)

    cur.execute("PRAGMA table_info(appliances)")
    existing_columns = [row[1] for row in cur.fetchall()]
    if "category" not in existing_columns:
        cur.execute("ALTER TABLE appliances ADD COLUMN category TEXT")
    if "icon" not in existing_columns:
        cur.execute("ALTER TABLE appliances ADD COLUMN icon TEXT")

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


def store_price_history(df: pd.DataFrame):
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


def add_appliance(name, power_kw, runtime_h, category=None, icon=None):
    con = get_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO appliances (name, category, icon, power_kw, runtime_h) VALUES (?, ?, ?, ?, ?)",
        (name, category, icon, power_kw, runtime_h),
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


def get_appliance_count():
    return len(get_appliances())


def get_recent_recommendations(limit=5):
    con = get_conn()
    df = pd.read_sql(
        "SELECT appliance_name, power_kw, runtime_h, start_iso, end_iso, estimated_cost, computed_at FROM recommendation_history ORDER BY id DESC LIMIT ?",
        con,
        params=(limit,),
    )
    con.close()
    return df


def get_today_recommendations(limit=5):
    con = get_conn()
    df = pd.read_sql(
        "SELECT appliance_name, power_kw, runtime_h, start_iso, end_iso, estimated_cost, computed_at FROM recommendation_history WHERE DATE(start_iso, 'localtime') = DATE('now', 'localtime') ORDER BY start_ts ASC LIMIT ?",
        con,
        params=(limit,),
    )
    con.close()
    return df
