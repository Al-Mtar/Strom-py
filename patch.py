from pathlib import Path
path = Path('Stromplaner.py')
text = path.read_text(encoding='utf-8')
old = '''df = get_appliances()

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
            st.rerun()'''
new = '''df = get_appliances()

if df.empty:
    st.info("Keine Geräte gespeichert")
else:
    st.dataframe(df)

    for _, row in df.iterrows():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

        col1.write(row["name"])
        col2.write(f"{row['power_kw']} kW")
        col3.write(f"{row['runtime_h']} h")

        if col4.button("🗑️", key=f"del_{row['id']}"):
            delete_appliance(row["id"])
            st.rerun()'''
if old not in text:
    raise SystemExit('Old block not found')
path.write_text(text.replace(old, new), encoding='utf-8')
print('patched')
