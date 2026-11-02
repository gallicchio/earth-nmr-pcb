#!/usr/bin/env python3
"""Produce everything a fab needs: gerbers, drill files, BOM, CPL and prints.

The BOM and CPL are written in the column layout JLCPCB expects, which
NextPCB and CircuitHub also accept.
"""
import csv, io, os, re, shutil, subprocess, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_pdf, kienv, parts

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
HW = os.path.join(ROOT, "hardware")
OUT = os.path.join(ROOT, "out")

GERBER_LAYERS_2 = ("F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,"
                   "F.Mask,B.Mask,Edge.Cuts")
GERBER_LAYERS_4 = ("F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,"
                   "F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts")

# Parts whose orientation in the CPL is worth a glance in the fab's preview:
# anything that is not rotationally symmetric.
ORIENTATION_SENSITIVE = (["Q1", "Q2", "Q3", "K1", "SW1", "SW2", "SW3", "SW4", "RV1", "RV2", "U11", "F1"]
                         + [f"U{i}" for i in range(1, 11)] + [f"D{i}" for i in range(1, 15)]
                         + [f"LED{i}" for i in range(1, 5)] + ["C1", "C2", "C5"] + [f"J{i}" for i in (1, 2, 3, 4, 5, 7, 8)])
IMAGES = os.path.join(ROOT, "docs", "images")
PNG_DPI = 170
import layout as _place
P_BOARD = max(_place.BOARD_W, _place.BOARD_H)


# Every KiCad output stamps the moment it was written, so an unchanged design
# produces different bytes on every build.  Pinning the stamp to the board's
# own date makes the fab files reproducible, which is what lets a diff on this
# repository mean something.  Fabs read the geometry, not the stamp.
STAMP_DATE = parts.BOARD_DATE
STAMP_TIME = f"{STAMP_DATE}T00:00:00+00:00"
TIMESTAMP_PATTERNS = [
    (re.compile(r"(%TF\.CreationDate,)[^*]*"), r"\g<1>" + STAMP_TIME),
    (re.compile(r"(TF\.CreationDate,)[-\d:T+]+"), r"\g<1>" + STAMP_TIME),
    (re.compile(r'("CreationDate":\s*")[^"]*'), r"\g<1>" + STAMP_TIME),
    (re.compile(r"(date )\d{4}-\d\d-\d\d[T ][\d:]+"), r"\g<1>" + STAMP_DATE),
    (re.compile(r"(- Date: ).*"), r"\g<1>" + STAMP_DATE),
    (re.compile(r'(\(date ")[^"]*'), r"\g<1>" + STAMP_DATE),
]


# A PDF carries byte offsets in its cross-reference table, so its date can
# only be replaced by something exactly as long.
PDF_DATE = re.compile(rb"(/(?:Creation|Mod)Date \(D:)(\d{4}:\d\d:\d\d:)[\d:]{8}")
STEP_DATE = re.compile(r"('[^']*\.step',')[\dT:-]+")


def normalise_timestamps(path):
    if path.endswith(".pdf"):
        raw = open(path, "rb").read()
        out = PDF_DATE.sub(rb"\g<1>\g<2>00:00:00", raw)
        if out != raw:
            open(path, "wb").write(out)
        return True
    try:
        body = open(path, encoding="latin-1").read()
    except OSError:
        return False
    out = body
    for pat, repl in TIMESTAMP_PATTERNS:
        out = pat.sub(repl, out)
    if path.endswith(".step"):
        out = STEP_DATE.sub(r"\g<1>" + STAMP_DATE + "T00:00:00", out)
    if out != body:
        open(path, "w", encoding="latin-1").write(out)
    return True


def board_files(stem):
    return (os.path.join(HW, stem + ".kicad_pcb"),
            os.path.join(HW, stem + ".kicad_sch"))


def export_fab(stem, layers):
    pcb, _ = board_files(stem)
    gdir = os.path.join(OUT, stem, "gerbers")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir, exist_ok=True)
    kienv.cli("pcb", "export", "gerbers",
              "--layers", GERBER_LAYERS_4 if layers == 4 else GERBER_LAYERS_2,
              "--no-protel-ext", "--subtract-soldermask",
              "--use-drill-file-origin", "-o", gdir + os.sep, pcb)
    kienv.cli("pcb", "export", "drill", "--format", "excellon",
              "--drill-origin", "plot", "--excellon-units", "mm",
              "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2",
              "-o", gdir + os.sep, pcb)
    for name in sorted(os.listdir(gdir)):
        normalise_timestamps(os.path.join(gdir, name))
    zpath = os.path.join(OUT, stem, f"{stem}-gerbers.zip")
    fixed = zipfile.ZipInfo.from_file  # noqa: F841  (documents the intent)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(gdir)):
            info = zipfile.ZipInfo(name, date_time=tuple(int(v) for v in STAMP_DATE.split("-")) + (0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(gdir, name), "rb") as fh:
                z.writestr(info, fh.read())
    return zpath, sorted(os.listdir(gdir))


def export_cpl(stem, bom_lines):
    """Pick-and-place in JLCPCB's column layout, twice.

    `<stem>_cpl_kicad_native.csv` is KiCad-canonical: every angle is the one
    in the board file.  `<stem>_cpl_jlcpcb_upload.csv` is the same file with
    JLCPCB's own per-part rotation offsets applied, because JLC places from
    its drawing of the part rather than from ours -- see parts.JLC_ROTATION.
    """
    pcb, _ = board_files(stem)
    raw = os.path.join(OUT, stem, "_pos.csv")
    kienv.cli("pcb", "export", "pos", "--format", "csv", "--units", "mm",
              "--side", "both", "--use-drill-file-origin", "--exclude-dnp",
              "-o", raw, pcb)
    rows = list(csv.DictReader(open(raw)))
    os.remove(raw)

    lcsc_of = {}
    for line in bom_lines:
        for ref in line["Designator"].split(","):
            lcsc_of[ref.strip()] = line["LCSC Part #"]

    def write(path, correct):
        """The JLCPCB copy turns each part by its table angle and moves it by
        its table datum shift (JLCPCB's origin for the part, in KiCad's
        footprint frame), rotated into board coordinates by KiCad's angle."""
        import math
        turned = []
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            for r in rows:
                rot = float(r["Rot"])
                x, y = float(r["PosX"]), float(r["PosY"])
                if correct:
                    d, (dx, dy) = parts.JLC_ROTATION.get(lcsc_of.get(r["Ref"], ""), (0, (0, 0)))[:2]
                    if d or dx or dy:
                        a = math.radians(rot)
                        # the pos file's y is up (drill origin at the bottom-left)
                        x += dx * math.cos(a) - dy * math.sin(a)
                        y += dx * math.sin(a) + dy * math.cos(a)
                        rot = (rot + d) % 360.0
                        turned.append(r["Ref"])
                w.writerow([r["Ref"], f'{x:.4f}', f'{y:.4f}',
                            "Top" if r["Side"].lower().startswith("t")
                            else "Bottom", f'{rot:.1f}'])
        return turned

    path = os.path.join(OUT, stem, f"{stem}_cpl_kicad_native.csv")
    write(path, False)
    jlc = os.path.join(OUT, stem, f"{stem}_cpl_jlcpcb_upload.csv")
    turned = write(jlc, True)
    return path, jlc, len(rows), turned


def by_lcsc():
    """Every order code the parts table knows, indexed by the code itself.

    The schematic already carries an LCSC field on every symbol, so the BOM is
    built from that rather than from a list of designators here -- adding a
    part is then one edit in parts.py plus one placement, and there is no
    second table to forget.
    """
    out = {}
    for key, p in list(parts.PARTS.items()) + [(k, v) for k, v in
                                               parts.PASSIVES.items()]:
        if p.get("lcsc"):
            out[p["lcsc"]] = p
    return out


def lcsc_for(code):
    p = by_lcsc().get(code)
    if not p:
        return "", 0.0, "extended"
    return p.get("mpn", ""), p.get("price", 0.0), p.get("jlc_type", "extended")


def export_bom(stem):
    _, sch = board_files(stem)
    raw = os.path.join(OUT, stem, "_bom.csv")
    kienv.cli("sch", "export", "bom", "--fields",
              "Reference,Value,Footprint,LCSC,${QUANTITY}",
              "--labels", "Reference,Value,Footprint,LCSC,Qty",
              "--group-by", "Value,Footprint,LCSC", "--exclude-dnp",
              "--ref-range-delimiter", "", "-o", raw, sch)
    groups = list(csv.DictReader(open(raw)))
    os.remove(raw)

    lines, unknown, total = [], [], 0.0
    for g in groups:
        refs = [r.strip() for r in g["Reference"].split(",") if r.strip()]
        value, fp, lcsc = g["Value"], g["Footprint"], g["LCSC"].strip()
        mpn, price, jlc = lcsc_for(lcsc)
        if not lcsc:
            unknown.append(f"{','.join(refs)} ({value})")
        qty = len(refs)
        total += price * qty
        lines.append({"Comment": value, "Designator": ",".join(refs),
                      "Footprint": fp.split(":")[-1], "LCSC Part #": lcsc,
                      "MPN": mpn, "Qty": qty, "Unit $": f"{price:.4f}",
                      "Ext $": f"{price * qty:.3f}", "JLC": jlc})
    lines.sort(key=lambda r: (r["Designator"][0], len(r["Designator"]),
                              r["Designator"]))

    path = os.path.join(OUT, stem, f"{stem}_bom_jlcpcb_upload.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["Comment", "Designator", "Footprint",
                                "LCSC Part #"], extrasaction="ignore")
        w.writeheader()
        for r in lines:
            w.writerow(r)
    full = os.path.join(OUT, stem, f"{stem}_bom_costed.csv")
    with open(full, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["Comment", "Designator", "Footprint",
                                "LCSC Part #", "MPN", "Qty", "Unit $",
                                "Ext $", "JLC"])
        w.writeheader()
        for r in lines:
            w.writerow(r)
    return path, full, lines, total, unknown


ASSEMBLY_NOTES = """EARTH'S FIELD NMR -- notes for the assembler
=========================================

PLACEMENTS
  Use {stem}_cpl_jlcpcb_upload.csv for JLCPCB.  It is {stem}_cpl_kicad_native.csv
  with JLCPCB's own per-part rotations and datum offsets applied; use the native
  file anywhere else.  Every part is on the top side.

U1-U10 -- OPA197 (U1-U7) and TS391 (U8-U10) in SOT-23-5, all at the same
  orientation: pins 3, 2, 1 along the TOP edge of the package, 4 and 5 along the
  bottom.  Each sits inside a silkscreen triangle pointing right; pin 1 is the
  upper-right pad, toward the triangle's point.
U11 -- NE555 in SOIC-8, pin 1 at the upper left (the silkscreen dot).

Q1 -- IRFS4227 in D2PAK (TO-263-2): the tab (drain) up, the two leads down.
Q2, Q3 -- MMBT3904 in SOT-23, collector pad up, inside a silkscreen circle.
D12 -- BAV99 in SOT-23: pin 3 (the common) up.

K1 -- HFD3/12 relay, through-hole; pin 1 (the coil's +) is the square pad, at
  the upper right of the two rows.
SW1 -- KingTek DSIC08 eight-way DIP switch; its ON side faces DOWN (toward
  pads 1-8, away from the TANK+ line).  The silkscreen says ON and OFF.
SW2, SW3, SW4 -- MSK12C02 slide switches; their two posts key them.
RV1, RV2 -- 3362P trimmers, keyed by their three holes.
C50-C52 -- 1 uF film capacitors, 5 mm pitch, through-hole, unpolarised.

J1, J3 -- 3-way 5 mm screw terminals; J2 -- 2-way.  The wire openings face
  the board edge: J1's the top edge, J2's and J3's the left edge.
J4, J5, J7, J8 -- BNC jacks, through-hole.  The barrel points OFF the board
  edge: J4 off the top, J5 off the right, J7 and J8 off the bottom.

D1-D14, LED1-LED4, C1, C2, C5 -- polarised; the cathode / negative end is pad 1,
  the end the footprint's silkscreen bar marks.  D9 (SMBJ12CA) is bidirectional.
TP1-TP21, TP100-TP103 -- RH-5019 test loops (SMD).
"""


def export_assembly_notes(stem):
    path = os.path.join(OUT, stem, f"{stem}-assembly-notes.txt")
    with open(path, "w") as fh:
        fh.write(ASSEMBLY_NOTES.format(stem=stem))
    return path


def export_prints(stem, layers):
    pcb, sch = board_files(stem)
    d = os.path.join(OUT, stem)
    made = []
    kienv.cli("sch", "export", "pdf", "--black-and-white", "-o",
              os.path.join(d, f"{stem}-schematic.pdf"), sch)
    # The assembly drawings fill a Letter page, centred, their scale printed
    # (fit_pdf.py; CLAUDE_PCB.md, "Every page fits what is on it"): kicad-cli
    # plots the board 1:1 where it lies on its A4 sheet, which put this one in
    # the sheet's top-left corner, hanging off the page.  No frame: the drawing
    # is the board, and the caption names it.
    title = f"{parts.BOARD_NAME} rev {parts.REV}, {parts.BOARD_DATE}"
    for side, lay, mirror, what in (
            ("top", "F.Fab,F.Silkscreen,Edge.Cuts", False, "top (F.Fab, F.Silkscreen, Edge.Cuts)"),
            ("bottom", "B.Silkscreen,Edge.Cuts", True, "bottom, seen from below (mirrored)")):
        path = os.path.join(d, f"{stem}-assembly-{side}.pdf")
        kienv.cli("pcb", "export", "pdf", "--mode-single", "--black-and-white",
                  *(["--mirror"] if mirror else []), "--layers", lay, "-o", path, pcb)
        fit_pdf.fit(path, path, caption=f"{title}: {what}, scale {{scale}}:1")
        # the back has nothing past the board's edge (the front's F.Fab has the BNC barrels), so this
        # wide board fills the page's width with slack above and below, and the caption in the bottom
        # margin moves the drawn box's centre: allow for the caption, not for a drawing off centre
        if not fit_pdf.check(path, off_max=0.03 if side == "top" else 0.065):
            raise SystemExit(f"{path} does not fill its page")
    for name in os.listdir(d):
        if name.endswith(".pdf"):
            normalise_timestamps(os.path.join(d, name))


def pdf_to_png(pdf, png, dpi=PNG_DPI, crop=False):
    """Rasterise page 1, optionally cropped to the board.

    The crop hunts for ink rather than assuming a corner: a mirrored plot of a
    back layer lands on the other side of the page, which is how an earlier
    version of this quietly produced a blank picture of the back silkscreen.
    Every view includes Edge.Cuts, so the ink is the board outline and the
    result is the same every build.
    """
    if not shutil.which("pdftoppm"):
        return False
    stem = png[:-4] if png.endswith(".png") else png
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", "1", "-l", "1",
                    "-singlefile", pdf, stem], check=True, capture_output=True)
    if not os.path.exists(png):
        return False
    if crop:
        try:
            from PIL import Image
        except ImportError:
            return True
        im = Image.open(png).convert("L")
        box = im.point(lambda v: 0 if v > 220 else 255).getbbox()
        if box:
            pad = int(round(1.0 * dpi / 25.4))
            im = Image.open(png).crop((max(0, box[0] - pad),
                                       max(0, box[1] - pad),
                                       min(im.width, box[2] + pad),
                                       min(im.height, box[3] + pad)))
            im.save(png)
    return True


def export_images(stem, layers):
    """PNGs of the sheet and both sides, plus 3D renders."""
    pcb, sch = board_files(stem)
    d = os.path.join(OUT, stem)
    os.makedirs(IMAGES, exist_ok=True)
    made, skipped = [], []

    # Flat views, via PDF so the stroke font comes out right: both sides, the
    # silkscreen alone, and the two inner planes.
    views = {
        f"{stem}-top": ("F.Cu,F.Silkscreen,Edge.Cuts", False),
        f"{stem}-bottom": ("B.Cu,B.Silkscreen,Edge.Cuts", True),
        f"{stem}-silk-top": ("F.Silkscreen,Edge.Cuts", False),
        f"{stem}-silk-bottom": ("B.Silkscreen,Edge.Cuts", True),
        f"{stem}-in1-ground": ("In1.Cu,Edge.Cuts", False),
        f"{stem}-in2-plus15": ("In2.Cu,Edge.Cuts", False),
    }
    for name, (lay, mirror) in views.items():
        tmp = os.path.join(d, "_" + name + ".pdf")
        args = ["pcb", "export", "pdf", "--mode-single", "--black-and-white",
                "--layers", lay, "-o", tmp, pcb]
        if mirror:
            args.insert(-1, "--mirror")
        kienv.cli(*args)
        png = os.path.join(IMAGES, name + ".png")
        (made if pdf_to_png(tmp, png, crop=True)
         else skipped).append(name)
        os.remove(tmp)

    png = os.path.join(IMAGES, "schematic.png")
    (made if pdf_to_png(os.path.join(d, f"{stem}-schematic.pdf"), png, 90)
     else skipped).append("schematic")

    # 3D
    renders = (
        ("render-top", ["--side", "top"]),
        ("render-bottom", ["--side", "bottom"]),
        ("render-iso", ["--side", "top", "--perspective",
                        "--rotate", "-30,0,-20", "--zoom", "0.75"]))
    for name, extra in renders:
        out = os.path.join(IMAGES, f"{stem}-{name}.png")
        # "basic" rather than "high": the raytraced setting samples
        # stochastically, so an unchanged board renders differently every time
        # and the image churns in git.  The difference is soft shadows.
        kienv.cli("pcb", "render", "--width", "1400", "--height", "1150",
                  "--quality", "basic", "--background", "opaque",
                  *extra, "-o", out, pcb)
        made.append(name)

    step = os.path.join(d, f"{stem}.step")
    kienv.cli("pcb", "export", "step", "--no-dnp", "--subst-models",
              "-o", step, pcb, check=False)
    normalise_timestamps(step)
    stats = os.path.join(d, f"{stem}-stats.txt")
    kienv.cli("pcb", "export", "stats", "-o", stats, pcb, check=False)
    normalise_timestamps(stats)
    return made, skipped


def run(stem, layers):
    os.makedirs(os.path.join(OUT, stem), exist_ok=True)
    zpath, names = export_fab(stem, layers)
    bom, costed, lines, total, unknown = export_bom(stem)
    cpl, jlc_cpl, ncpl, turned = export_cpl(stem, lines)
    notes_path = export_assembly_notes(stem)
    export_prints(stem, layers)
    made, skipped = export_images(stem, layers)
    print(f"  {stem}: {len(names)} gerber/drill files -> "
          f"{os.path.relpath(zpath, ROOT)}")
    print(f"  {stem}: {ncpl} placements -> {os.path.relpath(cpl, ROOT)}")
    print(f"  {stem}: {len(turned)} of them turned for JLCPCB -> "
          f"{os.path.relpath(jlc_cpl, ROOT)}")
    print(f"  {stem}: assembler's notes -> {os.path.relpath(notes_path, ROOT)}")
    print(f"  {stem}: {len(lines)} BOM lines, parts ${total:.2f}/board -> "
          f"{os.path.relpath(bom, ROOT)}")
    print(f"  {stem}: {len(made)} images -> docs/images/, plus STEP and stats")
    if skipped:
        print(f"  .. {len(skipped)} PNG(s) skipped (pdftoppm not installed): "
              f"{', '.join(skipped)}")
    if unknown:
        print(f"  !! no order code for: {'; '.join(unknown)}")
    return total, lines, unknown


if __name__ == "__main__":
    bad = 0
    for stem, layers in (("earthnmr", 4),):
        total, lines, unknown = run(stem, layers)
        bad += len(unknown)
    sys.exit(1 if bad else 0)
