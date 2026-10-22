#!/usr/bin/env bash
# Render/Oracle ke "Build Command" me ye use karo:
#
#   apt-get update && apt-get install -y tesseract-ocr && pip install -r requirements.txt && playwright install --with-deps chromium
#
# (Oracle Ubuntu VM par: sudo apt-get install -y tesseract-ocr)
#
# Ye script sirf reference/documentation ke liye hai.

apt-get update && apt-get install -y tesseract-ocr
pip install -r requirements.txt
playwright install --with-deps chromium
