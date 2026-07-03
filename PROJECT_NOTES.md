# Projekt-Notizen: Pro-Strom-py

## Tag 1
- Projekt begann als kleines Demo-Projekt mit einer einfachen Streamlit-App.
- `main.py` zeigt den Start des Projekts und ruft eine Wetter-API ab.
- Ziel war: Stromverbrauch zu planen und günstigere Startzeiten für Geräte zu finden.
- Jeden Fortschritt sollte man direkt per Git push sichern.

##  Tag 2 Erste funktionale Schritte
- Es wurde eine Datei `Stromplaner.py` erstellt, die den Kern der App enthält.
- Die App verwendet Streamlit für die Benutzeroberfläche.
- Es wurde eine Verbindung zur `awattar` Marktpreis-API eingebaut, um Strompreise zu laden.
- Gleichzeitig wurde eine lokale SQLite-Datenbank `pro_strom.db` eingerichtet.
- Nach jeder neuen Funktion sollte der Code in Git gespeichert und gepusht werden.

##  Tag 3 Daten und Speicherung
- In der Datenbank gibt es Tabellen für:
  - Geräte (`appliances`)
  - Preisverlauf (`price_history`)
  - Empfehlungsverlauf (`recommendation_history`)
- Die App kann Preise speichern und später auswerten.
- Änderungen am Datenmodell wurden immer mit Git commit und Git push dokumentiert.

## Tag 4 Funktionen der App heute
- Geräte können mit Name, Leistung und Laufzeit gespeichert werden.
- Der Code berechnet günstige Zeitfenster für den Start eines Geräts.
- Es gibt eine Funktion, um die beste Startzeit für heute zu finden.
- Es gibt einen Preisvergleich mit einer möglichen Solaranpassung.
- Die App speichert Empfehlungen in der Datenbank.
- Beim Entwickeln wurde regelmäßig `git add`, `git commit` und `git push` ausgeführt.

## Tag 5 Wetter und Zusatzdaten
- Es gibt auch einen Bereich für weltweites Wetter:
  - Suche nach Stadt
  - Anzeige von Temperatur, Wind, Luftfeuchtigkeit und Zustand
- Einige zusätzliche Daten-Funktionen sind vorhanden, zum Beispiel:
  - Verbrauchsdaten für Dresdner Stadtteile als Demo
  - Lebenserwartungsdaten für Länder als Beispiel
- Auch diese Teile sollten immer mit einem Git push gesichert werden.

##Tag 6 Aktueller Stand
- Die App ist ein Web-Demo mit Streamlit und kann lokal gestartet werden.
- `README.md` erklärt die Installation und dass Standarddaten zuerst als Mock verwendet werden.
- Für echte Preise kann man `ENERGY_API_URL` und `ENERGY_API_KEY` als Umgebungsvariablen setzen.
- `patch.py` ist ein kleines Hilfsskript, das eine kleine UI-Änderung in `Stromplaner.py` macht.
- Die beste Praxis ist: nach jeder Änderung git pushen.

## Wichtige Dateien
- `main.py` - einfacher Einstieg und Wetter-API-Demo
- `Stromplaner.py` - Hauptlogik und UI der App
- `README.md` - Installationshinweise und Projektbeschreibung
- `requirements.txt` - benötigte Python-Pakete
- `pro_strom.db` - lokale Datenbank mit Preisen und Empfehlungen

## Einfache Sprache zusammengefasst
- Das Projekt war ein Planer für Stromverbrauch.
- Es fing mit einer simplen Wetter-Demo an.
- Es wuchs zu einer App mit Energiepreisen, Geräteverwaltung und Empfehlungssystem.
- Heute kann die App Preise laden, Geräte speichern und Startzeiten vorschlagen.
- Und wichtig: Nach jeder Änderung an der App immer `git push` ausführen.
