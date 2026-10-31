"""Extract white-filled rectangles (candidate field boxes) with nearby text."""
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))

PLACEHOLDERS = set("DMYHI0123456789-/:.")


def is_placeholder(text):
    t = text.replace(" ", "")
    return bool(t) and all(c in PLACEHOLDERS for c in t) or t.upper() in (
        "INCAPITAL", "INCAPITALLETTERS", "INCAPITALLETTERSONLY", "CAPITAL", "LETTERS", "ONLY",
        "N", "U", "M", "B", "E", "R", "S", "O", "F", "D", "A", "Y", "E", "X", "T",
    )


def inside(w, r):
    cx = (w["x0"] + w["x1"]) / 2
    cy = (w["y0"] + w["y1"]) / 2
    return r[0] <= cx <= r[2] and r[1] <= cy <= r[3]


for p in data["pages"]:
    words = p["words"]
    rects = []
    for d in p["drawings"]:
        if d["fill"] is None:
            continue
        # near-white fill
        if not all(c > 0.97 for c in d["fill"]):
            continue
        for it in d["items"]:
            if it["t"] != "re":
                continue
            x0, y0, x1, y1 = it["r"]
            w, h = x1 - x0, y1 - y0
            if w < 18 or h < 7 or h > 120 or w > 590:
                continue
            rects.append((round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)))
    rects = sorted(set(rects), key=lambda r: (r[1], r[0]))
    print(f"\n===== PAGE {p['index']+1}: {len(rects)} candidate white boxes =====")
    for r in rects:
        inside_words = [w for w in words if inside(w, r)]
        text = " ".join(w["text"] for w in inside_words)
        left = [w for w in words if w["x1"] <= r[0] + 1 and abs((w["y0"] + w["y1"]) / 2 - (r[1] + r[3]) / 2) < 12]
        left.sort(key=lambda w: -w["x1"])
        label = " ".join(w["text"] for w in left[:6][::-1])
        above = [w for w in words if r[1] - 14 < w["y1"] <= r[1] + 2 and r[0] - 4 <= w["x0"] <= r[2]]
        above.sort(key=lambda w: w["x0"])
        alabel = " ".join(w["text"] for w in above)
        flag = "EMPTY" if not text.strip() else ("PH" if is_placeholder(text) else "text")
        print(f"  {r} w={r[2]-r[0]:6.1f} h={r[3]-r[1]:5.1f} {flag:5s} in='{text[:40]}' left='{label[:38]}' above='{alabel[:34]}'")
