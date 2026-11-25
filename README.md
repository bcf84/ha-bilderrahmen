# E-Paper Bilderrahmen für Home Assistant

Zeigt ein frei gestaltbares Layout aus Home Assistant auf einem **Waveshare 7.3" E6 PhotoPainter** (Spectra 6, 800 × 480) mit Raspberry Pi Zero an.

- **Grafischer Layout-Editor** in der Seitenleiste („Bilderrahmen“): Elemente per Drag & Drop platzieren, Größe ziehen, Hilfslinien, Rückgängig, Live-Vorschau in den echten sechs Farben
- **Elemente:** Datum/Titel, Wetter jetzt, Wetterdetails, Wettervorhersage, Temperaturverlauf, Müllabfuhr, Kalender, Einzelwert, Werteliste, To-do-Liste, Text, Linie
- **Modernes Design:** Grau, Orange, Pastell und Verläufe werden aus den sechs Displayfarben gedithert (mit gemessener Spectra-6-Palette), Text und Icons bleiben gestochen scharf. Jost-Schrift, illustrierte Wettersymbole, Papier/Weiß/Dunkel, Akzentfarbe
- Knopf **„Jetzt aktualisieren“**, Vorschaubild und Status direkt in Home Assistant
- Der Rahmen wird nur neu gezeichnet, wenn sich etwas geändert hat

Home Assistant zeichnet das Bild und schickt es an einen kleinen Empfänger-Dienst auf dem Pi. Der Pi braucht dafür keinen Zugangstoken.

## 1. Empfänger auf dem Pi installieren

Voraussetzung: Die Waveshare-Demo liegt in `~/RPi_Zero_PhotoPainter` und SPI ist aktiviert.

```bash
curl -sSL https://raw.githubusercontent.com/bcf84/ha-bilderrahmen/main/pi/install.sh | bash
```

Am Ende zeigt das Skript Adresse und Port (Standard `8765`) an.

## 2. Integration in Home Assistant

1. Über HACS / Marketplace dieses Repository als benutzerdefiniertes Repository (Typ *Integration*) hinzufügen und herunterladen.
2. Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → E-Paper Bilderrahmen*.
4. Adresse des Pi eingeben (z. B. `frame.local` oder die IP), Einbaulage und Intervall wählen.
5. In der Seitenleiste **Bilderrahmen** öffnen und das Layout gestalten. „Speichern & anzeigen“ schickt es sofort an den Rahmen.

## Entitäten

| Entität | Zweck |
|---|---|
| `button.…_jetzt_aktualisieren` | Bild sofort neu zeichnen und anzeigen (auch für Automationen) |
| `image.…_vorschau` | aktuelles Bild, z. B. für eine Bild-Karte im Dashboard |
| `sensor.…_zuletzt_angezeigt` | Zeitpunkt der letzten Anzeige |
| `sensor.…_status` | Aktualisiert / Unverändert / Rahmen nicht erreichbar |

## Empfänger-Schnittstelle

- `POST /display?force=0|1` – PNG im Body, 800 × 480
- `GET /status` – Zustand als JSON
- `GET /current.png` – zuletzt angezeigtes Bild

Protokoll auf dem Pi: `journalctl -u bilderrahmen -f`

## Lizenz

MIT. Enthält die Schrift Jost (SIL Open Font License) und Material Design Icons (Pictogrammers Free License / Apache 2.0), siehe `fonts/`.
