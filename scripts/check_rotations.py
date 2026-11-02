#!/usr/bin/env python3
"""Which way round does JLCPCB place each part?  Fit JLCPCB's own land pattern (easyeda, scripts/easyeda.py) onto the
footprint on our board, pad number by pad number, at each quarter turn, and compare the turn that fits, and where
their origin lands, with parts.JLC_ROTATION.

    python3 scripts/check_rotations.py

AMOD-and-RFMOD's check_rotations.py (CLAUDE_PCB.md section 23), for one board and for a table that carries the datum
beside the turn, and then the upload itself: JLCPCB's drawing put where earthnmr_cpl_jlcpcb_upload.csv says,
against our pads on the board, and then the body JLCPCB's preview draws (the 3D model's outline in its component
record), placed the same way, against our courtyard and whatever else it lands on.  A part whose pads are all one number, or two of a two-terminal part with no polarity, is skipped; a
fit whose best two turns are close is "ambiguous" and printed for a look.  It needs the network the first time (the
cache, scripts/easyeda_cache.json, is gitignored), so ./make.py does not run it: run it whenever a part is added.
"""
import csv, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import parts, easyeda
from sexp_parse import parse_file

STEM = "earthnmr"

UNPOLAR = ("Resistor_SMD:", "Capacitor_SMD:C_", "Inductor_SMD:", "Fuse:")
# fits that disagree with the table for a known reason: the table is right
KNOWN = {
    "C2297": "KT-0805G: read at 0 in GPiBridge's preview; JLCPCB numbers this LED's pads the other way round",
    "C474882": "KF301-3P: a symmetric pin row; their wire openings on +y, ours on -y, so +180 turns only the body",
    "C474881": "KF301-2P: as the 3P (read at +180 in the op-amp board's preview)",
}
# where JLCPCB numbers the pads otherwise (check_pinouts.py: the KT-0805G's pin 1 is its anode; the BNC's posts are
# 1-4 and its centre 5), the upload is measured pad to nearest pad
RENUMBERED = {"C2297", "C41416668", "C474882", "C474881"}
# parts whose pads do not say which way the body faces: their drawing's outline (top silk) and our courtyard, each
# from the pads' centre, must lean the same way on the board
FACING = {"C41416668": "the barrel", "C474882": "the wire openings (the body is 3.7 mm deep on their side, 4.0 behind)",
          "C474881": "the wire openings (as the 3P)"}
# where our footprint names the pads and JLCPCB's drawing numbers them: ours -> theirs, from the maker's datasheet
NAMES = {
    "C20182914": {"S": "1", "T": "2", "R": "3"},   # SJ1-3523N: Same Sky's drawing of 09/12/2024, 1 sleeve, 2 tip, 3 ring
}
TOL = 0.3          # mm, a pad centre of theirs from ours in the upload
# parts whose datum is set by JLCPCB's 3D body (what their preview draws and their machine places), not by their land
# pattern's pads: (why, the tolerance for the signal pads in the upload)
BODY_DATUM = {
    "C431540": ("the body's posts on Shouhan's post line; JLCPCB's land pattern puts the terminals 0.3 mm further out "
                "than Shouhan's (rev A's preview, 2026-10-29)", 0.35),
}
# mechanical pads (numbered once on neither side: tabs, shells, posts) that JLCPCB draws elsewhere; the signal pads
# place the part, and these are listed, not failed
MECH = {
    "C233689": "the tab (our 2, their 4): their pad 1.3 mm further from the leads than KiCad's TO-263, overlapping it",
    "C154570": "the tab (our 2, their 4): as the NPN's",
    "C351173": "the posts: their drawing 10 mm apart, ALPS's slots 8.8 mm (review round 1)",
    "C202373": "the posts: as the C351173's, the same RK09K body",
    "C431540": "the shell tabs: their drawing 0.3 mm off Shouhan's land pattern, which ours follows",
    "C146578": "the tab: their pad sits elsewhere under the body than KiCad's TO-263-2's; the leads place the part",
}


def footprints():
    """{ref: (fpid, [(pad, x, y)], (X, Y, R), [(x, y)] of its unplated holes)}, pads footprint-local, unrotated."""
    root = parse_file(os.path.join(ROOT, "hardware", STEM + ".kicad_pcb"))
    out = {}
    for fp in root.kids("footprint"):
        ref = next((pr.atom(1) for pr in fp.kids("property") if pr.atom(0) == "Reference"), None)
        at = fp.first("at")
        pads = [(pd.atom(0), float(pd.first("at").atom(0)), float(pd.first("at").atom(1)))
                for pd in fp.kids("pad") if pd.atom(1) != "np_thru_hole"]
        holes = [(float(pd.first("at").atom(0)), float(pd.first("at").atom(1)))
                 for pd in fp.kids("pad") if pd.atom(1) == "np_thru_hole"]
        out[ref] = (fp.atom(0), pads, (float(at.atom(0)), float(at.atom(1)), float(at.atom(2) or 0)), holes)
    return out


def courtyard(ref):
    """Our courtyard's box centre, footprint-local."""
    root = parse_file(os.path.join(ROOT, "hardware", STEM + ".kicad_pcb"))
    for fp in root.kids("footprint"):
        if next((pr.atom(1) for pr in fp.kids("property") if pr.atom(0) == "Reference"), None) != ref:
            continue
        pts = [(float(g.first(k).atom(0)), float(g.first(k).atom(1))) for g in fp.kids()
               if g.tag in ("fp_line", "fp_rect") and g.first("layer").atom(0) == "F.CrtYd" for k in ("start", "end")]
        return ((min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2)


def aux_origin():
    ax = parse_file(os.path.join(ROOT, "hardware", STEM + ".kicad_pcb")).first("setup").first("aux_axis_origin")
    return float(ax.atom(0)), float(ax.atom(1))


def lcsc_of():
    out = {}
    with open(os.path.join(ROOT, "out", STEM, STEM + "_bom_jlcpcb_upload.csv")) as fh:
        for row in csv.DictReader(fh):
            for ref in row["Designator"].split(","):
                out[ref.strip()] = row["LCSC Part #"]
    return out


def centroids(pads):
    """{pad number: centre of its pads}, and the numbers that have one pad only."""
    acc = {}
    for num, x, y in pads:
        if num:
            acc.setdefault(num, []).append((x, y))
    cen = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in acc.items()}
    return cen, {k for k, v in acc.items() if len(v) == 1}


def turn(p, a):
    """Rotate by a degrees counter-clockwise as seen on a y-down board (KiCad's sense)."""
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return (p[0] * c + p[1] * s, -p[0] * s + p[1] * c)


def fit(ours, theirs, single=None):
    """[(rms, correction, datum)] over the four corrections, best first.  JLCPCB's drawing D = our footprint F turned by
    a; the CPL then needs -a.  The datum (where their origin sits in our footprint) comes from the numbers with one pad
    on both sides when there are two or more of them; a pad that still disagrees by 0.5 mm is dropped from it."""
    keys = sorted(set(ours) & set(theirs))
    if len(keys) < 2:
        return None
    tkeys = sorted(single) if single and len(single) >= 2 else keys
    res = []
    for a in (0, 90, 180, 270):
        F = [turn(ours[k], a) for k in keys]
        D = [theirs[k] for k in keys]
        fx, fy = sum(p[0] for p in F) / len(F), sum(p[1] for p in F) / len(F)
        dx, dy = sum(p[0] for p in D) / len(D), sum(p[1] for p in D) / len(D)
        e = math.sqrt(sum((f[0] - fx - d[0] + dx) ** 2 + (f[1] - fy - d[1] + dy) ** 2 for f, d in zip(F, D)) / len(F))
        tk = list(tkeys)
        while True:
            Ft = [turn(ours[k], a) for k in tk]
            Dt = [theirs[k] for k in tk]
            fx, fy = sum(p[0] for p in Ft) / len(Ft), sum(p[1] for p in Ft) / len(Ft)
            dx, dy = sum(p[0] for p in Dt) / len(Dt), sum(p[1] for p in Dt) / len(Dt)
            r = [math.hypot(f[0] - fx - d[0] + dx, f[1] - fy - d[1] + dy) for f, d in zip(Ft, Dt)]
            if len(tk) <= 2 or max(r) < 0.5:
                break
            tk.pop(r.index(max(r)))
        # their origin in our footprint's own frame: D = turn(F, a) + t, so their (0, 0) is turn(-t, -a) in ours
        datum = turn((fx - dx, fy - dy), -a)
        res.append((e, (360 - a) % 360, datum))
    return sorted(res, key=lambda r: r[0])


def main():
    fps, codes = footprints(), lcsc_of()
    seen, bad = {}, []
    for ref, (fpid, pads, _, _) in sorted(fps.items()):
        code = codes.get(ref)
        if not code or code in seen:
            continue
        seen[code] = (ref, fpid)
        pads = [(NAMES.get(code, {}).get(n, n), x, y) for n, x, y in pads]
        ours, ours1 = centroids(pads)
        if len(ours) < 2 or (len(ours) == 2 and fpid.startswith(UNPOLAR)):
            print("  skip    %-10s %-6s %-46s not polarised" % (code, ref, fpid[:46]))
            continue
        try:
            lp, _ = easyeda.land_pattern(code)
        except Exception as e:
            print("  ?       %-10s %-6s %-46s cannot fetch JLCPCB's drawing: %s" % (code, ref, fpid[:46], e))
            continue
        if not lp:
            print("  ?       %-10s %-6s %-46s no drawing" % (code, ref, fpid[:46]))
            continue
        theirs, theirs1 = centroids([(p["number"], p["x"], p["y"]) for p in lp["pads"]])
        r = fit(ours, theirs, ours1 & theirs1)
        if code in RENUMBERED and code not in KNOWN:
            print("  renum   %-10s %-6s %-46s numbered otherwise by JLCPCB: measured in the upload below" % (code, ref, fpid[:46]))
            continue
        if r is None:
            print("  ?       %-10s %-6s %-46s pad numbers do not match (ours %s, theirs %s)"
                  % (code, ref, fpid[:46], sorted(ours)[:6], sorted(theirs)[:6]))
            continue
        (e0, best, datum), (e1, _, _) = r[0], r[1]
        deg, have, how = parts.JLC_ROTATION.get(code, (0, (0.0, 0.0), "absent"))[:3]
        have = (have[0], -have[1])      # the table's shift is y-up, as gen_outputs.py applies it to the CPL
        flag = "ok" if deg == best else ("known" if code in KNOWN else "DIFFERS")
        amb = " ambiguous (%.2f vs %.2f mm)" % (e0, e1) if e1 - e0 < 0.15 else ""
        dat = ""
        if code in BODY_DATUM:
            dat = "; datum from the body: " + BODY_DATUM[code][0]
        elif math.hypot(datum[0] - have[0], datum[1] - have[1]) > 0.15:
            dat = "; their origin at (%.3f, %.3f) in ours, table (%.3f, %.3f)" % (datum[0], datum[1], have[0], have[1])
            if not amb and flag == "ok":
                flag = "DATUM"
        line = "  %-7s %-10s %-6s %-46s fits +%-3d (rms %.2f mm, package %s); table +%d %s%s%s" % (
            flag, code, ref, fpid[:46], best, e0, lp["package"], deg, how, amb, dat)
        print(line)
        if flag not in ("ok", "known") and not amb:
            bad.append(line)
    print("\n%d codes checked; %d differ from the table" % (len(seen), len(bad)))
    for b in bad:
        print(b)
    off = upload(fps, codes)
    off += bodies(codes)
    return 1 if bad or off else 0


def _boxes():
    """{ref: courtyard box on the board, y down}, and the front silkscreen's texts [(text, x, y)]."""
    root = parse_file(os.path.join(ROOT, "hardware", STEM + ".kicad_pcb"))
    boxes, texts = {}, []
    for fp in root.kids("footprint"):
        ref = next((pr.atom(1) for pr in fp.kids("property") if pr.atom(0) == "Reference"), None)
        at = fp.first("at")
        X, Y, R = float(at.atom(0)), float(at.atom(1)), float(at.atom(2) or 0)
        pts = []
        for g in fp.kids():
            if g.tag in ("fp_line", "fp_rect") and g.first("layer").atom(0) == "F.CrtYd":
                for k in ("start", "end"):
                    q = turn((float(g.first(k).atom(0)), float(g.first(k).atom(1))), R)
                    pts.append((X + q[0], Y + q[1]))
        if pts:
            boxes[ref] = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    for t in root.kids("gr_text"):
        if t.first("layer").atom(0) == "F.SilkS":
            at = t.first("at")
            texts.append((t.atom(0), float(at.atom(0)), float(at.atom(1))))
    return boxes, texts


# bodies that reach past our courtyard on purpose: printed, not failed
OVERHANG = {
    "C41416668": "the BNC's barrel, off the board's edge",
    "C474882": "",
}


def bodies(codes):
    """JLCPCB's drawing of each part's body (the 3D model's outline their preview shows) where the upload CPL puts
    it, against our courtyard: how far it reaches past each side, and any other part's courtyard or silk text it
    lands on.  The preview is where a body drawn in the wrong place shows; the pads cannot show it (the 3362P's
    body sits 1.3 mm toward pins 1 and 3 from the middle of its pins, which our first footprint had not drawn)."""
    ox, oy = aux_origin()
    boxes, texts = _boxes()
    off, done = [], set()
    print("\nThe bodies, JLCPCB's 3D outline where the CPL puts it, against our courtyard (mm past it: left, top, "
          "right, bottom on the board):")
    with open(os.path.join(ROOT, "out", STEM, STEM + "_cpl_jlcpcb_upload.csv")) as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        ref = row["Designator"]
        code = codes.get(ref)
        if not code or ref not in boxes:
            continue
        try:
            mb = easyeda.model_outline(code)
        except Exception as e:
            print("  ?     %-5s %-10s cannot fetch its component record: %s" % (ref, code, e))
            continue
        if not mb:
            continue
        xc, yc, rot = float(row["Mid X"]), float(row["Mid Y"]), float(row["Rotation"])
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = [(xc + x * c + y * s, yc + x * s - y * c) for x in (mb[0], mb[2]) for y in (mb[1], mb[3])]
        b = (min(p[0] for p in pts) + ox, oy - max(p[1] for p in pts), max(p[0] for p in pts) + ox, oy - min(p[1] for p in pts))
        cy = boxes[ref]
        past = (cy[0] - b[0], cy[1] - b[1], b[2] - cy[2], b[3] - cy[3])
        hits = [o for o, ob in boxes.items() if o != ref and ob[0] < b[2] - 0.1 and ob[2] > b[0] + 0.1
                and ob[1] < b[3] - 0.1 and ob[3] > b[1] + 0.1]
        covered = [t for t, x, y in texts if b[0] < x < b[2] and b[1] < y < b[3]]
        worst = max(past)
        if (code, round(worst, 1)) in done and not hits and not covered:
            continue
        done.add((code, round(worst, 1)))
        flag = "ok" if worst <= 0.5 else ("known" if code in OVERHANG else "PAST")
        if hits:
            flag = "HITS"
        print("  %-5s %-5s %-10s %+.2f %+.2f %+.2f %+.2f%s%s%s" % (
            flag, ref, code, *past, ("  on " + ", ".join(hits)) if hits else "",
            ("  over silk " + ", ".join(repr(t[:16]) for t in covered)) if covered else "",
            ("  (" + OVERHANG[code] + ")") if flag == "known" and OVERHANG[code] else ""))
        if flag in ("PAST", "HITS"):
            off.append("  %s (%s): JLCPCB's body reaches %.2f mm past our courtyard%s" % (
                ref, code, worst, (" onto " + ", ".join(hits)) if hits else ""))
    return off


def upload(fps, codes):
    """Put JLCPCB's drawing of each part where the upload CPL says (their origin at Mid X/Y, y up from the drill
    origin, turned by Rotation) and measure each of our pads from theirs: by number, or to the nearest of theirs for
    a part they number otherwise; our unplated holes against their holes."""
    ox, oy = aux_origin()
    off = []
    with open(os.path.join(ROOT, "out", STEM, STEM + "_cpl_jlcpcb_upload.csv")) as fh:
        rows = list(csv.DictReader(fh))
    worst = {}
    for row in rows:
        ref = row["Designator"]
        code = codes.get(ref)
        if not code or ref not in fps:
            continue
        lp, _ = easyeda.land_pattern(code)
        if not lp:
            continue
        fpid, pads, (X, Y, R), holes = fps[ref]
        xc, yc, rot = float(row["Mid X"]), float(row["Mid Y"]), float(row["Rotation"])
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))

        def theirs_at(x, y):                       # their drawing is y down; the CPL is y up
            return (xc + x * c + y * s, yc + x * s - y * c)

        def ours_at(x, y):
            q = turn((x, y), R)
            return (X + q[0] - ox, oy - (Y + q[1]))
        tp = [(p["number"], theirs_at(p["x"], p["y"])) for p in lp["pads"]]
        op = [(NAMES.get(code, {}).get(n, n), ours_at(x, y)) for n, x, y in pads]
        d = dm = 0.0
        for n, o in op:
            if not n:
                continue                           # a paste-only aperture
            same = [t for m, t in tp if m == n]
            if code in RENUMBERED or (len(same) == 1 and len([1 for m, _ in op if m == n]) == 1):
                d = max(d, min(math.hypot(o[0] - t[0], o[1] - t[1]) for t in (same if code not in RENUMBERED else [t for _, t in tp])))
            else:
                dm = max(dm, min(math.hypot(o[0] - t[0], o[1] - t[1]) for _, t in tp))
        dh = max((min(math.hypot(o[0] - t[0], o[1] - t[1]) for t in [theirs_at(h["x"], h["y"]) for h in lp["holes"]])
                  for o in [ours_at(x, y) for x, y in holes]), default=0.0) if holes and lp["holes"] else 0.0
        if code in FACING and lp["silk"]:
            x0, y0, x1, y1 = lp["silk"]
            pc = [sum(t[0] for _, t in tp) / len(tp), sum(t[1] for _, t in tp) / len(tp)]
            tb = theirs_at((x0 + x1) / 2, (y0 + y1) / 2)
            ob = ours_at(*courtyard(ref))
            oc = [sum(o[0] for _, o in op) / len(op), sum(o[1] for _, o in op) / len(op)]
            lean = (tb[0] - pc[0]) * (ob[0] - oc[0]) + (tb[1] - pc[1]) * (ob[1] - oc[1])
            print("  body  %-6s %-10s theirs leans (%+.2f, %+.2f), ours (%+.2f, %+.2f) mm: %s %s" % (
                ref, code, tb[0] - pc[0], tb[1] - pc[1], ob[0] - oc[0], ob[1] - oc[1], FACING[code],
                "agree" if lean > 0 else "FACE OPPOSITE WAYS"))
            if lean <= 0:
                off.append("  %s (%s): %s face the other way in JLCPCB's drawing" % (ref, code, FACING[code]))
        w = worst.setdefault(code, [0.0, 0.0, 0.0, [], fpid])
        w[0], w[1], w[2] = max(w[0], d), max(w[1], dm), max(w[2], dh)
        w[3].append(ref)
        tol = BODY_DATUM.get(code, (None, TOL))[1]
        if d > tol:
            off.append("  %s (%s): a pad of ours %.2f mm from theirs" % (ref, code, d))
    print("\nThe upload, JLCPCB's drawing where the CPL puts it (worst signal pad, mechanical pad, unplated hole):")
    for code, (d, dm, dh, refs, fpid) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        print("  %-5s %-10s %-46s pads %.2f  mech %.2f  holes %.2f mm  (%d: %s)%s" % (
            "OFF" if d > BODY_DATUM.get(code, (None, TOL))[1] else "ok", code, fpid[:46], d, dm, dh, len(refs), " ".join(refs[:5]) + (" ..." if len(refs) > 5 else ""),
            ("\n" + " " * 19 + MECH[code]) if dm > TOL and code in MECH else ("  MECHANICAL PADS UNEXPLAINED" if dm > TOL else "")))
        if dm > TOL and code not in MECH:
            off.append("  %s: a mechanical pad %.2f mm from theirs, not in MECH" % (code, dm))
    print("%d placement(s) more than %.1f mm off" % (len(off), TOL))
    for o in off:
        print(o)
    return off


if __name__ == "__main__":
    sys.exit(main())
