# Projekt-Notizen: Pro-Strom-py (Tag 1–10)

## Tag 1
- Projekt gestartet als kleines Demo mit einer einfachen Streamlit-App.
- `main.py` zeigt ein kleines Wetter-Beispiel (Open-Meteo API).

## Tag 2
- Erste Arbeit an der Benutzeroberfläche mit Streamlit.
- Ziel gesetzt: Geräte verwalten und günstige Startzeiten finden.

## Tag 3
- `Stromplaner.py` wurde als zentrale Datei erstellt.
- Funktionen für Geräte (Name, Leistung, Laufzeit) implementiert.

## Tag 4
- Erste SQLite-Datenbank `pro_strom.db` angelegt.
- Tabellen: `appliances`, `price_history`, `recommendation_history`.

## Tag 5
- Anbindung an die aWATTar Marktpreis-API hinzugefügt.
- Preisdaten werden geparst und in `price_history` gespeichert.

## Tag 6
- Wetter-Suche (Open-Meteo) in die App integriert.
- Zusätzliche Demo-Daten (z. B. Verbrauch Dresden) hinzugefügt.

## Tag 7
- Empfehlungssystem ergänzt: Bestes Startzeitfenster berechnen.
- Empfehlungen werden in `recommendation_history` gespeichert.

## Tag 8
- Projekt modularisiert: `db.py`, `energy.py` und `ui.py` erstellt.
- Code sauberer getrennt: DB / API / UI / Business-Logik.

## Tag 9
- Plotly eingebunden und modernes Dashboard entwickelt.
- Dashboard zeigt aktuellen Preis, günstigste/teuerste Stunde und Tageskosten.

## Tag 10
- Projekt-Dokumentation (`PROJECT_NOTES.md`) hinzugefügt und aktualisiert.
- Alle Änderungen committed und zu `origin/main` gepusht.

## Kurze Zusammenfassung (einfache Sprache)
- Tag 1–3: App-Grundgerüst und Geräteverwaltung.
- Tag 4–7: Datenbank, Preisdaten und Empfehlungssystem.
- Tag 8–9: Modularisierung und Dashboard (Plotly).
- Tag 10: Notizen ergänzt und alles auf das Git-Repo gepusht.

