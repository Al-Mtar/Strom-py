# Pro-Strom — Verbrauchsplanung & Empfehlungen

Kurzes Demo-Projekt, das Verbrauchsgeräte (Leistung + Laufzeit) annimmt, Strompreis-Vorhersagen verwendet und günstige Startzeiten empfiehlt.

Installation:

```bash
python -m venv .venv
.
# Windows PowerShell
.\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

Starten (Streamlit):

```bash
streamlit run main.py
```

Hinweise:
- Standardmäßig werden Mock-Preise erzeugt (im Sidebar wählbar).
- Für echtes API-Backend `ENERGY_API_URL` (und optional `ENERGY_API_KEY`) als Umgebungsvariablen setzen.
- Preise und Empfehlungen werden in `pro_strom.db` (SQLite) gespeichert.
