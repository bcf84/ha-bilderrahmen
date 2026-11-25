#!/usr/bin/env python3
"""Eingebaute Hinweis-Bildschirme des Rahmens.

Aufruf: frame_screens.py low_battery|offline [Detail] [Drehung]
"""

import os
import sys
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

W, H = 800, 480
BLACK, WHITE, RED, BLUE = (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 0, 255)
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size, bold=False):
    path = FONTS[1 if bold else 0]
    return ImageFont.truetype(path, size) if os.path.isfile(path) else ImageFont.load_default()


def battery_icon(d, cx, cy):
    w, h = 220, 110
    x0, y0 = cx - w // 2, cy - h // 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=16, outline=BLACK, width=8)
    d.rounded_rectangle([x0 + w + 4, cy - 22, x0 + w + 22, cy + 22], radius=6, fill=BLACK)
    d.rounded_rectangle([x0 + 18, y0 + 18, x0 + 52, y0 + h - 18], radius=6, fill=RED)


def wifi_off_icon(d, cx, cy):
    for i, r in enumerate((150, 105, 60)):
        d.arc([cx - r, cy - r + 60, cx + r, cy + r + 60], start=225, end=315, fill=BLACK, width=14)
    d.ellipse([cx - 14, cy + 46, cx + 14, cy + 74], fill=BLACK)
    d.line([cx - 120, cy - 60, cx + 120, cy + 90], fill=RED, width=16)


def server_off_icon(d, cx, cy):
    for i in range(3):
        y = cy - 70 + i * 52
        d.rounded_rectangle([cx - 110, y, cx + 110, y + 40], radius=8, outline=BLACK, width=6)
        d.ellipse([cx + 70, y + 13, cx + 84, y + 27], fill=BLACK)
    d.line([cx - 130, cy - 90, cx + 130, cy + 100], fill=RED, width=16)


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "offline"
    detail = sys.argv[2] if len(sys.argv) > 2 else ""
    rotation = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].lstrip("-").isdigit() else 0
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    if kind == "low_battery":
        battery_icon(d, W // 2, 160)
        title, text = "Akku fast leer", "Bitte den Rahmen über USB-C laden."
        sub = f"Akkuspannung {detail}" if detail else ""
    elif detail == "wifi":
        wifi_off_icon(d, W // 2, 140)
        title, text = "Keine WLAN-Verbindung", "Der Rahmen versucht es automatisch weiter."
        sub = "Router und WLAN prüfen."
    else:
        server_off_icon(d, W // 2, 160)
        title, text = "Home Assistant nicht erreichbar", "Seit längerer Zeit kam kein neues Bild."
        sub = "Läuft Home Assistant? Ist die Integration eingerichtet?"
    d.text((W // 2, 300), title, font=font(40, True), fill=BLACK, anchor="mm")
    d.text((W // 2, 352), text, font=font(24), fill=BLACK, anchor="mm")
    if sub:
        d.text((W // 2, 390), sub, font=font(20), fill=BLUE, anchor="mm")
    d.text((W // 2, 450), f"Stand {datetime.now():%d.%m.%Y %H:%M}", font=font(16), fill=BLACK, anchor="mm")
    if rotation:
        img = img.rotate(rotation, expand=True)

    sys.path.insert(0, os.environ.get("EPD_LIB", os.path.expanduser("~/RPi_Zero_PhotoPainter/7in3_e-Paper_E/python/lib")))
    from waveshare_epd import epd7in3e  # noqa: E402

    epd = epd7in3e.EPD()
    epd.init()
    epd.display(epd.getbuffer(img))
    epd.sleep()


if __name__ == "__main__":
    main()
