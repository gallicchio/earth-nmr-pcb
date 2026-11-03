#!/usr/bin/env python3
"""Draw the schematic of the Earth's-field NMR board on one A1 sheet.

Left to right, as the signal goes: the POLARIZING SUPPLY at the top left feeds
the relay's pole A; the COIL's two leads come in at the left to the relay's
commons; released, the relay hands the coil to the TANK (the tuning bank, the
clamp, the calibration input); the PREAMPLIFIER (a three-op-amp
instrumentation amplifier), the 4th-order HIGH-PASS, the LOW-PASS and the GAIN
stage follow along the middle row to OUT at the right.  The
POLARIZING SWITCH (the MOSFET, its clamp and its sense resistor) hangs under
the relay's pole B.  Along the bottom, the SEQUENCER: the timer, the
POLARIZE IN level detector, the SEQUENCE and MODE switches, the gate delay and
the relay hold, the relay's driver and SYNC OUT.  Power comes in at the top
right.  Every signal is a drawn wire; only the rails and ground use power
symbols.

Every value the design arithmetic computes is read from sim/design.json
(sim/design.py), by the key of the parts table it was fitted to.  References
are fixed here, block by block, so adding a part never renumbers another.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kienv, parts
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "hardware", "earthnmr.kicad_sch")
DESIGN = os.path.join(HERE, "..", "sim", "design.json")
LOCAL_SYM = os.path.join(HERE, "..", "hardware", "lib", "earthnmr.kicad_sym")

G = 2.54


def g(n):
    """Grid units to millimetres."""
    return round(n * G, 4)


def design():
    return json.load(open(DESIGN))


def passive_fields(value):
    p = parts.PASSIVES.get(value)
    return {"LCSC": p["lcsc"], "MPN": p["mpn"]} if p else {}


def part_fields(key):
    p = parts.PARTS[key]
    return {"LCSC": p["lcsc"], "MPN": p["mpn"]}


def fp(key):
    return parts.PARTS[key]["footprint"]


def sym(key):
    return parts.PARTS[key]["symbol"]


# Every probe loop has a fixed number, so the board's placement (keyed by
# reference) never slides when a loop is added to the sheet.
TP_NUMBER = {"V POL": 1, "DRAIN": 2, "I POL": 3, "GATE": 4, "TANK+": 5, "TANK-": 6,
             "INA A": 7, "INA B": 8, "PREAMP": 9, "HP1": 10, "HP": 11, "LP": 12, "OUT": 13,
             "POL CMD": 14, "DELAY": 15, "HOLD": 16, "RELAY": 17, "TIMER": 18, "EXT": 19,
             "+15V": 20, "-15V": 21, "PHONES": 22}


class Draw:
    """The sheet and the small drawing helpers every block uses."""

    def __init__(self, D):
        self.D = D
        self.s = Sheet(kienv.share_dir(), paper="A1",
                       title=f"{parts.BOARD_NAME}: proton precession in the Earth's field",
                       date=parts.BOARD_DATE, rev=parts.REV,
                       company="Jason Gallicchio and Claude",
                       comments=[f"Larmor frequency {D['site']['f_L']:.0f} Hz at {D['site']['name']} "
                                 f"({D['site']['F_nT'] / 1000:.1f} uT, {D['site']['source']})",
                                 f"{D['world']['f_L'][0]:.0f}-{D['world']['f_L'][1]:.0f} Hz anywhere on Earth",
                                 "OPA197 for every amplifier, TS391 comparators, NE555 timer, IRFS4227 switch, HFD3 relay",
                                 "Open source, CERN-OHL-P-2.0 -- " + parts.PROJECT_URL])
        self.s.add_local_lib(LOCAL_SYM, "earthnmr")
        self.npwr = 0
        self.nflg = 0
        self.nbyp = 80
        self.ngnd_tp = 100

    # ---------------------------------------------------------- symbols --
    def pwr_ref(self):
        self.npwr += 1
        return f"#PWR{self.npwr:04d}"

    def gnd(self, x, y, up=False):
        self.s.place("power:GND", self.pwr_ref(), "GND", x, y, rot=180 if up else 0,
                     in_bom=False, on_board=False, hide_ref=True, hide_value=True)

    def rail(self, name, x, y, down=False):
        """+15V's arrow points up from a wire below it; -15V's (down=True) points
        down from a wire above it."""
        rot = 180 if down else 0
        self.s.place(f"power:{name}", self.pwr_ref(), name, x, y, rot=rot, in_bom=False,
                     on_board=False, hide_ref=True,
                     val_off=(0, -3.81) if rot == 0 else (0, 3.81))

    def flag(self, x, y, to_x):
        """A PWR_FLAG lying on a wire at (to_x, y), from the left or the right."""
        self.nflg += 1
        left = x < to_x
        self.s.place("power:PWR_FLAG", f"#FLG{self.nflg:02d}", "PWR_FLAG", x, y,
                     in_bom=False, on_board=False, hide_ref=True,
                     rot=90 if left else 270,
                     val_off=(-3.81, 0) if left else (3.81, 0),
                     val_justify="right" if left else "left")
        self.s.wire((x, y), (to_x, y))

    def res(self, ref, value, x, y, rot=0, side="right", text="split", fields=None, footprint=None,
            hide=False, label=None):
        """R_US: rot 0 vertical (pin 1 top), rot 90 horizontal (pin 1 left).
        Returns (pin 1, pin 2)."""
        if rot == 0:
            dx = 2.4 if side == "right" else -2.4
            ro, vo, j = (dx, -1.4), (dx, 1.4), ("left" if side == "right" else "right")
        elif text == "above":
            ro, vo, j = (0, -4.4), (0, -2.6), None
        elif text == "below":
            ro, vo, j = (0, 2.6), (0, 4.4), None
        else:
            ro, vo, j = (0, -2.6), (0, 2.6), None
        self.s.place("Device:R_US", ref, label or parts.printed(value), x, y, rot=rot,
                     footprint=footprint or fp("R_0805"),
                     fields=fields if fields is not None else passive_fields(value),
                     ref_off=ro, val_off=vo, ref_justify=j, val_justify=j, hide_ref=hide, hide_value=hide)
        if rot == 0:
            return (x, y - 3.81), (x, y + 3.81)
        return (x - 3.81, y), (x + 3.81, y)

    def cap(self, ref, key, x, y, rot=0, side="right", text="split", hide=False):
        """Device:C, vertical (rot 0, pin 1 top) or horizontal (rot 90, pin 1 left)."""
        p = parts.PASSIVES[key]
        foot = fp(p.get("footprint", "C_0805"))
        if rot == 0:
            dx = 2.6 if side == "right" else -2.6
            j = "left" if side == "right" else "right"
            ro, vo = (dx, -1.4), (dx, 1.4)
        elif text == "above":
            ro, vo, j = (0, -4.6), (0, -2.8), None
        elif text == "below":
            ro, vo, j = (0, 2.8), (0, 4.6), None
        else:
            ro, vo, j = (0, -2.8), (0, 2.8), None
        self.s.place("Device:C", ref, parts.printed(key), x, y, rot=rot, footprint=foot,
                     fields=passive_fields(key), ref_off=ro, val_off=vo,
                     ref_justify=j, val_justify=j, hide_ref=hide, hide_value=hide)
        if rot == 0:
            return (x, y - 3.81), (x, y + 3.81)
        return (x - 3.81, y), (x + 3.81, y)

    def diode(self, ref, key, x, y, rot, side="right", value=None):
        """Device:D and its cousins: rot 0 cathode left; 90 anode top; 180
        cathode right; 270 cathode top.  Returns (cathode, anode)."""
        if rot in (90, 270):
            dx = 2.6 if side == "right" else -2.6
            ro, vo, j = (dx, -1.4), (dx, 1.4), ("left" if side == "right" else "right")
        else:
            ro, vo, j = (0, -2.8), (0, 2.8), None
        self.s.place(sym(key), ref, value or parts.PARTS[key]["value"], x, y, rot=rot,
                     footprint=fp(key), fields=part_fields(key),
                     ref_off=ro, val_off=vo, ref_justify=j, val_justify=j)
        return self.s.pin(ref, 1, "1"), self.s.pin(ref, 1, "2")

    def led(self, ref, key, x, y, up=True):
        """An LED standing: up=True anode on top (rot 90)."""
        self.s.place("Device:LED", ref, parts.PARTS[key]["value"], x, y, rot=90 if up else 270,
                     footprint=fp(key), fields=part_fields(key), ref_off=(2.8, -1.4), val_off=(2.8, 1.4),
                     ref_justify="left", val_justify="left")
        k, a = self.s.pin(ref, 1, "1"), self.s.pin(ref, 1, "2")
        return k, a

    def testpoint(self, x, y, name, rot=0, dx=1.8, dy=-3.0, justify="left"):
        """A test loop at the node, carrying the name of what it probes.
        rot 0: loop above the wire, 180 below, 90 left of a vertical wire, 270 right."""
        if name == "GND":
            n = self.ngnd_tp
            self.ngnd_tp += 1
        else:
            n = TP_NUMBER[name]
        ref = f"TP{n}"
        self.s.place("Connector:TestPoint", ref, name, x, y, rot=rot,
                     footprint=fp("TP"), fields=part_fields("TP"),
                     hide_ref=True, val_off=(dx, dy), val_justify=justify)
        return ref

    def text(self, lines, x, y, size=1.05, pitch=None):
        if isinstance(lines, str):
            lines = [lines]
        for i, line in enumerate(lines):
            if line:
                self.s.text(line, x, y + i * (pitch or size * 1.8), size=size)

    def title(self, name, x, y, lines=(), size=1.8):
        self.s.text(name, x, y, size=size)
        self.text(list(lines), x, y + size * 1.3, size=1.05)

    def label(self, txt, x, y, size=1.0, justify="left"):
        self.s.label(txt, x, y, size=size, justify=justify)

    # ---------------------------------------------------------- blocks ---
    def bypass(self, pin, rail_name):
        """A supply pin's stub to its rail symbol, with its own 100 nF lying
        beside the stub to ground: one capacitor per supply pin, at the pin."""
        up = rail_name == "+15V" or (rail_name == "GND_TOP")
        x, y = pin
        sgn = -1 if pin_dir(self, pin) == "up" else 1
        end = (x, y + sgn * g(2))
        self.s.wire(pin, end)
        if rail_name == "GND":
            self.gnd(*end)
            return
        self.rail(rail_name, *end, down=(sgn > 0))
        cy = y + sgn * g(1)
        c = f"C{self.nbyp}"
        self.nbyp += 1
        self.s.wire((x, cy), (x + g(1), cy))
        self.cap(c, "100nF", x + g(2.5), cy, rot=90, hide=True)
        self.gnd(x + g(4), cy)

    def opamp(self, ref, x, y, mirror=None):
        """An OPA197 at (x, y), + on top (mirror="x": - on top).  Returns
        (+ pin, - pin, output pin)."""
        s = self.s
        s.place(sym("OPAMP"), ref, "OPA197", x, y, footprint=fp("OPAMP"), mirror=mirror,
                fields=part_fields("OPAMP"), ref_off=(2.0 if len(ref) <= 2 else 0.9, -1.2 if mirror != "x" else 1.2),
                val_off=(2.0, 1.2), ref_justify="left", val_justify="left", hide_value=True)
        vp, vm = s.pin(ref, 1, "5"), s.pin(ref, 1, "2")
        self._dirs[vp] = "up" if vp[1] < y else "down"
        self._dirs[vm] = "up" if vm[1] < y else "down"
        self.bypass(vp, "+15V")
        self.bypass(vm, "-15V")
        return s.pin(ref, 1, "3"), s.pin(ref, 1, "4"), s.pin(ref, 1, "1")

    def comparator(self, ref, x, y):
        """A TS391 at (x, y) on +15 V and ground, + on top.  Returns (+, -, out)."""
        s = self.s
        s.place(sym("COMP"), ref, "TS391", x, y, footprint=fp("COMP"),
                fields=part_fields("COMP"), ref_off=(2.0 if len(ref) <= 2 else 0.9, -1.2), val_off=(2.0, 1.2),
                ref_justify="left", val_justify="left", hide_value=True)
        vp, vm = s.pin(ref, 1, "5"), s.pin(ref, 1, "2")
        self._dirs[vp] = "up"
        self._dirs[vm] = "down"
        self.bypass(vp, "+15V")
        self.bypass(vm, "GND")
        return s.pin(ref, 1, "4"), s.pin(ref, 1, "3"), s.pin(ref, 1, "1")

    def follower_fb(self, pm, po, x_op, below=True):
        """Unity-gain feedback: from the - input down past the V- stub's pin and
        across to the output column, crossing the stub's wire (not its pin)."""
        ox = po[0] + g(1.5)
        yy = pm[1] + g(2.5) if below else pm[1] - g(2.5)
        self.s.wire(pm, (pm[0], yy), (ox, yy), (ox, po[1]))
        self.s.wire(po, (ox, po[1]))
        return ox

    def switch(self, ref, title, x, y, mirror, lines, text_at, rot=0):
        """An SPDT slide switch with what each position does printed beside it."""
        s = self.s
        s.place(sym("SW"), ref, title, x, y, rot=rot, mirror=mirror, footprint=fp("SW"),
                fields=part_fields("SW"), hide_ref=True, hide_value=True)
        tx, ty = text_at
        s.text(f"{ref}  {title}", tx, ty, size=1.15)
        for i, ln in enumerate(lines):
            s.text(ln, tx, ty + 2.1 * (i + 1), size=1.0)
        return s.pin(ref, 1, "1"), s.pin(ref, 1, "2"), s.pin(ref, 1, "3")

    def bnc(self, ref, x, y, name, lines, facing, text_at):
        """A BNC jack.  facing='left': an input at the board's left edge, its pin
        on the right; 'right': an output, its pin on the left."""
        s = self.s
        mir = "y" if facing == "left" else None
        s.place("Connector:Conn_Coaxial", ref, "BNC", x, y, mirror=mir,
                footprint=fp("BNC"), fields=part_fields("BNC"),
                ref_off=(-5.6 if facing == "left" else 3.0, 4.0), val_off=(-5.6 if facing == "left" else 3.0, 5.8),
                ref_justify="right" if facing == "left" else "left",
                val_justify="right" if facing == "left" else "left", hide_value=True)
        pin, shield = s.pin(ref, 1, "1"), s.pin(ref, 1, "2")
        s.wire(shield, (shield[0], shield[1] + g(1)))
        self.gnd(shield[0], shield[1] + g(1))
        self.title(name, *text_at, lines=lines, size=2.0)
        return pin


def pin_dir(d, pin):
    return d._dirs.get(pin, "up")


def build():
    D = design()
    d = Draw(D)
    d._dirs = {}
    s = d.s
    c = D["coil"]

    # ================================================== the story ============
    d.text([f"{parts.BOARD_NAME.upper()} -- a proton precession spectrometer",
            "",
            "A coil round a bottle of water.  POLARIZE: a few amperes through the coil for a few seconds magnetize the",
            f"water's protons along the coil's field, a few hundred times more than the Earth's {D['site']['F_nT'] / 1000:.0f} uT alone would.",
            "Switch off: in a millisecond the field is gone, faster than the protons can follow, and they precess about the",
            f"Earth's field at f = 42.58 Hz/uT x B: {D['site']['f_L']:.0f} Hz here, a few microvolts in the same coil, dying away in a",
            "fraction of a second to a few seconds (T2*).  LISTEN: the relay hands the coil to a tank tuned to f, and the",
            "preamplifier and the filters raise the microvolts to a volt.",
            f"The reference coil (handbook): {c['N']} turns of AWG 20 on 3-inch pipe, {c['L'] * 1e3:.0f} mH, {c['R']:.1f} ohm, Q {c['Q']:.0f}.  At "
            f"{c['I_pol']:.1f} A: {c['B_p'] * 1e3:.1f} mT,",
            f"about {c['emf'] * 1e6:.1f} uV in the coil from 1 L of water, {c['v_tank'] * 1e6:.0f} uV across the tank, "
            f"{D['fid_out_hi']:.1f} V at OUT on HIGH gain."],
           g(8), g(5), size=1.5, pitch=2.9)

    # ===================================================== POLARIZING SUPPLY ==
    VPOL_Y = g(36)
    s.place(sym("TERM2"), "J2", "POLARIZE SUPPLY", g(14), VPOL_Y, mirror="y", footprint=fp("TERM2"),
            fields=part_fields("TERM2"), ref_off=(-3.0, 5.6), val_off=(-3.0, 7.4), hide_value=True,
            ref_justify="right", val_justify="right")
    j2p, j2m = s.pin("J2", 1, "1"), s.pin("J2", 1, "2")
    ps = D["pol_supply"]
    d.title("POLARIZING SUPPLY", g(8), g(26.5),
            [f"{ps['V'][0]:.0f}-{ps['V'][1]:.0f} V, up to {ps['I_max']:.0f} A.  A bench supply in",
             "constant current sets the coil's current;", "or the coil's resistance does:",
             f"the reference coil draws {ps['I_max']:.0f} A at {ps['V_max_ref_coil']:.0f} V."], size=2.0)
    FX = g(19.5)
    s.place(sym("PTC"), "F1", "3A", FX, VPOL_Y, rot=90, footprint=fp("PTC"), fields=part_fields("PTC"),
            ref_off=(0, -2.8), val_off=(0, 2.8))
    f1, f2 = s.pin("F1", 1, "1"), s.pin("F1", 1, "2")
    fl, fr = (f1, f2) if f1[0] < f2[0] else (f2, f1)
    s.wire(j2p, fl)
    # the crowbar: a reversed supply forward-biases D5 and trips F1
    X5, X6, XC5, XL3 = g(23), g(29), g(35), g(40)
    k5, a5 = d.diode("D5", "DSCH", X5, VPOL_Y + g(2.5), rot=270, side="left")
    s.wire((X5, VPOL_Y), k5)
    s.wire(a5, (X5, VPOL_Y + g(5)))
    d.gnd(X5, VPOL_Y + g(5))
    s.wire(j2m, (j2m[0] + g(1), j2m[1]), (j2m[0] + g(1), VPOL_Y + g(5)))
    d.gnd(j2m[0] + g(1), VPOL_Y + g(5))
    k6, a6 = d.diode("D6", "TVS_SUPPLY", X6, VPOL_Y + g(2.5), rot=270, side="left")
    s.wire((X6, VPOL_Y), k6)
    s.wire(a6, (X6, VPOL_Y + g(5)))
    d.gnd(X6, VPOL_Y + g(5))
    s.place(sym("CPOL"), "C5", "470uF", XC5, VPOL_Y + g(2.5), footprint=fp("CPOL"),
            fields=part_fields("CPOL"), ref_off=(-2.6, -1.4), val_off=(-2.6, 1.4),
            ref_justify="right", val_justify="right")
    s.wire((XC5, VPOL_Y), (XC5, VPOL_Y + g(1)))
    s.wire((XC5, VPOL_Y + g(4)), (XC5, VPOL_Y + g(5)))
    d.gnd(XC5, VPOL_Y + g(5))
    r3a, r3b = d.res("R3", "15k", XL3, VPOL_Y + g(2.5))
    s.wire((XL3, VPOL_Y), r3a)
    k3, a3 = d.led("LED3", "LED", XL3, VPOL_Y + g(7.5))
    s.wire(r3b, a3)
    s.wire(k3, (XL3, VPOL_Y + g(10)))
    d.gnd(XL3, VPOL_Y + g(10))
    d.text(["LED3: the supply is there"], g(30), VPOL_Y + g(12), size=1.0)
    XV = g(44)                       # +V POL comes down this column to the relay
    s.wire(fr, (XV, VPOL_Y))
    d.testpoint(XV - g(2), VPOL_Y, "V POL", rot=0)
    d.text(["V POL: behind the 3 A fuse"], XV - g(8), VPOL_Y - g(3.2), size=1.0)

    # ============================================ the COIL and the RELAY ======
    POLE_X = g(30)
    YA, YB = g(64), g(72)
    # turned 180 so the shield (3) is on top and pin 1 at the bottom, as on the board:
    # the middle pin goes to pole A's common, the bottom pin to pole B's
    s.place(sym("TERM3"), "J3", "COIL", g(14), g(68), rot=180, footprint=fp("TERM3"),
            fields=part_fields("TERM3"), ref_off=(3.0, 4.6), val_off=(3.0, 6.0), hide_value=True,
            ref_justify="right", val_justify="right")
    j3b, j3a, j3s = s.pin("J3", 1, "1"), s.pin("J3", 1, "2"), s.pin("J3", 1, "3")
    assert j3s[1] < j3a[1] < j3b[1], (j3s, j3a, j3b)
    d.title("COIL", g(8), g(52.0), ["A (2), B (1): the coil's two leads", "S (3): its shield, if any",
                                    "up to 130 V at switch-off:", "do not touch",
                                    "10-200 mH, up to 3 A, 1/2 L I^2 < 1 J"], size=2.4)
    s.wire(j3s, (j3s[0] + g(1), j3s[1]), (j3s[0] + g(1), j3s[1] - g(2)))
    d.gnd(j3s[0] + g(1), j3s[1] - g(2), up=True)
    # pole A turned so its common faces the coil and normally-open looks up;
    # pole B so normally-open looks down, to the switch under it
    s.place(sym("RELAY"), "K1", "HFD3/12", POLE_X, YA, rot=270, mirror="x", unit=2,
            footprint=fp("RELAY"), fields=part_fields("RELAY"), hide_ref=True, hide_value=True)
    s.place(sym("RELAY"), "K1", "HFD3/12", POLE_X, YB, rot=270, unit=3,
            footprint=fp("RELAY"), fields=part_fields("RELAY"), hide_ref=True, hide_value=True)
    comA, ncA, noA = s.pin("K1", 2, "4"), s.pin("K1", 2, "3"), s.pin("K1", 2, "5")
    comB, ncB, noB = s.pin("K1", 3, "9"), s.pin("K1", 3, "10"), s.pin("K1", 3, "8")
    assert noA[1] < ncA[1] and ncB[1] < noB[1] and comA[0] < noA[0], (comA, noA, ncA, comB, ncB, noB)
    s.wire(j3a, (g(25), j3a[1]), (g(25), comA[1]), comA)
    s.wire(j3b, (g(23), j3b[1]), (g(23), comB[1]), comB)
    d.label("COIL_A", g(17), j3a[1])
    d.label("COIL_B", g(17), j3b[1])
    s.wire(noA, (XV, noA[1]), (XV, VPOL_Y))
    d.label("V_POL", XV - g(6), noA[1])
    d.text(["K1 HFD3/12: released, the coil LISTENS (as drawn);",
            "energized, it is POLARIZED:", "A to V POL, B to the switch"], POLE_X - g(6), YA - g(9.5), size=1.0)

    # ================================================== POLARIZING SWITCH =====
    QX, QY = g(35), g(84)
    s.place(sym("MOSFET"), "Q1", "IRFS4227", QX, QY, footprint=fp("MOSFET"),
            fields=part_fields("MOSFET"), ref_off=(5.2, -1.4), val_off=(5.2, 0.4),
            ref_justify="left", val_justify="left")
    qg, qd, qs = s.pin("Q1", 1, "1"), s.pin("Q1", 1, "2"), s.pin("Q1", 1, "3")
    s.wire(noB, (qd[0], noB[1]), qd)
    d.label("DRAIN", noB[0] + g(0.5), noB[1])
    d.testpoint(qd[0], g(76), "DRAIN", rot=270, dx=3.4, dy=0.0)
    d.text(["DRAIN: up to 160 V,", "a x10 probe"], qd[0] + g(1.5), g(77.4), size=1.0)
    DCX = g(42)
    k7, a7 = d.diode("D7", "TVS_CLAMP", DCX, QY, rot=270)
    s.wire((qd[0], g(79)), (DCX, g(79)), k7)
    SRC_Y = qs[1] + g(1)
    s.wire(qs, (qs[0], SRC_Y))
    s.wire(a7, (DCX, SRC_Y), (qs[0], SRC_Y))
    r4a, r4b = d.res("R4", "0.1R", qs[0], SRC_Y + g(1.5), fields=part_fields("RSENSE"),
                     footprint=fp("RSENSE"), label="0.1R")
    s.wire(r4b, (qs[0], r4b[1] + g(1)))
    d.gnd(qs[0], r4b[1] + g(1))
    d.text([f"D7 SMCJ100A holds the drain near {D['switch_off']['v_clamp_3A']:.0f} V",
            "while the coil's current falls to zero in a",
            f"straight line ({D['switch_off']['t_ramp_ref'] * 1e3:.1f} ms for the reference coil):",
            "faster than the protons can follow"], g(30), g(93), size=1.0)
    # the gate: 47 ohm in, 100k to the source
    r5a, r5b = d.res("R5", D["gate"]["R_g"], qg[0] - g(2.5), qg[1], rot=90, text="above")
    s.wire(r5b, qg)
    GATE_X = g(26)
    s.wire((GATE_X, qg[1]), r5a)
    r6a, r6b = d.res("R6", D["gate"]["R_gs"], qg[0] - g(0.5), SRC_Y - g(1.5), side="left")
    s.wire(r6b, (qs[0] - g(1.5), SRC_Y), (qs[0], SRC_Y))
    d.label("SOURCE", qs[0] - g(1.2), SRC_Y)
    d.testpoint(qs[0] - g(1.5), SRC_Y, "I POL", rot=180, dx=-1.8, dy=3.6, justify="right")
    d.text(["I POL: 0.1 V per ampere,", "on and ramping off"], g(16), SRC_Y + g(2.4), size=1.0)

    # ======================================================= the TANK =========
    TP_Y, TN_Y = g(56), g(86)
    s.wire(ncA, (g(48), ncA[1]), (g(48), TP_Y), (g(50), TP_Y))
    s.wire(ncB, (g(47), ncB[1]), (g(47), TN_Y), (g(50), TN_Y))
    d.label("TANK+", g(48) + 0.3, TP_Y)
    d.label("TANK-", g(47) + 0.3, TN_Y)
    TVX = g(52)
    s.place(sym("TVS_TANK"), "D9", "SMBJ12CA", TVX, (TP_Y + TN_Y) / 2, rot=90,
            footprint=fp("TVS_TANK"), fields=part_fields("TVS_TANK"),
            ref_off=(2.6, -1.4), val_off=(2.6, 0.4), ref_justify="left", val_justify="left")
    d9a, d9b = s.pin("D9", 1, "1"), s.pin("D9", 1, "2")
    top9, bot9 = (d9a, d9b) if d9a[1] < d9b[1] else (d9b, d9a)
    s.wire((TVX, TP_Y), top9)
    s.wire(bot9, (TVX, TN_Y))
    d.text(["D9: a clamp, idle", "unless a fault dumps", "the coil's energy here"], TVX + g(1), g(76.5), size=0.95)
    # the bank: the DIP standing with its switches vertical; each switch's lower
    # pin a binary weight of C0G capacitance down to TANK-
    DIPX, DIPY = g(78), g(61)
    s.place(sym("DIP8"), "SW1", "TUNE", DIPX, DIPY, rot=90, footprint=fp("DIP8"),
            fields=part_fields("DIP8"), hide_ref=True, hide_value=True)
    tops = [s.pin("SW1", 1, str(17 - k)) for k in range(1, 9)]
    bots = [s.pin("SW1", 1, str(k)) for k in range(1, 9)]
    assert all(abs(t[0] - b[0]) < 0.01 and t[1] < b[1] for t, b in zip(tops, bots)), (tops, bots)
    for t in tops:
        s.wire(t, (t[0], TP_Y))
    d.text(["SW1 TUNE"], tops[0][0] - g(6), DIPY + 0.4, size=1.15)
    bank = D["bank"]["switches"]
    gap_x = (bots[3][0] + bots[4][0]) / 2          # between switches 4 and 5
    combs = [None] * 8
    x = gap_x - g(1.5)
    for k in (3, 2, 1, 0):                          # the left four, right to left
        n = len(bank[k]["parts"])
        combs[k] = [x - g(2) * (n - 1 - i) for i in range(n)]
        x = combs[k][0] - g(3)
    x = gap_x + g(1.5)
    for k in (4, 5, 6, 7):
        n = len(bank[k]["parts"])
        combs[k] = [x + g(2) * i for i in range(n)]
        x = combs[k][-1] + g(3)
    CAP_Y = g(80)
    BIT_Y = CAP_Y - g(2.5)
    cref = 10
    for k, b in enumerate(bank):
        bx, by = bots[k]
        xs = combs[k]
        near = xs[-1] if k < 4 else xs[0]
        level = BIT_Y - g(abs(k - 3.5) + 0.5)
        s.wire((bx, by), (bx, level), (near, level), (near, BIT_Y))
        if len(xs) > 1:
            s.wire((xs[0], BIT_Y), (xs[-1], BIT_Y))
        for i, xx in enumerate(xs):
            d.cap(f"C{cref}", b["parts"][i], xx, CAP_Y, hide=True)
            cref += 1
            s.wire((xx, BIT_Y), (xx, CAP_Y - 3.81))
            s.wire((xx, CAP_Y + 3.81), (xx, TN_Y))
        s.text(f"{b['sw']}:", xs[0] - 1.6, CAP_Y - 1.0, size=1.0, justify="right")
        s.text(f"{b['C'] * 1e9:.1f}n", xs[0] - 1.6, CAP_Y + 1.2, size=0.9, justify="right")
    assert cref == 30, cref
    TANK_X1 = combs[-1][-1] + g(5)
    s.wire((TVX, TP_Y), (TANK_X1, TP_Y))
    s.wire((g(50), TP_Y), (TVX, TP_Y))
    s.wire((g(50), TN_Y), (TANK_X1, TN_Y))
    d.text([f"SW1 TUNE: each switch adds its capacitance (C0G) to the tank, in {D['bank']['step'] * 1e9:.1f} nF steps up to "
            f"{D['bank']['C_max'] * 1e9:.0f} nF.",
            "Resonance: f = 1 / (2 pi sqrt(L C)); tune to the Larmor frequency for the most signal.",
            f"The reference coil needs {D['coil']['C_res'] * 1e9:.0f} nF at {D['site']['f_L']:.0f} Hz.  "
            "Caps C10-C29: 3.3n, 6.8n, 10n 0805, 47n, 100n 1206"],
           combs[0][0] - g(1), TN_Y + g(3), size=1.05)
    d.testpoint(TANK_X1 - g(2), TP_Y, "TANK+", rot=0)
    d.testpoint(TANK_X1 - g(2), TN_Y, "TANK-", rot=180, dy=3.6)
    # calibration: a generator through 1M into TANK+, terminated in 51 ohm at the jack
    jc = d.bnc("J4", g(56), g(47), "CAL IN", ["a generator through 1M: I = V / 1M", "into the tank.  mV-level, 5 Vpp max"],
               facing="left", text_at=(g(60), g(40.5)))
    r13a, r13b = d.res("R13", "51R", jc[0] + g(2), jc[1] + g(3.5), side="right")
    s.wire((jc[0] + g(2), jc[1]), r13a)
    d.gnd(*r13b)
    r14a, r14b = d.res("R14", "1M", jc[0] + g(5), jc[1], rot=90)
    s.wire(jc, r14a)
    s.wire(r14b, (g(66), jc[1]), (g(66), TP_Y))

    # ================================================== the PREAMPLIFIER ======
    # U1 (+ on top) takes TANK+, U2 (mirrored, - on top) TANK-; between their -
    # inputs 10k / 200R / 10k set the gain, 1 + 2 Rf / Rg.
    UX = TANK_X1 + g(16)
    U1Y, U2Y = TP_Y + g(1), TN_Y - g(1)
    p1, m1, o1 = d.opamp("U1", UX, U1Y)
    p2, m2, o2 = d.opamp("U2", UX, U2Y, mirror="x")
    assert m2[1] < p2[1], (m2, p2)
    rs = D["ina"]["R_series"]
    r15a, r15b = d.res("R15", rs, p1[0] - g(4), p1[1], rot=90, text="above")
    s.wire((TANK_X1, TP_Y), r15a)
    s.wire(r15b, p1)
    r16a, r16b = d.res("R16", rs, p2[0] - g(4), p2[1], rot=90, text="below")
    s.wire((TANK_X1, TN_Y), r16a)
    s.wire(r16b, p2)
    BX = p1[0] - g(1)
    r11a, r11b = d.res("R11", D["ina"]["R_bias"], BX, p1[1] - g(2.5), side="left")
    s.wire((BX, p1[1]), r11b)
    d.gnd(r11a[0], r11a[1], up=True)
    r12a, r12b = d.res("R12", D["ina"]["R_bias"], BX, p2[1] + g(2.5), side="left")
    s.wire((BX, p2[1]), r12a)
    d.gnd(*r12b)
    CX = m1[0] - g(2)
    s.wire(m1, (CX, m1[1]))
    s.wire(m2, (CX, m2[1]))
    RGY = (m1[1] + m2[1]) / 2
    r19a, r19b = d.res("R19", D["ina"]["R_g"], CX, RGY, side="left")
    s.wire((CX, m1[1]), r19a)
    s.wire(r19b, (CX, m2[1]))
    FY1, FY2 = U1Y + g(7), U2Y - g(7)
    OX1 = o1[0] + g(1.5)
    r17a, r17b = d.res("R17", D["ina"]["R_f"], UX, FY1, rot=90, text="below")
    s.wire((CX, FY1), r17a)
    s.wire(o1, (OX1, o1[1]), (OX1, FY1), r17b)
    r18a, r18b = d.res("R18", D["ina"]["R_f"], UX, FY2, rot=90, text="above")
    s.wire((CX, FY2), r18a)
    s.wire(o2, (OX1, o2[1]), (OX1, FY2), r18b)
    s.wire((OX1, o1[1]), (OX1 + g(1), o1[1]))
    s.wire((OX1, o2[1]), (OX1 + g(1), o2[1]))
    d.testpoint(OX1 + g(1), o1[1], "INA A", rot=0)
    d.testpoint(OX1 + g(1), o2[1], "INA B", rot=180, dy=3.6)
    d.text([f"gain {D['ina']['gain']:.0f} = 1 + 2 x {D['ina']['R_f']} / {D['ina']['R_g']}",
            "(between the two - inputs)"], CX - g(17), RGY - g(1), size=1.05)
    # U3: the difference amplifier, 4 x 10k, gain 1: INA A - INA B
    DX_ = OX1 + g(16)
    p3, m3, o3 = d.opamp("U3", DX_, (U1Y + U2Y) / 2)
    rd = D["ina"]["R_diff"]
    XA, XB = OX1 + g(4), OX1 + g(3)
    s.wire((OX1 + g(1), o1[1]), (XA, o1[1]), (XA, p3[1]))
    s.wire((OX1 + g(1), o2[1]), (XB, o2[1]), (XB, m3[1]))
    r21a, r21b = d.res("R21", rd, p3[0] - g(5), p3[1], rot=90, text="above")
    s.wire((XA, p3[1]), r21a)
    s.wire(r21b, p3)
    r20a, r20b = d.res("R20", rd, p3[0] - g(5), m3[1], rot=90, text="below")
    s.wire((XB, m3[1]), r20a)
    s.wire(r20b, m3)
    r22a, r22b = d.res("R22", rd, p3[0] - g(1.5), p3[1] - g(3.5), side="left")
    s.wire((p3[0] - g(1.5), p3[1]), r22b)
    d.gnd(r22a[0], r22a[1], up=True)
    O3X = o3[0] + g(1.5)
    r23a, r23b = d.res("R23", rd, DX_, m3[1] + g(6), rot=90, text="below")
    s.wire((m3[0] - g(1.5), m3[1]), (m3[0] - g(1.5), m3[1] + g(6)), r23a)
    s.wire(o3, (O3X, o3[1]), (O3X, m3[1] + g(6)), r23b)
    s.wire((O3X, o3[1]), (O3X + g(1), o3[1]))
    d.testpoint(O3X + g(1), o3[1], "PREAMP", rot=0)
    d.title("PREAMPLIFIER", UX - g(10), g(44),
            [f"an instrumentation amplifier, gain {D['ina']['gain']:.0f}: U1 and U2 amplify each side",
             "of the tank, U3 takes the difference, so pickup common to both cancels.",
             "OPA197: 5.5 nV/rtHz and no current noise against the tank's",
             f"{D['coil']['Rp'] / 1e3:.0f} k: {D['noise']['nf_db']:.1f} dB noise figure with the reference coil.",
             "R11, R12 (1M) give the inputs their DC; R15, R16 (1k) limit a fault's",
             "current into them"])

    # ================================================== the FILTERS ===========
    SIG_Y = o3[1]

    def sallen_key(refs, x, kind, vals, in_pt):
        """A unity-gain Sallen-Key section at op-amp (x, SIG_Y + 1 g).  kind
        'hp': C, C in series, R1 from their node to the output, R2 from + to
        ground.  'lp': R, R in series, C1 from their node to the output, C2 from
        + to ground.  Returns the output column's point."""
        u, sa, sb, fb, sh = refs
        pp, pm, po = d.opamp(u, x, SIG_Y + g(1))
        xa = pp[0] - g(5)
        if kind == "hp":
            d.cap(sa, vals["C"], xa - g(1.5), pp[1], rot=90, text="above")
            d.cap(sb, vals["C"], xa + g(2), pp[1], rot=90, text="above")
        else:
            d.res(sa, vals["R1"], xa - g(1.5), pp[1], rot=90, text="below")
            d.res(sb, vals["R2"], xa + g(2), pp[1], rot=90, text="below")
        s.wire((xa, pp[1]), (xa + g(0.5), pp[1]))
        s.wire((xa + g(3.5), pp[1]), pp)
        s.wire(in_pt, (xa - g(4), in_pt[1]), (xa - g(4), pp[1]), (xa - g(3), pp[1]))
        # the shunt from + to ground
        sx = pp[0] - g(1)
        if kind == "hp":
            ra, rb = d.res(sh, vals["R2"], sx, pp[1] + g(4.5), side="left")
        else:
            ra, rb = d.cap(sh, vals["C2"], sx, pp[1] + g(4.5), side="left")
        s.wire((sx, pp[1]), ra)
        d.gnd(*rb)
        # the feedback element from the series node over the top to the output
        fy = pp[1] - g(6.5)
        ox = po[0] + g(1.5)
        if kind == "hp":
            fa, fbb = d.res(fb, vals["R1"], x, fy, rot=90, text="above")
        else:
            fa, fbb = d.cap(fb, vals["C1"], x, fy, rot=90, text="above")
        s.wire((xa + g(0.5), pp[1]), (xa + g(0.5), fy), fa)
        s.wire(po, (ox, po[1]), (ox, fy), fbb)
        # unity gain: - to the output, under the op-amp
        yy = pm[1] + g(6)
        s.wire(pm, (pm[0], yy), (ox, yy), (ox, po[1]))
        s.wire((ox, po[1]), (ox + g(1), po[1]))
        return (ox, po[1])

    h1, h2, lp = D["hp1"], D["hp2"], D["lp"]
    out4 = sallen_key(("U4", "C30", "C31", "R24", "R25"), O3X + g(19), "hp", h1, (O3X + g(1), SIG_Y))
    d.testpoint(out4[0] + g(1), out4[1], "HP1", rot=0)
    out5 = sallen_key(("U5", "C32", "C33", "R26", "R27"), out4[0] + g(19), "hp", h2, (out4[0] + g(1), out4[1]))
    d.testpoint(out5[0] + g(1), out5[1], "HP", rot=0)
    d.title("HIGH-PASS", O3X + g(8), g(50),
            [f"4th-order Butterworth, {D['filter_band']['f_lo']:.0f} Hz: two unity-gain Sallen-Key sections,",
             f"Q {h1['Q']:.2f} at {h1['f0']:.0f} Hz and Q {h2['Q']:.2f} at {h2['f0']:.0f} Hz.  60 Hz {D['filter_db']['60']:.0f} dB, "
             f"180 Hz {D['filter_db']['180']:.0f} dB,",
             f"420 Hz {D['filter_db']['420']:.0f} dB: mains hum and its low harmonics go.  C0G capacitors."])
    out6 = sallen_key(("U6", "R28", "R29", "C34", "C35"), out5[0] + g(19), "lp", lp, (out5[0] + g(1), out5[1]))
    d.testpoint(out6[0] + g(1), out6[1], "LP", rot=0)
    d.title("LOW-PASS", out5[0] + g(8), g(50),
            [f"2nd-order Butterworth, {lp['f0']:.0f} Hz (Q {lp['Q']:.2f}):",
             "the top of the band, and the anti-alias filter",
             "for a sound card.  C0G capacitors."])

    # ================================================== the GAIN stage =========
    gn = D["gain"]
    GX = out6[0] + g(13)
    pp7, pm7, po7 = d.opamp("U7", GX, SIG_Y + g(1))
    s.wire((out6[0] + g(1), out6[1]), (pp7[0] - g(2), out6[1]), (pp7[0] - g(2), pp7[1]), pp7)
    ox7 = po7[0] + g(1.5)
    FY7 = pm7[1] + g(6)
    r30a, r30b = d.res("R30", gn["R_f"], GX, FY7, rot=90, text="below")
    s.wire(pm7, (pm7[0] - g(1), pm7[1]), (pm7[0] - g(1), FY7), r30a)
    s.wire(po7, (ox7, po7[1]), (ox7, FY7), r30b)
    SWX, SWY = pm7[0] - g(3), FY7 + g(7)
    w1, w2, w3 = d.switch("SW2", "GAIN", SWX, SWY, "y",
                          [f"1: LOW, x{gn['total_lo']:.0f} overall ({gn['db_lo']:.0f} dB)",
                           f"3: HIGH, x{gn['total_hi']:.0f} ({gn['db_hi']:.0f} dB)"],
                          text_at=(SWX - g(2), SWY + g(3.5)))
    assert abs(w2[0] - (pm7[0] - g(1))) < 0.01, (w2, pm7)
    s.wire(w2, (pm7[0] - g(1), FY7))
    r31a, r31b = d.res("R31", gn["R_lo"], w1[0] - g(2.5), w1[1], rot=90, text="above")
    r32a, r32b = d.res("R32", gn["R_hi"], w3[0] - g(2.5), w3[1], rot=90, text="below")
    s.wire(w1, r31b)
    s.wire(w3, r32b)
    GDX = r31a[0] - g(1)
    s.wire(r31a, (GDX, r31a[1]), (GDX, r32a[1]))
    s.wire(r32a, (GDX, r32a[1]), (GDX, r32a[1] + g(2)))
    d.gnd(GDX, r32a[1] + g(2))
    s.wire((ox7, po7[1]), (ox7 + g(1), po7[1]))
    d.testpoint(ox7 + g(1), po7[1], "OUT", rot=0)
    d.title("GAIN", GX - g(5), g(50), [f"x{gn['lo']:.0f} or x{gn['hi']:.0f} = 1 + {gn['R_f']} / Rg"])
    # OUT
    r33a, r33b = d.res("R33", D["out"]["R"], ox7 + g(4), po7[1], rot=90, text="above")
    s.wire((ox7 + g(1), po7[1]), r33a)
    j5 = d.bnc("J5", r33b[0] + g(5), po7[1], "OUT", ["the FID, about 1 V on HIGH;",
                                                      "1k in series: for a scope, an ADC",
                                                      "or a sound card's line input"],
               facing="right", text_at=(r33b[0] + g(8), po7[1] - g(6.5)))
    s.wire(r33b, j5)
    # ================================================== the SEQUENCER ==========
    tm, dl, ex = D["timer"], D["delay"], D["ext"]
    d.title("SEQUENCER", g(8), g(124),
            ["POL CMD high = POLARIZE: the relay pulls in at once, and the switch closes "
             f"{dl['t_gate'] * 1e3:.0f} ms later (U9).",
             "POL CMD low: the switch opens at once, the coil's current ramps off through D7, and the relay "
             f"lets go {dl['t_hold'] * 1e3:.0f} ms later (U10): LISTEN."], size=2.2)
    # --- the 555: a diode-steered astable, POLARIZE and LISTEN set independently
    TX_, TY_ = g(40), g(146)
    s.place(sym("TIMER"), "U11", "NE555", TX_, TY_, footprint=fp("TIMER"), fields=part_fields("TIMER"),
            ref_off=(5.0, 9.0), val_off=(5.0, 10.8), ref_justify="left", val_justify="left")
    t_gnd, t_vcc = s.pin("U11", 1, "1"), s.pin("U11", 1, "8")
    t_trig, t_out, t_rst = s.pin("U11", 1, "2"), s.pin("U11", 1, "3"), s.pin("U11", 1, "4")
    t_ctl, t_thr, t_dis = s.pin("U11", 1, "5"), s.pin("U11", 1, "6"), s.pin("U11", 1, "7")
    s.wire(t_gnd, (t_gnd[0], t_gnd[1] + g(1)))
    d.gnd(t_gnd[0], t_gnd[1] + g(1))
    d._dirs[t_vcc] = "up"
    d.bypass(t_vcc, "+15V")
    s.wire(t_ctl, (t_ctl[0], t_ctl[1] - g(2)))
    c53a, c53b = d.cap("C53", "10nF", t_ctl[0] - g(1.5), t_ctl[1] - g(2), rot=90, text="above")
    d.gnd(*c53a)
    s.wire(t_rst, (t_rst[0] - g(1), t_rst[1]), (t_rst[0] - g(1), t_rst[1] - g(5)))
    d.rail("+15V", t_rst[0] - g(1), t_rst[1] - g(5))
    # column A: +15 -> R40 -> RV1 -> X (DIS) -> D10 -> the capacitor node
    XA_ = g(31)
    XD = t_dis[1]
    s.wire(t_dis, (XA_, XD))
    rv1y = XD - g(2)
    s.place(sym("TRIM"), "RV1", "2M", XA_, rv1y, footprint=fp("TRIM"), fields=part_fields("TRIM"),
            ref_off=(-2.4, -1.4), val_off=(-2.4, 0.4), ref_justify="right", val_justify="right")
    v1a, v1w, v1b = s.pin("RV1", 1, "1"), s.pin("RV1", 1, "2"), s.pin("RV1", 1, "3")
    s.wire(v1b, (XA_, XD))
    s.wire(v1w, (v1w[0], XD))
    r40a, r40b = d.res("R40", tm["R_min"], XA_, v1a[1] - g(1.5) - 3.81 + 3.81, side="left")
    if abs(r40b[1] - v1a[1]) > 0.01:
        s.wire(r40b, v1a)
    s.wire(r40a, (XA_, r40a[1] - g(1)))
    d.rail("+15V", XA_, r40a[1] - g(1))
    k10, a10 = d.diode("D10", "DSIG", XA_, XD + g(1.5), rot=90, side="left")
    assert abs(a10[1] - XD) < 0.01 and abs(k10[1] - t_trig[1]) < 0.01, (a10, k10, XD, t_trig)
    s.wire(t_trig, k10)
    s.wire(t_thr, (t_thr[0] - g(1), t_thr[1]), (t_thr[0] - g(1), t_trig[1]))
    CN_Y = g(161)
    s.wire(k10, (XA_, CN_Y))
    d.testpoint(XA_, g(152), "TIMER", rot=270, dx=4.4, dy=0.0)
    d.text(["RV1  POLARIZE TIME", f"{tm['t_pol'][0]:.1f}-{tm['t_pol'][1]:.1f} s, clockwise longer"],
           g(10), rv1y - g(1), size=1.0)
    # column B: X -> RV2 -> R41 -> D11 (cathode up) -> the capacitor node
    XB_ = g(24)
    s.wire((XA_, XD), (XB_, XD))
    rv2y = XD + g(2)
    s.place(sym("TRIM"), "RV2", "2M", XB_, rv2y, footprint=fp("TRIM"), fields=part_fields("TRIM"),
            ref_off=(-2.4, -1.4), val_off=(-2.4, 0.4), ref_justify="right", val_justify="right")
    v2a, v2w, v2b = s.pin("RV2", 1, "1"), s.pin("RV2", 1, "2"), s.pin("RV2", 1, "3")
    s.wire((XB_, XD), v2a)
    s.wire(v2w, (v2w[0], v2b[1] + g(1)), (XB_, v2b[1] + g(1)))
    r41a, r41b = d.res("R41", tm["R_min"], XB_, v2b[1] + g(3), side="left")
    s.wire(v2b, r41a)
    k11, a11 = d.diode("D11", "DSIG", XB_, r41b[1] + g(3), rot=270, side="left")
    s.wire(r41b, k11)
    s.wire(a11, (XB_, CN_Y), (XA_, CN_Y))
    d.text(["RV2  LISTEN TIME", f"{tm['t_listen'][0]:.1f}-{tm['t_listen'][1]:.1f} s, clockwise longer"],
           g(10), rv2y + g(2), size=1.0)
    # the timing capacitors: three 1 uF film in parallel
    for i in range(tm["n_C"]):
        xx = XA_ + g(4) + g(3) * i
        s.place("Device:C", f"C{50 + i}", "1uF", xx, CN_Y + g(2.5), footprint=fp("CFILM"),
                fields=part_fields("CFILM"), ref_off=(2.4, -1.4), val_off=(2.4, 0.4),
                ref_justify="left", val_justify="left")
        s.wire((xx, CN_Y), (xx, CN_Y + g(1)))
        s.wire((xx, CN_Y + g(4)), (xx, CN_Y + g(5)))
        d.gnd(xx, CN_Y + g(5))
    s.wire((XA_, CN_Y), (XA_ + g(4) + g(3) * (tm["n_C"] - 1), CN_Y))
    d.text(["C50-C52: 3 x 1 uF polypropylene", f"film; t = {tm['kc']:.2f} R C each way"], g(10), CN_Y + g(2), size=1.0)

    # --- POLARIZE IN: a level detector, TTL to 30 V
    EY = g(178)
    je = d.bnc("J7", g(14), EY, "POLARIZE IN", [f"high (> {ex['v_th']:.1f} V) = polarize: TTL, 3.3 V, 5 V,",
                                                f"a function generator; ±{ex['v_max']:.0f} V max;", "open = listen"],
               facing="left", text_at=(g(8), EY - g(9)))
    r43a, r43b = d.res("R43", ex["R_pd"], je[0] + g(1), je[1] + g(3), side="right")
    s.wire((je[0] + g(1), je[1]), r43a)
    d.gnd(*r43b)
    r44a, r44b = d.res("R44", ex["R_series"], je[0] + g(5), je[1], rot=90, text="above")
    s.wire(je, r44a)
    UX8, UY8 = je[0] + g(18), je[1] + g(1)
    pe, me, oe = d.comparator("U8", UX8, UY8)
    XIN = pe[0] - g(5)
    s.wire(r44b, (XIN, je[1]))
    assert abs(je[1] - pe[1]) < 0.01, (je, pe)
    # R59: the comparator's own pin behind 10k, so the clamp's -0.35 V never puts more than
    # microamps into it (TS391: -0.3 V absolute maximum); the hysteresis lands on the clamped node
    r59a, r59b = d.res("R59", ex["R_in"], XIN + g(3.5), pe[1], rot=90, text="above")
    s.wire((XIN, je[1]), r59a)
    assert abs(r59b[0] - pe[0]) < 0.01 and abs(r59b[1] - pe[1]) < 0.01, (r59b, pe)
    # the clamp: BAT54S, pin 3 on the node, pin 1 (anode) to ground, pin 2 (cathode) to +15 V
    s.place(sym("DCLAMP"), "D12", parts.PARTS["DCLAMP"]["value"], XIN - g(2), pe[1] - g(6), rot=90, footprint=fp("DCLAMP"),
            fields=part_fields("DCLAMP"), ref_off=(-3.0, -1.4), val_off=(-3.0, 0.4),
            ref_justify="right", val_justify="right")
    d12_1, d12_2, d12_3 = s.pin("D12", 1, "1"), s.pin("D12", 1, "2"), s.pin("D12", 1, "3")
    s.wire(d12_3, (d12_3[0] + g(1), d12_3[1]), (d12_3[0] + g(1), pe[1]))
    hi, lo = (d12_2, d12_1)
    s.wire(hi, (hi[0], hi[1] - g(1)))
    d.rail("+15V", hi[0], hi[1] - g(1))
    s.wire(lo, (lo[0], lo[1] + g(1)))
    d.gnd(lo[0], lo[1] + g(1))
    # the threshold, 1.3 V from +15 V, and the hysteresis
    # R45 from +15 V to the - input's node, R46 from it to ground, in a column
    # left of the comparator under its + input
    THX8 = me[0] - g(2)
    NODE8 = (THX8, me[1] + g(4))
    s.wire(me, (THX8, me[1]), NODE8)
    r45a, r45b = d.res("R45", ex["R_top"], THX8 - g(3.5), NODE8[1], rot=90, text="below")
    s.wire(r45b, NODE8)
    s.wire(r45a, (r45a[0] - g(1), r45a[1]), (r45a[0] - g(1), r45a[1] - g(1)))
    d.rail("+15V", r45a[0] - g(1), r45a[1] - g(1))
    r46a, r46b = d.res("R46", ex["R_bot"], THX8, NODE8[1] + g(2.5), side="right")
    s.wire(NODE8, r46a)
    d.gnd(*r46b)
    r47a, r47b = d.res("R47", ex["R_hyst"], UX8, pe[1] - g(6.5), rot=90, text="above")
    s.wire((XIN + g(2), pe[1]), (XIN + g(2), pe[1] - g(6.5)), r47a)
    OEX = oe[0] + g(2)
    s.wire(oe, (OEX, oe[1]), (OEX, pe[1] - g(6.5)), r47b)
    r48a, r48b = d.res("R48", ex["R_pu"], OEX + g(2), oe[1] - g(3), side="right")
    s.wire((OEX, oe[1]), (OEX + g(2), oe[1]), r48b)
    s.wire(r48a, (r48a[0], r48a[1] - g(1)))
    d.rail("+15V", r48a[0], r48a[1] - g(1))
    s.wire((OEX + g(2), oe[1]), (OEX + g(4), oe[1]))
    d.testpoint(OEX + g(4), oe[1], "EXT", rot=180, dy=3.6)
    d.text([f"U8: a comparator at {ex['v_th']:.1f} V (R45, R46),", f"{ex['hyst'] * 1e3:.0f} mV of hysteresis (R47).",
            f"D12 clamps the input between -0.35 V and +15.3 V; R59 keeps",
            f"the TS391's pin inside its -0.3 V limit at ±{ex['v_max']:.0f} V in"],
           UX8 - g(8), UY8 + g(11), size=1.0)

    # --- SEQUENCE (INT / EXT) and MODE (RUN / LISTEN ONLY)
    SW3X, SW3Y = g(56), g(150)
    a1, a2, a3 = d.switch("SW3", "SEQUENCE", SW3X, SW3Y, None,
                          ["1: EXT, the POLARIZE IN jack", "3: INT, the timer (RV1, RV2)"],
                          text_at=(SW3X - g(6), SW3Y - g(9)), rot=180)
    s.wire(t_out, (g(50), t_out[1]), (g(50), a3[1]), a3)
    s.wire((OEX + g(4), oe[1]), (g(51), oe[1]), (g(51), a1[1]), a1)
    SW4X, SW4Y = SW3X + g(13), SW3Y
    b1, b2, b3 = d.switch("SW4", "MODE", SW4X, SW4Y, "y",
                          ["1: RUN", "3: LISTEN ONLY (no polarizing)"],
                          text_at=(SW4X - g(2), SW4Y + g(5.5)))
    s.wire(a2, (b1[0] - g(3), a2[1]), (b1[0] - g(3), b1[1]), b1)
    s.wire(b3, (b3[0] - g(1), b3[1]), (b3[0] - g(1), b3[1] + g(2)))
    d.gnd(b3[0] - g(1), b3[1] + g(2))
    PC_X = b2[0] + g(4)
    POLC_Y = b2[1]
    r42a, r42b = d.res("R42", "100k", PC_X, POLC_Y + g(2.5), side="left")
    s.wire((PC_X, POLC_Y), r42a)
    d.gnd(*r42b)
    d.testpoint(PC_X + g(2), POLC_Y, "POL CMD", rot=0)
    d.label("POL_CMD", PC_X + g(3), POLC_Y)
    s.wire(b2, (PC_X, POLC_Y))

    # --- the threshold the two delays compare with: half the rail, on a bus
    # that runs under both delays to their comparators' - inputs
    THX = PC_X + g(9)
    VTH_Y = POLC_Y + g(16)
    r51a, r51b = d.res("R51", dl["R_th_top"], THX, VTH_Y - g(1.5), side="left")
    s.wire(r51a, (THX, r51a[1] - g(1)))
    d.rail("+15V", THX, r51a[1] - g(1))
    r52a, r52b = d.res("R52", dl["R_th_bot"], THX, VTH_Y + g(1.5), side="left")
    d.gnd(*r52b)
    c54a, c54b = d.cap("C54", "100nF", THX + g(3), VTH_Y + g(1.5), side="right")
    d.gnd(*c54b)
    VTH = (THX, VTH_Y)
    d.text([f"{dl['v_th']:.1f} V"], THX + g(1), VTH_Y - g(1), size=1.0)

    def delay(refs, x0, kind):
        """POL CMD at x0 on the bus; R and D in parallel to the timing node;
        the node's 100 nF to ground; a comparator on it against VTH.
        kind 'gate': D's cathode on POL CMD (empties the node at once);
        'hold': D's anode on POL CMD (fills it at once)."""
        rr, dd, cc, uu, tp = refs
        y1, y2 = POLC_Y + g(4), POLC_Y + g(7)
        s.wire((x0, POLC_Y), (x0, y2))
        ra, rb = d.res(rr, dl["R_gate"] if kind == "gate" else dl["R_hold"], x0 + g(4), y1, rot=90, text="above")
        s.wire((x0, y1), ra)
        if kind == "gate":
            dk, da = d.diode(dd, "DSIG", x0 + g(4), y2, rot=0)
            s.wire((x0, y2), dk)
            s.wire(da, (x0 + g(8), y2))
        else:
            dk, da = d.diode(dd, "DSIG", x0 + g(4), y2, rot=180)
            s.wire((x0, y2), da)
            s.wire(dk, (x0 + g(8), y2))
        xn = x0 + g(8)
        s.wire(rb, (xn, y1), (xn, y2))
        ca, cb = d.cap(cc, dl["C"], xn, y2 + g(3.5), side="right")
        s.wire((xn, y2), ca)
        d.gnd(*cb)
        d.testpoint(xn, y1 - g(1.5), tp, rot=90, dx=-1.8, dy=-2.4, justify="right")
        s.wire((xn, y1), (xn, y1 - g(1.5)))
        pc, mc, oc = d.comparator(uu, xn + g(10), y2 + g(2))
        s.wire((xn, y2), (pc[0] - g(2), y2), (pc[0] - g(2), pc[1]), pc)
        s.wire(mc, (mc[0] - g(1), mc[1]), (mc[0] - g(1), VTH_Y))
        return oc, (mc[0] - g(1), VTH_Y)

    HOLD_X = THX + g(40)
    s.wire((PC_X, POLC_Y), (HOLD_X, POLC_Y))
    og, vg = delay(("R49", "D13", "C55", "U9", "DELAY"), THX + g(8), "gate")
    oh, vh = delay(("R50", "D14", "C56", "U10", "HOLD"), HOLD_X, "hold")
    s.wire(VTH, vh)
    d.text([f"U9 GATE: on {dl['t_gate'] * 1e3:.0f} ms after POL CMD rises (R49, C55),", "off at once when it falls (D13)"],
           THX + g(8), VTH_Y + g(1.5), size=1.0)
    d.text(["U10 RELAY: on at once (D14),", f"off {dl['t_hold'] * 1e3:.0f} ms after POL CMD falls (R50, C56)"],
           HOLD_X, VTH_Y + g(1.5), size=1.0)
    # the gate drive: 4.7k up from U9's open collector, then up and left to Q1
    ogx = og[0] + g(2)
    r7a, r7b = d.res("R7", D["gate"]["R_pu"], ogx, og[1] - g(3), side="right")
    s.wire(og, (ogx, og[1]), r7b)
    s.wire(r7a, (ogx, r7a[1] - g(1)))
    d.rail("+15V", ogx, r7a[1] - g(1))
    d.testpoint(ogx + g(2), og[1], "GATE", rot=180, dy=3.6)
    GATE_Y = g(112)
    s.wire((ogx, og[1]), (ogx + g(4), og[1]), (ogx + g(4), GATE_Y), (GATE_X, GATE_Y), (GATE_X, qg[1]))
    d.label("GATE", GATE_X + g(2), GATE_Y)
    # the relay: U10 out, 10k up, 10k into Q2's base; Q2 sinks the coil
    ohx = oh[0] + g(2)
    r9a, r9b = d.res("R9", "10k", ohx, oh[1] - g(3), side="right")
    s.wire(oh, (ohx, oh[1]), r9b)
    s.wire(r9a, (ohx, r9a[1] - g(1)))
    d.rail("+15V", ohx, r9a[1] - g(1))
    d.testpoint(ohx + g(1.5), oh[1], "RELAY", rot=180, dy=3.6)
    r8a, r8b = d.res("R8", "10k", ohx + g(6), oh[1], rot=90, text="above")
    s.wire((ohx, oh[1]), r8a)
    QRX = r8b[0] + g(2)
    s.place(sym("NPN"), "Q2", "MMBT3904", QRX, oh[1], footprint=fp("NPN"), fields=part_fields("NPN"),
            ref_off=(3.8, -1.4), val_off=(3.8, 0.4), ref_justify="left", val_justify="left")
    q2b, q2e, q2c = s.pin("Q2", 1, "1"), s.pin("Q2", 1, "2"), s.pin("Q2", 1, "3")
    s.wire(r8b, q2b)
    s.wire(q2e, (q2e[0], q2e[1] + g(1)))
    d.gnd(q2e[0], q2e[1] + g(1))
    KY = q2c[1] - g(5)
    s.place(sym("RELAY"), "K1", "HFD3/12", q2c[0], KY, unit=1, footprint=fp("RELAY"),
            fields=part_fields("RELAY"), hide_ref=True, hide_value=True)
    kc1, kc12 = s.pin("K1", 1, "1"), s.pin("K1", 1, "12")
    s.wire(kc12, q2c)
    s.wire(kc1, (kc1[0], kc1[1] - g(2)))
    d.rail("+15V", kc1[0], kc1[1] - g(2))
    d.text(["K1 coil", "1028 ohm"], kc1[0] - g(6), KY + g(1.5), size=1.0)
    DFX = kc1[0] + g(4)
    k8, a8 = d.diode("D8", "DSIG", DFX, KY, rot=270, side="right")
    s.wire((kc1[0], kc1[1] - g(1)), (DFX, kc1[1] - g(1)), k8)
    s.wire(a8, (DFX, kc12[1] + g(1)), (kc12[0], kc12[1] + g(1)))
    LDX = DFX + g(6)
    r10a, r10b = d.res("R10", "3.3k", LDX, KY - g(1.5), side="right")
    s.wire((DFX, kc1[1] - g(1)), (LDX, kc1[1] - g(1)), r10a)
    k4, a4 = d.led("LED4", "LED_R", LDX, KY + g(2.5))
    s.wire(r10b, a4)
    s.wire(k4, (LDX, kc12[1] + g(1)), (DFX, kc12[1] + g(1)))
    d.text(["red: POLARIZING"], LDX + g(1), KY + g(5.5), size=1.0)
    # SYNC OUT: an emitter follower off POL CMD
    SYX = PC_X + g(3)
    SYY = POLC_Y + g(27)
    r53a, r53b = d.res("R53", "10k", SYX + g(2), SYY, rot=90, text="above")
    TAPX = PC_X + g(6)
    s.wire((TAPX, POLC_Y), (TAPX, SYY - g(3)), (r53a[0] - g(1), SYY - g(3)), (r53a[0] - g(1), SYY), r53a)
    s.place(sym("NPN"), "Q3", "MMBT3904", r53b[0] + g(2), SYY, footprint=fp("NPN"), fields=part_fields("NPN"),
            ref_off=(3.8, -1.4), val_off=(3.8, 0.4), ref_justify="left", val_justify="left")
    q3b, q3e, q3c = s.pin("Q3", 1, "1"), s.pin("Q3", 1, "2"), s.pin("Q3", 1, "3")
    s.wire(r53b, q3b)
    s.wire(q3c, (q3c[0], q3c[1] - g(1)))
    d.rail("+15V", q3c[0], q3c[1] - g(1))
    r54a, r54b = d.res("R54", "10k", q3e[0], q3e[1] + g(3), side="left")
    s.wire(q3e, r54a)
    d.gnd(*r54b)
    r55a, r55b = d.res("R55", D["out"]["R"], q3e[0] + g(4), q3e[1] + g(1), rot=90, text="above")
    s.wire((q3e[0], q3e[1] + g(1)), r55a)
    js_ = d.bnc("J8", r55b[0] + g(5), r55b[1], "SYNC OUT", ["follows POL CMD: 0 / 13 V open, through 1k;",
                                                            "its falling edge is the switch-off:",
                                                            "trigger the scope on it"],
                facing="right", text_at=(r55b[0] + g(9), r55b[1] - g(4)))
    s.wire(r55b, js_)

    # ================================================== HEADPHONES ============
    # drawn after the sequencer, so the bypass capacitors drawn before keep their numbers
    ph = D["phones"]
    HX0, HY = ox7 + g(2), po7[1] + g(12)
    s.wire((HX0, po7[1]), (HX0, HY))
    r58a, r58b = d.res("R58", ph["R_feed"], HX0 + g(3.5), HY, rot=90, text="above")
    s.wire((HX0, HY), r58a)
    # RV3, VOLUME: pin 3 (the clockwise end) up to R58, pin 1 to ground, the wiper to U12's +
    PX = r58b[0] + g(2)
    s.place(sym("POT_KNOB"), "RV3", ph["RV"], PX, HY + g(3), mirror="x", footprint=fp("POT_KNOB"),
            fields=part_fields("POT_KNOB"), ref_off=(-2.4, -1.4), val_off=(-2.4, 0.4),
            ref_justify="right", val_justify="right")
    v3a, v3w, v3b = s.pin("RV3", 1, "1"), s.pin("RV3", 1, "2"), s.pin("RV3", 1, "3")
    assert v3b[1] < v3a[1] and v3w[0] > PX, ("RV3 must have pin 3 on top, the wiper on the right", v3a, v3w, v3b)
    s.wire(r58b, (PX, r58b[1]), v3b)
    s.wire(v3a, (v3a[0], v3a[1] + g(1)))
    d.gnd(v3a[0], v3a[1] + g(1))
    d.text(["VOLUME", "clockwise louder"], PX - g(7.5), HY + g(5.5), size=1.0)
    UPX = v3w[0] + g(6)
    pp12, pm12, po12 = d.opamp("U12", UPX, v3w[1] + g(1))
    assert abs(pp12[1] - v3w[1]) < 0.01, (pp12, v3w)
    s.wire(v3w, pp12)
    ox12 = d.follower_fb(pm12, po12, UPX)
    s.wire((ox12, po12[1]), (ox12 + g(1), po12[1]))
    d.testpoint(ox12 + g(1), po12[1], "PHONES", rot=0)
    # each earpiece through its own 100 ohm: tip (left) and ring (right) alike
    JX, JY = ox12 + g(16), po12[1] + g(2)
    s.place(sym("JACK"), "J9", "PHONES", JX, JY, rot=180, footprint=fp("JACK"), fields=part_fields("JACK"),
            ref_off=(2.4, -6.4), val_off=(2.4, -4.6), ref_justify="left", val_justify="left", hide_value=True)
    jt, jr, js = s.pin("J9", 1, "T"), s.pin("J9", 1, "R"), s.pin("J9", 1, "S")
    assert jt[1] < jr[1] < js[1] and jt[0] == jr[0] == js[0], ("J9: T, R, S down its left side", jt, jr, js)
    RXA = ox12 + g(4)
    r56a, r56b = d.res("R56", ph["R_out"], RXA + g(2), jt[1], rot=90, text="above")
    r57a, r57b = d.res("R57", ph["R_out"], RXA + g(2), jr[1], rot=90, text="below")
    assert po12[1] < jt[1] < jr[1], "the split's column runs down from U12's output past the tip to the ring"
    s.wire((ox12 + g(1), po12[1]), (RXA - g(1), po12[1]), (RXA - g(1), jr[1]), r57a)
    s.wire((RXA - g(1), jt[1]), r56a)
    s.wire(r56b, jt)
    s.wire(r57b, jr)
    s.wire(js, (js[0] - g(1), js[1]), (js[0] - g(1), js[1] + g(1)))
    d.gnd(js[0] - g(1), js[1] + g(1))
    d.title("HEADPHONES", HX0 + g(2), HY - g(7),
            [f"a mono copy of OUT for a stereo headset: {ph['fid_ear_hi'] * 1e3:.0f} mV of FID at a "
             f"{ph['Z']:.0f} ohm earpiece on HIGH, the knob full up",
             f"(about {ph['spl_hi']:.0f} dB SPL); R56, R57 hold a mono plug's shorted ring to "
             f"{ph['i_short'] * 1e3:.0f} mA.  J9: Same Sky SJ1-3523N, 1 sleeve, 2 tip, 3 ring"], size=1.8)

    # ================================================== POWER =================
    PX, PY = g(268), g(24)
    s.place(sym("TERM3"), "J1", "POWER", PX, PY, mirror="y", footprint=fp("TERM3"),
            fields=part_fields("TERM3"), ref_off=(-3.0, -4.6), val_off=(-3.0, 6.0), hide_value=True,
            ref_justify="right", val_justify="right")
    j1a, j1b, j1c = s.pin("J1", 1, "1"), s.pin("J1", 1, "2"), s.pin("J1", 1, "3")
    d.title("POWER", PX - g(12), PY - g(9), ["+15 V, GND, -15 V,", "100 mA a rail"], size=2.2)
    VP_Y, VM_Y = PY - g(6), PY + g(14)
    kd1, ad1 = d.diode("D1", "DSCH", PX + g(7), VP_Y, rot=180)
    s.wire(j1a, (j1a[0] + g(1), j1a[1]), (j1a[0] + g(1), VP_Y), ad1)
    d.label("+15V_IN", j1a[0] + g(1) + 0.3, VP_Y)
    kd2, ad2 = d.diode("D2", "DSCH", PX + g(7), VM_Y, rot=0)
    s.wire(j1c, (j1c[0] + g(1), j1c[1]), (j1c[0] + g(1), VM_Y), kd2)
    d.label("-15V_IN", j1c[0] + g(1) + 0.3, VM_Y)
    s.wire(j1b, (j1b[0] + g(3), j1b[1]))
    s.wire((j1b[0] + g(3), j1b[1]), (j1b[0] + g(3), j1b[1] + g(1)))
    d.gnd(j1b[0] + g(3), j1b[1] + g(1))
    d.flag(j1b[0] + g(3) + g(3), j1b[1], j1b[0] + g(3))
    RAIL_X1 = PX + g(48)
    s.wire(kd1, (RAIL_X1, VP_Y))
    s.wire(ad2, (RAIL_X1, VM_Y))
    d.rail("+15V", PX + g(12), VP_Y)
    d.rail("-15V", PX + g(12), VM_Y, down=True)
    # the shunts on each rail: clamp, bulk, bypass, lamp
    cols = [PX + g(18), PX + g(24), PX + g(30), PX + g(38)]
    # +15 V: D3 (clamp, cathode up), C1 100 uF, C3 100 nF, R1 + LED1
    k3d, a3d = d.diode("D3", "DSCH", cols[0], VP_Y + g(3.5), rot=270, side="left")
    s.wire((cols[0], VP_Y), k3d)
    s.wire(a3d, (cols[0], VP_Y + g(6)))
    d.gnd(cols[0], VP_Y + g(6))
    s.place(sym("CBULK"), "C1", "100uF", cols[1], VP_Y + g(3.5), footprint=fp("CBULK"),
            fields=part_fields("CBULK"), ref_off=(2.6, -1.4), val_off=(2.6, 0.4),
            ref_justify="left", val_justify="left")
    s.wire((cols[1], VP_Y), (cols[1], VP_Y + g(2)))
    s.wire((cols[1], VP_Y + g(5)), (cols[1], VP_Y + g(6)))
    d.gnd(cols[1], VP_Y + g(6))
    c3a, c3b = d.cap("C3", "100nF", cols[2], VP_Y + g(3.5))
    s.wire((cols[2], VP_Y), c3a)
    s.wire(c3b, (cols[2], VP_Y + g(6)))
    d.gnd(cols[2], VP_Y + g(6))
    r1a, r1b = d.res("R1", "10k", cols[3], VP_Y + g(2.5))
    s.wire((cols[3], VP_Y), r1a)
    k1l, a1l = d.led("LED1", "LED", cols[3], VP_Y + g(6.5))
    s.wire(r1b, a1l)
    d.gnd(*k1l)
    # -15 V: D4 (clamp, cathode on ground), C2 100 uF (+ on ground), C4, R2 + LED2
    k4d, a4d = d.diode("D4", "DSCH", cols[0], VM_Y - g(3.5), rot=270, side="left")
    s.wire(a4d, (cols[0], VM_Y))
    s.wire(k4d, (cols[0], VM_Y - g(6)))
    d.gnd(cols[0], VM_Y - g(6), up=True)
    s.place(sym("CBULK"), "C2", "100uF", cols[1], VM_Y - g(3.5), footprint=fp("CBULK"),
            fields=part_fields("CBULK"), ref_off=(2.6, -1.4), val_off=(2.6, 0.4),
            ref_justify="left", val_justify="left")
    s.wire((cols[1], VM_Y), (cols[1], VM_Y - g(2)))
    s.wire((cols[1], VM_Y - g(5)), (cols[1], VM_Y - g(6)))
    d.gnd(cols[1], VM_Y - g(6), up=True)
    c4a, c4b = d.cap("C4", "100nF", cols[2], VM_Y - g(3.5))
    s.wire((cols[2], VM_Y), c4b)
    s.wire(c4a, (cols[2], VM_Y - g(6)))
    d.gnd(cols[2], VM_Y - g(6), up=True)
    r2a, r2b = d.res("R2", "10k", cols[3], VM_Y - g(2.5))
    s.wire((cols[3], VM_Y), r2b)
    k2l, a2l = d.led("LED2", "LED", cols[3], VM_Y - g(6.5))
    s.wire(r2a, k2l)
    d.gnd(*a2l, up=True)
    d.flag(RAIL_X1 + g(3), VP_Y, RAIL_X1)
    d.flag(RAIL_X1 + g(3), VM_Y, RAIL_X1)
    d.text(["D1, D2: a reversed supply does nothing", "D3, D4: clamp a rail left open",
            "LED1, LED2: both rails present"], PX + g(18), VM_Y + g(3), size=1.0)
    d.testpoint(RAIL_X1 - g(3), VP_Y, "+15V", rot=0)
    d.testpoint(RAIL_X1 - g(3), VM_Y, "-15V", rot=180, dy=3.6)

    # ================================================== probe grounds and holes ==
    for (x, y) in ((g(60), g(110)), (g(160), g(110)), (g(250), g(110)), (g(150), g(178))):
        d.testpoint(x, y, "GND", rot=0, dx=1.8, dy=-3.0)
        s.wire((x, y), (x, y + g(1)))
        d.gnd(x, y + g(1))
    d.text(["ground loops for the scope's clip"], g(63), g(108.3), size=1.0)
    for i in range(4):
        s.place(sym("MH"), f"MH{i + 1}", "MountingHole", g(290 + 6 * i), g(185),
                footprint=fp("MH"), in_bom=False, ref_off=(0, -3.5), val_off=(0, 3.5),
                hide_value=True)
    d.text(["M3 mounting holes, one per corner"], g(288), g(189), size=1.0)
    d.text([f"Bypass: 100 nF X7R at every op-amp's, comparator's and the timer's supply pins (C80-C{d.nbyp - 1})"],
           g(150), g(196), size=1.0)
    return s


if __name__ == "__main__":
    s = build()
    added = s.add_missing_junctions()
    if added:
        print(f"  auto-placed {added} junction(s) where wires meet end-to-middle")
    bad = s.check_grid()
    if bad:
        print(f"  !! {len(bad)} off-grid endpoint(s):")
        for what, pt in bad[:12]:
            print(f"       {what} at {pt}")
        raise SystemExit("off-grid endpoints would confuse KiCad's connectivity")
    s.write(OUT)
    print(f"  wrote {os.path.relpath(OUT)}")
