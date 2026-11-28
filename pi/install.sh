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
sudo apt-get install -y -qq python3-smbus i2c-tools wireless-tools iw fonts-dejavu-core >/dev/null 2>&1 || true

echo "     WLAN-Stromsparmodus abschalten (verhindert Verbindungsabbrüche) ..."
sudo mkdir -p /etc/NetworkManager/conf.d
printf '[connection]\nwifi.powersave = 2\n' | sudo tee /etc/NetworkManager/conf.d/bilderrahmen-wifi-powersave.conf > /dev/null
if command -v nmcli > /dev/null; then
  nmcli -t -f NAME,TYPE connection show 2>/dev/null | awk -F: '$2 ~ /wireless/ {print $1}' | while read -r c; do
    sudo nmcli connection modify "$c" 802-11-wireless.powersave 2 >/dev/null 2>&1 || true
  done
fi
sudo iw dev wlan0 set power_save off >/dev/null 2>&1 || true

echo "     Freigabe für automatische Reparaturen (WLAN, Neustart, Herunterfahren bei leerem Akku) ..."
SUDOERS=/etc/sudoers.d/bilderrahmen
TMP=$(mktemp)
echo "$USER ALL=(root) NOPASSWD: $(command -v shutdown), $(command -v reboot), $(command -v nmcli || echo /usr/bin/nmcli), $(command -v systemctl) restart NetworkManager" > "$TMP"
if sudo visudo -cf "$TMP" > /dev/null; then
  sudo install -m 0440 -o root -g root "$TMP" "$SUDOERS"
else
  echo "     (Freigabe übersprungen – Prüfung fehlgeschlagen)"
fi
rm -f "$TMP"

echo "     Strom sparen: Bluetooth und LED aus, sparsamer CPU-Takt ..."
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
NEED_REBOOT=0
for line in "dtoverlay=disable-bt" "dtparam=act_led_trigger=none" "dtparam=act_led_activelow=on"; do
  if ! grep -qx "$line" "$CFG"; then echo "$line" | sudo tee -a "$CFG" > /dev/null; NEED_REBOOT=1; fi
done
sudo systemctl disable --now hciuart.service bluetooth.service >/dev/null 2>&1 || true
sudo tee /etc/systemd/system/bilderrahmen-power.service > /dev/null << 'EOF2'
[Unit]
Description=Bilderrahmen: sparsamer CPU-Takt
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo powersave > "$g"; done'
[Install]
WantedBy=multi-user.target
EOF2
sudo systemctl daemon-reload
sudo systemctl enable --now bilderrahmen-power.service >/dev/null 2>&1 || true

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
  if [ "$NEED_REBOOT" = "1" ]; then
    echo
    echo "Der Pi startet in 10 Sekunden neu, damit Bluetooth und LED aus sind."
    sleep 10
    sudo reboot
  fi
else
  echo "Der Dienst antwortet nicht. Protokoll: journalctl -u bilderrahmen -n 30"
  exit 1
fi
