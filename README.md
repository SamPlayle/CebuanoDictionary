# Wolff Cebuano Dictionary

An offline phone app for John U. Wolff, *A Dictionary of Cebuano Visayan* (1972), from the Project Gutenberg edition (#40074).

Open the GitHub Pages address on your phone, then choose **Install app** (Chrome) or **Share → Add to Home Screen** (Safari). It then opens in its own window and works without a connection.

Search features:
- Forgiving spelling: e = i, o = u, accents optional
- l/w and dropped-l dialect forms (uwan → ulan, bay → balay)
- Affixed words find their root, including nasal assimilation (pamahaw → báhaw)
- Headword matches first; English search via the ENG toggle

`build/` holds the scripts: `python build.py 40074-h.htm db.json`, then `python assemble.py` (needs Pillow).
