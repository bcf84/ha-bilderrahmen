#!/usr/bin/env python3
"""Zeigt eine PNG-Datei auf dem Waveshare 7.3" E6 an. Aufruf: frame_show.py BILD.png"""

import os
import sys

EPD_LIB = os.environ.get(
    "EPD_LIB",
    os.path.expanduser("~/RPi_Zero_PhotoPainter/7in3_e-Paper_E/python/lib"),
)
sys.path.insert(0, EPD_LIB)

from PIL import Image, ImageOps  # noqa: E402
from waveshare_epd import epd7in3e  # noqa: E402

img = Image.open(sys.argv[1]).convert("RGB")
if img.size != (800, 480):
    img = ImageOps.fit(img, (800, 480))

epd = epd7in3e.EPD()
epd.init()
epd.display(epd.getbuffer(img))
epd.sleep()
