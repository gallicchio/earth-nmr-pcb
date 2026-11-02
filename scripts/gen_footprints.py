#!/usr/bin/env python3
"""Generate the project-specific footprints that the stock KiCad libraries lack
or get slightly wrong.

Every dimension below is taken from the drawing named in the footprint's
description (datasheets/), cross-checked against the land pattern JLCPCB
places the part with (scripts/easyeda.py <code>), so the numbers can be
re-checked.  The BNC, the terminal block, the trimmer and the test loop are
the op-amp and PID boards'; the slide switch is KiCad's own footprint with
its locating holes lengthened to take JLCPCB's drawing of the part as well;
the DIP switch is the Lorenz board's DSIC06 drawn for eight.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import S, q, n, uid, effects, stroke, at

FP_VERSION = "20260206"
LIB = "earthnmr"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "hardware", "lib", LIB + ".pretty")

SILK_W = 0.15
FAB_W = 0.10
CRT_W = 0.05
MM_SCALE = 1.0 / 2.54       # KiCad VRML unit is 2.54 mm; models are drawn in mm


def model(f, path, scale=1.0, rot=(0, 0, 0), offset=(0, 0, 0)):
    m = S("model", q(path))
    m.add(S("offset").add(S("xyz", n(offset[0]), n(offset[1]), n(offset[2]))),
          S("scale").add(S("xyz", n(scale), n(scale), n(scale))),
          S("rotate").add(S("xyz", n(rot[0]), n(rot[1]), n(rot[2]))))
    f.add(m)


def fp_header(name, descr, tags, attr, ref_y):
    f = S("footprint", q(name))
    f.add(S("version", FP_VERSION),
          S("generator", q("earthnmr-gen")),
          S("generator_version", q("10.0")),
          S("layer", q("F.Cu")),
          S("descr", q(descr)),
          S("tags", q(tags)),
          S("attr", attr))
    for pname, val, layer, hide in (("Reference", "REF**", "F.SilkS", False),
                                    ("Value", name, "F.Fab", False),
                                    ("Datasheet", "", "F.Fab", True),
                                    ("Description", descr, "F.Fab", True)):
        y = ref_y if pname == "Reference" else -ref_y
        p = S("property", q(pname), q(val))
        p.add(at(0, y), S("unlocked", "yes"), S("layer", q(layer)))
        if hide:
            p.add(S("hide", "yes"))
        p.add(S("uuid", q(uid(f"{name}/prop/{pname}"))),
              effects(size=1.0, thickness=0.15))
        f.add(p)
    return f


def line(x1, y1, x2, y2, layer, width, key):
    return S("fp_line").add(
        S("start", n(x1), n(y1)), S("end", n(x2), n(y2)),
        stroke(width), S("layer", q(layer)), S("uuid", q(uid(key))))


def rect_lines(f, x1, y1, x2, y2, layer, width, key):
    f.add(line(x1, y1, x2, y1, layer, width, key + "/t"),
          line(x2, y1, x2, y2, layer, width, key + "/r"),
          line(x2, y2, x1, y2, layer, width, key + "/b"),
          line(x1, y2, x1, y1, layer, width, key + "/l"))


def circle(cx, cy, r, layer, width, key):
    return S("fp_circle").add(
        S("center", n(cx), n(cy)), S("end", n(cx + r), n(cy)),
        stroke(width), S("fill", "no"), S("layer", q(layer)), S("uuid", q(uid(key))))


def tht_pad(num, x, y, drill, dia, key, shape="circle"):
    p = S("pad", q(num), "thru_hole", shape)
    p.add(at(x, y), S("size", n(dia), n(dia)), S("drill", n(drill)),
          S("layers", q("*.Cu"), q("*.Mask")),
          S("remove_unused_layers", "no"), S("uuid", q(uid(key))))
    return p


def npth_slot(x, y, w, h, key):
    """An unplated slot: a locating post that two libraries put 0.3 mm apart."""
    p = S("pad", q(""), "np_thru_hole", "oval")
    p.add(at(x, y), S("size", n(w), n(h)), S("drill", "oval", n(w), n(h)),
          S("layers", q("*.Cu"), q("*.Mask")), S("uuid", q(uid(key))))
    return p


def smd_pad(num, x, y, w, h, key):
    p = S("pad", q(num), "smd", "roundrect")
    p.add(at(x, y), S("size", n(w), n(h)),
          S("layers", q("F.Cu"), q("F.Paste"), q("F.Mask")),
          S("roundrect_rratio", "0.25"), S("uuid", q(uid(key))))
    return p


def text_fab(f, txt, x, y, key, size=0.8):
    f.add(S("fp_text", "user", q(txt)).add(
        at(x, y, 0), S("layer", q("F.Fab")), S("uuid", q(uid(key))),
        effects(size=size, thickness=0.12)))


# ----------------------------------------------------------------- BNC ------
def bnc():
    """SAMZO BNC-KYWE-295-W4-N right-angle PCB BNC jack (the op-amp board's).

    Drawing BNCKYWE-P03900 (LCSC C41416668): 10 x 10 mm body on the board,
    four ground pins O1.14 on an 8 x 8 mm square, centre pin O1.0 at the
    middle, barrel on the +X axis, 29.5 mm overall, axis 6.1 mm above board.
    JLCPCB's land pattern (easyeda C41416668): centre 1.8/1.2, posts 2.0/1.4
    at (+/-4, +/-4), barrel along their +y: our +x is their +y, hence the +90
    CPL correction read on the Lorenz board.
    """
    name = "BNC_KYWE_RightAngle"
    f = fp_header(name,
                  "BNC jack, right angle, 4 ground pins on 8x8mm + centre pin, "
                  "SAMZO BNC-KYWE-295-W4-N / HenryTech HL2-BNC-KYWE (LCSC C41416668)",
                  "BNC coaxial jack right-angle 50ohm", "through_hole", 7.4)
    BODY, PIN, BARREL_END, BARREL_R = 10.0, 4.0, 24.5, 4.8
    f.add(tht_pad("1", 0, 0, 1.3, 2.4, f"{name}/p1", "circle"))
    for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        f.add(tht_pad("2", sx * PIN, sy * PIN, 1.4, 2.6, f"{name}/p2/{i}"))
    h = BODY / 2
    rect_lines(f, -h, -h, h, h, "F.Fab", FAB_W, f"{name}/fab/body")
    f.add(line(h, -BARREL_R, BARREL_END, -BARREL_R, "F.Fab", FAB_W, f"{name}/fab/bt"),
          line(h, BARREL_R, BARREL_END, BARREL_R, "F.Fab", FAB_W, f"{name}/fab/bb"),
          line(BARREL_END, -BARREL_R, BARREL_END, BARREL_R, "F.Fab", FAB_W, f"{name}/fab/be"))
    m, g_ = 2.4, 0.8
    for key, (x1, y1, x2, y2) in {
        "t": (-m, -h, m, -h), "b": (-m, h, m, h),
        "l1": (-h, -m, -h, -g_), "l2": (-h, g_, -h, m), "r1": (h, -m, h, -g_), "r2": (h, g_, h, m),
    }.items():
        f.add(line(x1, y1, x2, y2, "F.SilkS", SILK_W, f"{name}/silk/{key}"))
    f.add(line(h, -BARREL_R, h + 1.5, -BARREL_R, "F.Fab", FAB_W, f"{name}/fab/bt2"),
          line(h, BARREL_R, h + 1.5, BARREL_R, "F.Fab", FAB_W, f"{name}/fab/bb2"))
    rect_lines(f, -h - 0.25, -h - 0.25, BARREL_END + 0.25, h + 0.25,
               "F.CrtYd", CRT_W, f"{name}/crt")
    text_fab(f, "BNC", 0, 0, f"{name}/fabtxt")
    model(f, "${KIPRJMOD}/lib/earthnmr.3dshapes/BNC_KYWE_RightAngle.wrl", scale=MM_SCALE)
    return name, f


# ---------------------------------------------------------- slide switch ----
def msk12c02():
    """Shouhan MSK12C02 SPDT slide switch, SMD, right-angle actuator (LCSC C431540).

    KiCad's own SW_SPDT_Shouhan_MSK12C02 has the three terminals at
    x = -2.25, +0.75, +2.25 on y = -1.95, 0.6 x 1.3 mm; four shell pads
    1.05 x 0.7 at (+/-3.675, +/-1.1); two 0.85 mm locating holes at (+/-1.5, 0):
    Shouhan's recommended land pattern exactly (datasheet page 1: 8.4 and 6.3 mm
    over the shell pads, 2.2 mm between their rows, the terminals 2.6 mm from the
    holes' line to their far ends).  JLCPCB's drawing (easyeda C431540) puts its
    terminals 2.25 mm from the posts, not 1.95, and its shell rows 2.3 mm apart:
    laid on ours by the terminals (check_rotations.py), its posts fall 0.3 mm
    further from the terminals than Shouhan's (CLAUDE_PCB.md, "Locating posts")
    and its shell pads 0.25-0.35 mm off ours.  The holes here are 0.9 x 1.45 mm
    slots centred at y = +0.275, so either drawing's posts drop in.  JLCPCB
    places the part by its 3D body, whose posts are at their holes: the CPL's
    datum (0.55 mm) puts those on ours.  Pin 2 is the common; the knob sticks
    out 1.45 mm from the long edge opposite the terminals (+y) and slides along
    x, +-0.8 mm about the middle, toward the terminal it connects.
    """
    name = "SW_SPDT_Shouhan_MSK12C02"
    f = fp_header(name,
                  "SPDT slide switch, SMD, Shouhan MSK12C02 (LCSC C431540); KiCad's "
                  "footprint with the locating holes lengthened to 0.9 x 1.45 mm so "
                  "JLCPCB's drawing of the posts (0.3 mm further out) fits too",
                  "MSK-12C02 MSK12C02 slide switch SPDT", "smd", 3.7)
    for num, x in (("1", -2.25), ("2", 0.75), ("3", 2.25)):
        f.add(smd_pad(num, x, -1.95, 0.6, 1.3, f"{name}/p{num}"))
    for i, (x, y) in enumerate(((-3.675, -1.1), (-3.675, 1.1), (3.675, -1.1), (3.675, 1.1))):
        f.add(smd_pad("SH", x, y, 1.05, 0.7, f"{name}/sh{i}"))
    for i, x in enumerate((-1.5, 1.5)):
        f.add(npth_slot(x, 0.275, 0.9, 1.45, f"{name}/post{i}"))
    # body 6.6 x 2.7; the knob stands off the +y edge, to y = 1.35 + 1.45 = 2.8
    rect_lines(f, -3.3, -1.35, 3.3, 1.35, "F.Fab", FAB_W, f"{name}/fab")
    f.add(line(-3.45, -0.4, -3.45, 0.4, "F.SilkS", SILK_W, f"{name}/silk/l"),
          line(3.45, -0.4, 3.45, 0.4, "F.SilkS", SILK_W, f"{name}/silk/r"),
          line(-1.6, 1.6, 1.6, 1.6, "F.SilkS", SILK_W, f"{name}/silk/b"))
    rect_lines(f, -1.45, 1.35, 1.45, 2.8, "F.Fab", FAB_W, f"{name}/fab/knob")      # its travel
    rect_lines(f, -4.45, -2.85, 4.45, 3.05, "F.CrtYd", CRT_W, f"{name}/crt")
    text_fab(f, "2=C", 0, 0.6, f"{name}/fabtxt", size=0.6)
    model(f, "${KIPRJMOD}/lib/earthnmr.3dshapes/SW_MSK12C02.wrl", scale=MM_SCALE)
    return name, f


# ---------------------------------------------------------------- trimmer ---
def trimpot():
    """Bourns 3362P, 1/4 inch square single-turn cermet trimmer, top adjust.

    BOCHEN's drawing of the part we buy (datasheets/3362P-1-105_C118945.pdf,
    page 3): body 6.9 x 7.1 mm, 4.8 mm tall, screw on top 3.2 mm from the edge
    beside pin 2; terminals 1 and 3 on a 5.0 mm pitch with the wiper (2) 2.5 mm
    from their row and 1.0 mm from the body's edge, the 1-3 row 3.6 mm from the
    other edge; pins 0.5 mm, so 0.9 mm holes.  So the body's middle is 1.30 mm
    from the pins' middle, toward pins 1 and 3: JLCPCB's 3D outline (easyeda
    C118945's component record, -2.25 to +4.85 mm) agrees, and its land pattern
    draws the same three pads at 5.08/2.54 mm, 1.8/0.9, exactly these.  The
    anchor is the pins' middle, as JLCPCB's.  rev A's first build centred the
    body on the pins' middle (JLCPCB's preview showed it, 2026-10-29).
    Pad 1 is square: it says which end is terminal 1 on the board.
    """
    name = "Potentiometer_Bourns_3362P_Vertical"
    f = fp_header(name,
                  "Bourns 3362P, 6.6 mm square single-turn cermet trimmer, "
                  "top adjust (LCSC C118945)",
                  "potentiometer trimmer trimpot Bourns 3362P vertical",
                  "through_hole", 4.9)
    for (num, x, y, shape) in (("1", -2.54, 1.27, "rect"),
                               ("2", 0.0, -1.27, "circle"),
                               ("3", 2.54, 1.27, "circle")):
        f.add(tht_pad(num, x, y, 0.9, 1.6, f"{name}/p{num}", shape=shape))
    bw, y0, y1 = 6.90 / 2, -2.25, 4.85          # the body: pin 2's edge at y0, the far edge at y1
    rect_lines(f, -bw, y0, bw, y1, "F.Fab", FAB_W, f"{name}/fab")
    f.add(circle(0, y0 + 3.2, 1.6, "F.Fab", FAB_W, f"{name}/screw"))
    rect_lines(f, -bw - 0.3, y0 - 0.3, bw + 0.3, y1 + 0.3, "F.SilkS", SILK_W, f"{name}/silk")
    f.add(line(-bw - 0.3, y1 - 1.0, -bw + 0.9, y1 + 0.3, "F.SilkS", SILK_W, f"{name}/silk/p1"))
    rect_lines(f, -bw - 0.35, y0 - 0.35, bw + 0.35, y1 + 0.35, "F.CrtYd", CRT_W, f"{name}/crt")
    text_fab(f, "1", -2.54, 2.6, f"{name}/fab/p1", size=0.7)
    model(f, "${KIPRJMOD}/lib/earthnmr.3dshapes/Potentiometer_3362P.wrl", scale=MM_SCALE)
    return name, f


# ------------------------------------------------------- screw terminals ----
def kf301(npins):
    """KEFA KF301-5.0-xP screw terminal block, 5.0 mm pitch (LCSC C474882).

    KF301-5.0 drawing (datasheets/): pins O1.0 on 5.00 mm centres, holes 1.2
    recommended; body 7.6 mm deep and 10.0 mm tall; the side view puts the pins
    4.0 mm from the vertical back face, so the sloped wire-entry face is 3.6 mm
    from them (the 3.60 in the front view is the pins' length, not a depth: the
    op-amp board's review round 1).  JLCPCB's land pattern (easyeda) uses 2.2 mm
    pads on 1.4 mm holes at the same centres and draws the body from y = -4.0 to
    +3.7 with its wire-entry arrows on +y.  Here the wires enter from -y (3.7 mm
    from the pins) and the back is at +4.0, so the CPL turns JLCPCB's drawing by
    180 (parts.JLC_ROTATION; the pin row is symmetric, so only the body turns).
    Pads follow JLCPCB's; pad 1 is square.
    """
    name = f"TerminalBlock_KF301_1x{npins:02d}_P5.00mm"
    f = fp_header(name,
                  f"{npins}-way 5.0mm screw terminal block, KEFA KF301-5.0-{npins}P "
                  f"(LCSC {'C474881' if npins == 2 else 'C474882'}); wires enter from -y",
                  "screw terminal block KF301 5.0mm", "through_hole", 5.6)
    PITCH = 5.0
    for i in range(npins):
        x = (i - (npins - 1) / 2.0) * PITCH
        f.add(tht_pad(str(i + 1), x, 0, 1.4, 2.2, f"{name}/p{i+1}",
                      shape="rect" if i == 0 else "circle"))
    w = npins * PITCH + 0.4
    x0, x1, yf, yb = -w / 2, w / 2, -3.7, 4.0
    rect_lines(f, x0, yf, x1, yb, "F.Fab", FAB_W, f"{name}/fab")
    rect_lines(f, x0 - 0.1, yf - 0.1, x1 + 0.1, yb + 0.1, "F.SilkS", SILK_W, f"{name}/silk")
    # the wire openings, drawn on the entry side so the picture says which way the wires go
    for i in range(npins):
        x = (i - (npins - 1) / 2.0) * PITCH
        f.add(line(x - 1.5, yf - 0.1, x - 1.5, yf + 1.2, "F.SilkS", SILK_W, f"{name}/silk/w{i}a"),
              line(x + 1.5, yf - 0.1, x + 1.5, yf + 1.2, "F.SilkS", SILK_W, f"{name}/silk/w{i}b"),
              line(x - 1.5, yf + 1.2, x + 1.5, yf + 1.2, "F.SilkS", SILK_W, f"{name}/silk/w{i}c"))
    rect_lines(f, x0 - 0.35, yf - 0.35, x1 + 0.35, yb + 0.35, "F.CrtYd", CRT_W, f"{name}/crt")
    text_fab(f, "wires", 0, yf + 1.0, f"{name}/fabtxt", size=0.7)
    model(f, f"${{KIPRJMOD}}/lib/earthnmr.3dshapes/TerminalBlock_KF301_1x{npins:02d}.wrl",
          scale=MM_SCALE)
    return name, f


# ------------------------------------------------------- film capacitor -----
def film_mes():
    """Hongzhi MES105J2A-7-50R0, 1 uF 100 V metallized polypropylene (LCSC C333829).

    Hongzhi's table (datasheets/MES105J2A-7-50R0_C333829.pdf): W 7.2, H 12.0,
    T 6.0 mm, leads 0.5 mm on P = 5.0 mm.  JLCPCB's land pattern (easyeda
    C333829, CAP-TH_L7.2-W6.0-P5.00-D0.6) puts 1.8 mm pads on 1.0 mm holes at
    +/-2.54 from the body's middle; the 0.5 mm leads drop into 1.0 mm holes at
    either spacing, so the holes here are at the data sheet's 5.0 mm.  Not
    polarised.
    """
    name = "C_Film_P5.00mm_L7.2mm_W6.0mm"
    f = fp_header(name,
                  "Metallized polypropylene film capacitor, 7.2 x 6.0 mm, leads on 5.0 mm "
                  "(Hongzhi MES105J2A-7-50R0, LCSC C333829)",
                  "capacitor film polypropylene 5mm", "through_hole", 4.3)
    for num, x in (("1", -2.5), ("2", 2.5)):
        f.add(tht_pad(num, x, 0, 1.0, 1.8, f"{name}/p{num}"))
    bl, bw = 7.2 / 2, 6.0 / 2
    rect_lines(f, -bl, -bw, bl, bw, "F.Fab", FAB_W, f"{name}/fab")
    rect_lines(f, -bl - 0.15, -bw - 0.15, bl + 0.15, bw + 0.15, "F.SilkS", SILK_W, f"{name}/silk")
    rect_lines(f, -bl - 0.35, -bw - 0.35, bl + 0.35, bw + 0.35, "F.CrtYd", CRT_W, f"{name}/crt")
    model(f, "${KIPRJMOD}/lib/earthnmr.3dshapes/C_Film_L7.2_W6.0.wrl", scale=MM_SCALE)
    return name, f


# ------------------------------------------------------------ DIP switch ----
def dip8():
    """KingTek DSIC08LSGET, 8-way SMD DIP switch, 2.54 mm pitch (LCSC C3293158).

    KingTek's drawing DSIC08LSGET (datasheets/): body 20.32 x 6.20 mm; pads
    2.20 x 1.10 (the land pattern JLCPCB places with, easyeda C3293158: 16
    pads 2.20 x 1.10 on two rows 8.80 mm apart, 2.54 mm pitch); the Lorenz
    board's DSIC06 is the same family.  Switch k joins pad k and pad 17 - k.
    Here the switches lie along x: pads 1-8 on the row at +y, left to right,
    pads 16-9 on the row at -y, so switch k stands across the body at x_k.
    ON slides toward the pads 1-8 row (KingTek: ON is marked on the body).
    """
    name = "SW_DIP_SPSTx08_Slide_KingTek_DSIC08LSGET_W8.61mm_P2.54mm"
    f = fp_header(name,
                  "8-way SMD DIP switch, 2.54 mm pitch, 8.8 mm row spacing, "
                  "KingTek DSIC08LSGET (LCSC C3293158); switch k joins pads k and 17-k",
                  "DIP switch SPST x8 SMD 2.54mm", "smd", 6.2)
    PITCH, ROW, PW, PH = 2.54, 4.40, 1.10, 2.20
    x0 = -PITCH * 3.5
    for i in range(8):
        x = x0 + i * PITCH
        f.add(smd_pad(str(i + 1), x, ROW, PW, PH, f"{name}/p{i+1}"),
              smd_pad(str(16 - i), x, -ROW, PW, PH, f"{name}/p{16-i}"))
    bl, bw = 20.32 / 2, 6.20 / 2
    rect_lines(f, -bl, -bw, bl, bw, "F.Fab", FAB_W, f"{name}/fab")
    f.add(line(-bl, -bw, -bl, bw, "F.SilkS", SILK_W, f"{name}/silk/l"),
          line(bl, -bw, bl, bw, "F.SilkS", SILK_W, f"{name}/silk/r"))
    f.add(circle(-bl - 0.6, ROW, 0.3, "F.SilkS", SILK_W, f"{name}/silk/p1dot"))
    rect_lines(f, -bl - 1.2, -(ROW + PH / 2 + 0.25), bl + 0.35, ROW + PH / 2 + 0.25,
               "F.CrtYd", CRT_W, f"{name}/crt")
    text_fab(f, "ON", 0, 1.8, f"{name}/fabtxt", size=0.7)
    model(f, "${KIPRJMOD}/lib/earthnmr.3dshapes/SW_DIP_x08_DSIC08.wrl", scale=MM_SCALE)
    return name, f


# ------------------------------------------------------- test loop ----------
def testloop():
    """RH-5019 SMT test loop (LCSC C5199800), the Keystone 5019 pattern.

    JLCPCB's land pattern (easyeda C5199800) is one 4.0 x 2.2 mm pad with the
    loop lying along x; the part is a 3.8 x 2.0 mm wire loop standing 1.5 mm
    off the pad, which a scope probe's hook grabs.
    """
    name = "TestPoint_Loop_RH-5019"
    f = fp_header(name, "SMT test loop, 3.8 x 2.0 mm, RH-5019 / Keystone 5019 (LCSC C5199800)",
                  "test point loop probe", "smd", 2.6)
    f.add(smd_pad("1", 0, 0, 4.0, 2.2, f"{name}/p1"))
    rect_lines(f, -1.9, -1.0, 1.9, 1.0, "F.Fab", FAB_W, f"{name}/fab")
    f.add(line(-1.9, -1.0, 1.9, -1.0, "F.Fab", FAB_W, f"{name}/fab/t"))
    rect_lines(f, -2.3, -1.4, 2.3, 1.4, "F.CrtYd", CRT_W, f"{name}/crt")
    model(f, "${KIPRJMOD}/lib/earthnmr.3dshapes/TestLoop_RH-5019.wrl", scale=MM_SCALE)
    return name, f


def main():
    os.makedirs(OUT, exist_ok=True)
    for maker in (bnc, msk12c02, trimpot, testloop, lambda: kf301(2), lambda: kf301(3), film_mes, dip8):
        name, node = maker()
        path = os.path.join(OUT, name + ".kicad_mod")
        with open(path, "w") as fh:
            fh.write(node.render() + "\n")
        print(f"  wrote {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
