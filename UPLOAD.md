# Erstveröffentlichung auf GitHub

Dieses ZIP enthält die **Dateien für das Repository-Verzeichnis**, keine fertige Mercedes-Integration. Die vorhandene Platzhalter-`README.md` wird ersetzt.

## Empfohlen: über Git hochladen

1. ZIP lokal entpacken.
2. Repository klonen und den **Inhalt** des entpackten Verzeichnisses in die Wurzel des geklonten Repositories kopieren.
3. Im geklonten Verzeichnis ausführen:

```bash
# Generierte Protobuf-Klassen aus einem festgelegten mbapi2020-Stand übernehmen.
# Dafür wird Internetzugang benötigt.
python3 scripts/vendor_mbapi_protos.py

# Vor dem Commit prüfen (ggf. mit PYTHONPATH=src):
PYTHONPATH=src python3 -m unittest discover -s tests -v

git status
git add .
git commit -m "Initial Mercedes connector prototype"
git push origin main
```

Die kompakte Online-Variante: `git clone https://github.com/pahenning/CarConnectivity-connector-mercedes.git`, in das Verzeichnis wechseln, anschließend die ZIP-Dateien dort hinein entpacken und die Befehle oben verwenden.

**Nicht die ZIP-Datei selbst als einzelne Datei bei GitHub hochladen.** GitHub entpackt hochgeladene ZIP-Dateien nicht automatisch. Auch kein `build/`, `dist/`, `.venv/`, `.netrc`, Tokens oder Fahrzeugdaten hochladen. Vor `git add` prüfen, dass keine Zugangsdaten in Dateien stehen.

## Status

- Der Source-Code ist als Entwicklungsstand strukturiert, Test- und Buildlauf waren offline erfolgreich.
- Ein vollständiger OAuth-PKCE-Erstlogin fehlt.
- Live-Zugriffe auf Mercedes sind nicht getestet.
- Zurzeit ist der Connector nur lesend. 
