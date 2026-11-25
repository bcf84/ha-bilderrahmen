#!/bin/bash
# Installiert den Bilderrahmen-Empfänger auf dem Raspberry Pi.
# Aufruf auf dem Pi:
#   curl -sSL https://raw.githubusercontent.com/bcf84/ha-bilderrahmen/main/pi/install.sh | bash
set -e

REPO="https://raw.githubusercontent.com/bcf84/ha-bilderrahmen/main/pi"
DIR="$HOME/bilderrahmen"
EPD_LIB="$HOME/RPi_Zero_PhotoPainter/7in3_e-Paper_E/python/lib"
PORT=8765

echo "=== Bilderrahmen-Empfänger einrichten ==="

if [ ! -d "$EPD_LIB/waveshare_epd" ]; then
  echo "FEHLER: Waveshare-Treiber nicht gefunden in $EPD_LIB"
  echo "Bitte zuerst die Waveshare-Demo nach ~/RPi_Zero_PhotoPainter entpacken."
  exit 1
fi

echo "1/4  Dateien laden ..."
mkdir -p "$DIR"
curl -fsSL "$REPO/frame_receiver.py" -o "$DIR/frame_receiver.py"
curl -fsSL "$REPO/frame_show.py"     -o "$DIR/frame_show.py"
curl -fsSL "$REPO/frame_screens.py"  -o "$DIR/frame_screens.py"
chmod +x "$DIR"/*.py

echo "     Akku-Messung (I2C) und WLAN-Werkzeuge vorbereiten ..."
sudo raspi-config nonint do_i2c 0 >/dev/null 2>&1 || true
sudo apt-get install -y -qq python3-smbus i2c-tools wireless-tools fonts-dejavu-core >/dev/null 2>&1 || true

echo "2/4  Alte stündliche Aufgabe entfernen (falls vorhanden) ..."
if crontab -l 2>/dev/null | grep -q frame_dashboard.py; then
  crontab -l 2>/dev/null | grep -v frame_dashboard.py | crontab -
fi

echo "3/4  Dienst einrichten (fragt evtl. nach deinem Passwort) ..."
sudo tee /etc/systemd/system/bilderrahmen.service > /dev/null << EOF
[Unit]
Description=Bilderrahmen-Empfänger für Home Assistant
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$DIR
Environment=EPD_LIB=$EPD_LIB
Environment=FRAME_PORT=$PORT
ExecStart=/usr/bin/python3 $DIR/frame_receiver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now bilderrahmen.service
sudo systemctl restart bilderrahmen.service

echo "4/4  Test ..."
sleep 3
if curl -fsS "http://127.0.0.1:$PORT/status" > /dev/null; then
  IP=$(hostname -I | awk '{print $1}')
  echo
  echo "=== Fertig. Der Rahmen wartet jetzt auf Bilder von Home Assistant. ==="
  echo "Adresse für Home Assistant:  $(hostname).local   (oder $IP)"
  echo "Port:                        $PORT"
else
  echo "Der Dienst antwortet nicht. Protokoll: journalctl -u bilderrahmen -n 30"
  exit 1
fi
