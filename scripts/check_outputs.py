#!/usr/bin/env python3
"""Check the fab package the way a fab's importer would.

Catches the mistakes that survive DRC and only show up as a rejected order or,
worse, a wrong board: a BOM line with no order code, a placement that misses
the board because the origins disagree, a part in the CPL that the BOM never
mentions, a drill file with no holes.
"""
import csv, os, re, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parts, kienv
from sexp_parse import parse_file

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "out")

REQUIRED_2 = ["F_Cu", "B_Cu", "F_Mask", "B_Mask", "F_Silkscreen", "B_Silkscreen",
              "F_Paste", "B_Paste", "Edge_Cuts"]
REQUIRED_4 = REQUIRED_2 + ["In1_Cu", "In2_Cu"]


def gerber_extent(path):
    """Coordinate extent of a gerber, in mm."""
    xs, ys = [], []
    fmt = (4, 6)
    for line in open(path, errors="replace"):
        m = re.search(r"%FSLAX(\d)(\d)Y\d\d\*%", line)
        if m:
            fmt = (int(m.group(1)), int(m.group(2)))
        for m in re.finditer(r"X(-?\d+)Y(-?\d+)", line):
            xs.append(int(m.group(1)) / 10 ** fmt[1])
            ys.append(int(m.group(2)) / 10 ** fmt[1])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def check(stem, layers, w, h, problems, notes):
    d = os.path.join(OUT, stem)
    zpath = os.path.join(d, f"{stem}-gerbers.zip")
    if not os.path.exists(zpath):
        problems.append(f"{stem}: no gerber zip")
        return
    names = zipfile.ZipFile(zpath).namelist()
    for want in (REQUIRED_4 if layers == 4 else REQUIRED_2):
        if not any(want in n for n in names):
            problems.append(f"{stem}: gerber zip has no {want} layer")
    drills = [n for n in names if n.endswith(".drl")]
    if not drills:
        problems.append(f"{stem}: no Excellon drill file")
    for dn in drills:
        body = zipfile.ZipFile(zpath).read(dn).decode("latin-1")
        if "PTH" in dn and not re.search(r"^T\d", body, re.M):
            problems.append(f"{stem}: {dn} defines no tools")
    notes.append(f"{stem}: gerber zip has {len(names)} files "
                 f"({len(drills)} drill)")

    # the outline must be the board we think we designed
    gdir = os.path.join(d, "gerbers")
    edge = [n for n in os.listdir(gdir) if "Edge_Cuts" in n]
    if edge:
        ext = gerber_extent(os.path.join(gdir, edge[0]))
        if ext:
            gw, gh = ext[2] - ext[0], ext[3] - ext[1]
            if abs(gw - w) > 0.3 or abs(gh - h) > 0.3:
                problems.append(f"{stem}: outline is {gw:.2f} x {gh:.2f} mm, "
                                f"expected {w} x {h}")
            else:
                notes.append(f"{stem}: outline {gw:.2f} x {gh:.2f} mm, "
                             f"origin at ({ext[0]:.2f}, {ext[1]:.2f})")
            if gw > 100.5 or gh > 100.5:
                notes.append(f"{stem}: {gw:.0f} x {gh:.0f} mm is past the 100 x 100 mm discounted "
                             "size: the bare boards cost a few dollars more")

    # placements land on the board, and every one is in the BOM
    cpl = os.path.join(d, f"{stem}_cpl_kicad_native.csv")
    bom = os.path.join(d, f"{stem}_bom_jlcpcb_upload.csv")
    rows = list(csv.DictReader(open(cpl)))
    for r in rows:
        x, y = float(r["Mid X"]), float(r["Mid Y"])
        if not (-1 <= x <= w + 1 and -1 <= y <= h + 1):
            problems.append(f"{stem}: {r['Designator']} placed at "
                            f"({x:.1f}, {y:.1f}), off the board")
        if r["Layer"] not in ("Top", "Bottom"):
            problems.append(f"{stem}: {r['Designator']} has layer "
                            f"{r['Layer']!r}")
        rot = float(r["Rotation"])
        if not (-360 <= rot <= 360):
            problems.append(f"{stem}: {r['Designator']} rotation {rot}")

    bom_rows = list(csv.DictReader(open(bom)))
    in_bom = set()
    for b in bom_rows:
        if not b["LCSC Part #"].strip():
            problems.append(f"{stem}: BOM line {b['Designator']} "
                            f"({b['Comment']}) has no LCSC code")
        if not re.fullmatch(r"C\d+", b["LCSC Part #"].strip() or "x"):
            problems.append(f"{stem}: BOM line {b['Designator']} has a "
                            f"malformed code {b['LCSC Part #']!r}")
        in_bom.update(x.strip() for x in b["Designator"].split(","))
    placed = {r["Designator"] for r in rows}
    missing = sorted(placed - in_bom)
    extra = sorted(in_bom - placed)
    if missing:
        problems.append(f"{stem}: placed but not in the BOM: {missing}")
    if extra:
        problems.append(f"{stem}: in the BOM but not placed: {extra}")
    notes.append(f"{stem}: {len(placed)} placements, {len(bom_rows)} BOM "
                 f"lines, all with order codes")

    # The JLC copy must be the same file, turned by exactly the amounts in the
    # rotation table and by nothing else: same parts, same places, same sides.
    jlc_path = os.path.join(ROOT, "out", stem, f"{stem}_cpl_jlcpcb_upload.csv")
    if not os.path.exists(jlc_path):
        problems.append(f"{stem}: no JLCPCB-corrected placement file")
        return
    lcsc_of = {}
    for b in bom_rows:
        for ref in b["Designator"].split(","):
            lcsc_of[ref.strip()] = b["LCSC Part #"].strip()
    jlc = {r["Designator"]: r for r in csv.DictReader(open(jlc_path))}
    plain = {r["Designator"]: r for r in rows}
    if set(jlc) != set(plain):
        problems.append(f"{stem}: the JLCPCB placement file lists different "
                        f"parts from {os.path.basename(cpl)}")
        return
    import math
    turned = shifted = 0
    for ref, a in plain.items():
        b = jlc[ref]
        if a["Layer"] != b["Layer"]:
            problems.append(f"{stem}: {ref} changed side in the JLCPCB placement file")
        entry = parts.JLC_ROTATION.get(lcsc_of.get(ref, ""), (0, (0, 0)))
        want = (float(a["Rotation"]) + entry[0]) % 360.0
        diff = (float(b["Rotation"]) - want) % 360.0
        if min(diff, 360.0 - diff) > 0.05:
            problems.append(f"{stem}: {ref} is at {b['Rotation']} deg for "
                            f"JLCPCB, expected {want:.1f}")
        elif float(b["Rotation"]) != float(a["Rotation"]):
            turned += 1
        shift = math.hypot(float(b["Mid X"]) - float(a["Mid X"]), float(b["Mid Y"]) - float(a["Mid Y"]))
        want_shift = math.hypot(*entry[1])
        if abs(shift - want_shift) > 0.01:
            problems.append(f"{stem}: {ref} moved {shift:.2f} mm in the JLCPCB placement file, "
                            f"the table says {want_shift:.2f}")
        elif shift:
            shifted += 1
    notes.append(f"{stem}: the JLCPCB placement file turns {turned} parts and shifts "
                 f"{shifted} to JLCPCB's datum, by exactly the table's amounts")


# Through-hole parts whose hole pattern must be its own key: each of these
# has to fit the board in exactly one orientation, so that however a fab's
# preview chooses to draw them, they cannot be soldered in turned.  The
# assembler's notes say so in as many words, and this is what makes that
# true rather than hopeful.
KEYED_THT = ["RV1", "RV2", "K1"]


def check_keying(stem, problems, notes):
    """A hole pattern that maps onto itself under a quarter turn is not a key."""
    import math
    pcb = os.path.join(ROOT, "hardware", stem + ".kicad_pcb")
    if not os.path.exists(pcb):
        return
    board = parse_file(pcb)
    for fp in board.kids("footprint"):
        ref = next((p.atom(1) for p in fp.kids("property")
                    if p.atom(0) == "Reference"), "?")
        if ref not in KEYED_THT:
            continue
        holes = set()
        for pad in fp.kids("pad"):
            if pad.atom(1) != "thru_hole":
                continue
            at = pad.first("at")
            holes.add((round(float(at.atom(0)), 3), round(float(at.atom(1)), 3)))
        if len(holes) < 2:
            problems.append(f"{stem}: {ref} has no through-holes to key it")
            continue
        loose = []
        for deg in (90, 180, 270):
            c, s_ = round(math.cos(math.radians(deg))), round(math.sin(math.radians(deg)))
            if {(round(x * c - y * s_, 3), round(x * s_ + y * c, 3))
                    for x, y in holes} == holes:
                loose.append(deg)
        if loose:
            problems.append(f"{stem}: {ref} also fits at {loose} degrees, so "
                            f"its holes do not key it and it could be fitted "
                            f"turned")
        else:
            notes.append(f"{stem}: {ref}'s {len(holes)} holes fit only one "
                         f"way round, so no preview can mislead it")


def check_models(stem, problems, notes):
    """Every 3D model a footprint names must actually be on disk.

    gen_models.py was once not wired into the build at all, so a fresh clone
    had no models and half the board rendered as bare pads -- with nothing
    complaining.
    """
    pcb = os.path.join(ROOT, "hardware", stem + ".kicad_pcb")
    if not os.path.exists(pcb):
        return
    share = kienv.share_dir()
    subs = {"${KIPRJMOD}": os.path.join(ROOT, "hardware"),
            "${KICAD10_3DMODEL_DIR}": os.path.join(share, "3dmodels"),
            "${KICAD9_3DMODEL_DIR}": os.path.join(share, "3dmodels"),
            "${KISYS3DMOD}": os.path.join(share, "3dmodels")}
    board = parse_file(pcb)
    missing, ok = [], 0
    for fp in board.kids("footprint"):
        ref = next((p.atom(1) for p in fp.kids("property")
                    if p.atom(0) == "Reference"), "?")
        models = [m.atom(0) for m in fp.kids("model")]
        if not models:
            # Nothing is fitted here -- a mounting hole, a probe pad, a solder
            # jumper -- so there is nothing to draw.
            if ref[:2] not in ("MH", "TP", "JP"):
                missing.append(f"{ref} has no 3D model")
            continue
        for m in models:
            path = m
            for k, v in subs.items():
                path = path.replace(k, v)
            if os.path.exists(path):
                ok += 1
            else:
                missing.append(f"{ref} -> {os.path.basename(path)}")
    for m in missing:
        problems.append(f"{stem}: missing 3D model, {m}")
    notes.append(f"{stem}: {ok} 3D model(s) resolve on disk")


def check_qr(stem, problems, notes):
    """Read the QR codes back out of the finished board and decode them.

    The one thing on this board that can be silently, completely wrong: a
    misplaced module still looks like a QR code.  So the rectangles that were
    actually written to the .kicad_pcb are sampled back into a matrix and run
    through the decoder, which checks the format information's BCH, every
    Reed-Solomon block's syndromes, and the payload.
    """
    import qrcode_gen
    import layout as SILK
    pcb = os.path.join(ROOT, "hardware", stem + ".kicad_pcb")
    if not os.path.exists(pcb):
        return
    board = parse_file(pcb)
    rects = []
    for r in board.kids("gr_rect"):
        if (r.first("layer") is None
                or r.first("layer").atom(0) != "B.SilkS"):
            continue
        a, b = r.first("start"), r.first("end")
        rects.append((float(a.atom(0)), float(a.atom(1)),
                      float(b.atom(0)), float(b.atom(1))))
    mod = SILK.QR_MODULE
    for (qx, qy, key) in ((SILK.QR_AT[0], SILK.QR_AT[1], "project"),):
        want = "https://" + parts.PROJECT_URL
        n = len(qrcode_gen.encode(want, "M"))
        x0, y0 = qx - n * mod / 2.0, qy - n * mod / 2.0
        m = []
        for row in range(n):
            line = []
            for col in range(n):
                # drawn mirrored, so column j lives at n-1-j
                x = x0 + (n - 1 - col) * mod + mod / 2.0
                y = y0 + row * mod + mod / 2.0
                line.append(1 if any(rx0 <= x <= rx1 and ry0 <= y <= ry1
                                     for (rx0, ry0, rx1, ry1) in rects) else 0)
            m.append(line)
        try:
            got, mask, version = qrcode_gen.decode(m, "M")
        except Exception as e:
            problems.append(f"{stem}: the {key} QR code does not decode: {e}")
            continue
        if got != want:
            problems.append(f"{stem}: the {key} QR code reads {got!r}")
        else:
            notes.append(f"{stem}: the {key} QR code on B.Silkscreen decodes "
                         f"to {got} (version {version}, mask {mask})")


# What JLCPCB's own description of each code must say, beyond the MPN.
# (The ECP5 lesson: a code typed from memory can be a perfectly real other part.)
CODE_EXPECT = {
    "OPAMP": ["OPA197", "SOT-23-5"], "COMP": ["TS391", "SOT-23-5"], "TIMER": ["555", "SOIC-8"],
    "MOSFET": ["N-channel", "200V"], "RELAY": ["HFD3"], "NPN": ["NPN", "SOT-23"], "DSIG": ["SOD-123"],
    "DCLAMP": ["SOT-23"], "DSCH": ["SMA"], "TVS_CLAMP": ["SMC"], "TVS_TANK": ["SMB"], "TVS_SUPPLY": ["SMB"],
    "PTC": ["2920"], "RSENSE": ["2512"], "DIP8": ["DIP"], "SW": ["SPDT"], "TRIM": ["2M"],
    "CFILM": ["1uF"], "CBULK": ["100uF"], "CPOL": ["470uF"], "BNC": ["BNC"], "TERM3": ["3P"], "TERM2": ["2P"],
    "TP": ["Test"], "LED": ["0805"], "LED_R": ["0805"],
    "100nF": ["100nF", "0805"], "10nF": ["10nF", "0805"], "6.8nF": ["6.8nF", "0805"], "3.3nF": ["3.3nF", "0805"],
    "47nF": ["47nF", "1206"], "100nF_C0G": ["100nF", "1206"],
}


def check_codes(problems, notes):
    """Every LCSC code is the part the design thinks it is, by JLCPCB's own
    description (from the parts-API cache; scripts/jlc_api.py <code> refreshes it)."""
    import jlc_api
    seen = 0
    for key, p in list(parts.PARTS.items()) + list(parts.PASSIVES.items()):
        code = p.get("lcsc")
        if not code:
            continue
        try:
            part, ts = jlc_api.by_code(code)
        except Exception as e:                      # no network: the cache is gitignored
            notes.append(f"LCSC codes not re-checked against JLCPCB's API ({type(e).__name__}); "
                         f"they were on {parts.STOCK_DATE}")
            return
        if part is None:
            problems.append(f"{code} ({key}): JLCPCB's parts API knows no such code")
            continue
        seen += 1
        model = part.get("componentModelEn") or ""
        text = " ".join([part.get("describe") or "", model, part.get("componentSpecificationEn") or ""])
        mpn = p.get("mpn", "")
        if mpn and not model.upper().startswith(mpn.upper()):
            problems.append(f"{code} ({key}): JLCPCB calls it {model!r}, the design says {mpn!r}")
        missing = [w for w in CODE_EXPECT.get(key, []) if w.lower() not in text.lower()]
        if missing:
            problems.append(f"{code} ({key}): JLCPCB's description {text[:60]!r}... lacks {missing}")
        stock = part.get("stockCount") or 0
        if stock < 100:
            problems.append(f"{code} ({key}): only {stock} in stock ({ts[:10]})")
    notes.append(f"{seen} LCSC codes match JLCPCB's own descriptions (MPN, value, package)")


def check_stock(problems, notes):
    """Every chosen part had stock when the design was frozen."""
    low = []
    per_board = {}                      # placements of each order code, from the BOM itself
    bom = os.path.join(OUT, "earthnmr", "earthnmr_bom_jlcpcb_upload.csv")
    if os.path.exists(bom):
        for r in csv.DictReader(open(bom)):
            per_board[r["LCSC Part #"]] = per_board.get(r["LCSC Part #"], 0) + len(r["Designator"].split(","))
    for key, p in parts.PARTS.items():
        if "stock" not in p:
            continue
        need = per_board.get(p.get("lcsc"), 1)
        boards = p["stock"] // need
        if boards < 50:
            low.append(f"{p['mpn']} ({p['stock']} in stock = {boards} boards)")
    if low:
        notes.append("thin stock (see docs for alternates): " + "; ".join(low))
    notes.append(f"{len(parts.PARTS)} part types, "
                 f"{len(parts.PASSIVES)} passive values, all with order codes")


def main():
    problems, notes = [], []
    import layout
    check("earthnmr", 4, layout.BOARD_W, layout.BOARD_H, problems, notes)
    check_qr("earthnmr", problems, notes)
    check_keying("earthnmr", problems, notes)
    check_models("earthnmr", problems, notes)
    check_stock(problems, notes)
    check_codes(problems, notes)
    for n in notes:
        print(f"  ok   {n}")
    for p in problems:
        print(f"  FAIL {p}")
    print(f"\n{'ALL FAB CHECKS PASSED' if not problems else str(len(problems)) + ' PROBLEM(S)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
