import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# =========================
# CONFIG
# =========================
DB_PATH = "pro_strom.db"


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


# =========================
# STREAMLIT UI
# =========================
init_db()

st.title("⚡EnergiX Planner⚡")

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