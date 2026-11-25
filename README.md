# E-Paper Bilderrahmen für Home Assistant

Zeigt ausgewählte Inhalte aus Home Assistant auf einem **Waveshare 7.3" E6 PhotoPainter** (Spectra 6, 800 × 480) mit Raspberry Pi Zero an – komplett per Oberfläche einstellbar.

- **Wetter** mit 3-Tage-Vorschau
- **Müllabfuhr** (z. B. Waste Collection Schedule), Tonnenfarbe wird aus dem Namen erkannt
- **Kalender / Geburtstage** aus beliebig vielen Kalendern, doppelte Einträge werden zusammengefasst
- **Weitere Werte** – beliebige Entitäten (Temperaturen, Schlösser, Akkus …)
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
4. Adresse des Pi eingeben (z. B. `frame.local` oder die IP), dann Inhalte auswählen.

Inhalte ändern: *Geräte & Dienste → E-Paper Bilderrahmen → Konfigurieren*. Nach dem Speichern wird der Rahmen sofort neu gezeichnet.

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

MIT. Enthält die Schrift DejaVu Sans (Bitstream-Vera-Lizenz, siehe `fonts/LICENSE.txt`).
