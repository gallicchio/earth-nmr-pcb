#!/usr/bin/env python3
"""Build the PCB from scripts/layout.py: outline, placement, the drawn copper,
the planes and the silkscreen that is the schematic.

Runs under the Python that has KiCad's pcbnew:
    python3 scripts/gen_pcb.py out/earthnmr.net hardware/earthnmr.kicad_pcb

There is no autorouter.  Every wire in layout.WIRES is a schematic wire: it is
laid as copper on the top layer exactly where it is drawn, and drawn again on
the silkscreen (clipped round pads and part bodies), so the printed picture
and the copper cannot disagree.  A few segments dive under others on the back
layer (layout.HOPS); the silkscreen draws those as hops.

Four layers (JLC04161H-7628): F.Cu the parts and the drawn wires; In1.Cu
ground, solid; In2.Cu the +15 V plane; B.Cu the -15 V plane and the hops.
Every pad on one of those three nets reaches its plane through a via of its
own beside it (the op-amps' through vias in their triangles), so no supply is
drawn: the silkscreen marks each with a ground symbol or a rail flag, as a
sheet marks a power symbol at each pin.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from sexp_parse import parse_file
import layout as L
import parts

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.abspath(os.path.join(HERE, "..", "hardware"))
LOCAL_FP = os.path.join(HW, "lib", "earthnmr.pretty")
SHARE_FP = None

SILK_W = 0.3            # the schematic wires on the silkscreen
SILK_CLEAR = 0.3        # silkscreen to pad
VIA_DIA, VIA_DRILL = 0.6, 0.3
PLANE_NETS = {"GND": pcbnew.In1_Cu, "+15V": pcbnew.In2_Cu, "-15V": pcbnew.B_Cu}
Q_BAR_X, Q_BAR_H = 2.2, 1.4
Q_BEND = 3.6
Q_W_CIRCLE, Q_W_LEAD, Q_W_BAR, Q_W_STUB = 0.25, 0.45, 0.55, 0.16
Q_STUB_GAP = 0.3
MH_KEEPOUT = 3.6       # copper-free radius round a mounting hole


def mm(v):
    return pcbnew.FromMM(float(v))


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def tomm(v):
    return pcbnew.ToMM(v)


def find_share():
    env = os.environ.get("KICAD_SHARE_DIR")
    if env and os.path.isdir(os.path.join(env, "footprints")):
        return os.path.join(env, "footprints")
    here = os.path.dirname(os.path.abspath(pcbnew.__file__))
    for up in range(1, 8):
        base = os.path.abspath(os.path.join(here, *([".."] * up)))
        for sub in ("share/kicad/footprints", "usr/share/kicad/footprints"):
            cand = os.path.join(base, sub)
            if os.path.isdir(cand):
                return cand
    for cand in ("/usr/share/kicad/footprints", "/usr/local/share/kicad/footprints"):
        if os.path.isdir(cand):
            return cand
    raise SystemExit("cannot find KiCad's footprint libraries")


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = LOCAL_FP if lib == "earthnmr" else os.path.join(SHARE_FP, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"footprint {fpid} not found in {path}")
    return fp


def read_netlist(path):
    root = parse_file(path)
    comps = {}
    for c in root.first("components").kids("comp"):
        fields = {}
        fl = c.first("fields")
        if fl is not None:
            for f in fl.kids("field"):
                nm = f.first("name").atom(0)
                val = f.atom(0)
                if nm not in ("Footprint", "Datasheet", "Description") and val:
                    fields[nm] = val
        ts = c.first("tstamps")
        val = c.first("value").atom(0)
        comps[c.first("ref").atom(0)] = {
            "value": "" if val == "~" else val,
            "footprint": c.first("footprint").atom(0),
            "fields": fields, "tstamp": ts.atom(0) if ts is not None else ""}
    nets = {}
    for n in root.first("nets").kids("net"):
        name = n.first("name").atom(0)
        nets[name] = [(x.first("ref").atom(0), x.first("pin").atom(0)) for x in n.kids("node")]
    return comps, nets


# ------------------------------------------------------------- the board ---
BOARD_RULES = dict(m_MinClearance=0.20, m_HoleClearance=0.30, m_HoleToHoleMin=0.50,
                   m_CopperEdgeClearance=0.30, m_SilkClearance=0.15)


def apply_rules(board):
    ds = board.GetDesignSettings()
    for name, value in BOARD_RULES.items():
        setattr(ds, name, mm(value))


# JLCPCB's JLC04161H-7628 (their stack-up table): 1 oz outer, 0.5 oz inner,
# 7628 prepreg 0.2104 mm, core 1.065 mm: 1.6 mm.
STACKUP = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def write_stackup(path):
    text = open(path).read()
    if "(stackup" in text:
        return
    i = text.index("\t(setup\n") + len("\t(setup\n")
    open(path, "w").write(text[:i] + STACKUP + text[i:])


def board_outline(board):
    w, h, r = L.BOARD_W, L.BOARD_H, 3.0
    for (a, b) in (((r, 0), (w - r, 0)), ((w, r), (w, h - r)), ((w - r, h), (r, h)), ((0, h - r), (0, r))):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)
    for (cx, cy, a0) in ((r, r, 180), (w - r, r, 270), (w - r, h - r, 0), (r, h - r, 90)):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(pt(cx, cy))
        s.SetStart(pt(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def box_dist(p, b):
    """Distance from point p to an axis-aligned box (x0, y0, x1, y1); 0 inside."""
    dx = max(b[0] - p[0], 0, p[0] - b[2])
    dy = max(b[1] - p[1], 0, p[1] - b[3])
    return math.hypot(dx, dy)


class Board:
    def __init__(self, netlist_path, out_path):
        global SHARE_FP
        SHARE_FP = find_share()
        self.comps, self.nets = read_netlist(netlist_path)
        self.board = pcbnew.CreateEmptyBoard()
        self.board.SetCopperLayerCount(4)
        apply_rules(self.board)
        self.out_path = out_path
        self.netmap = {}
        for name in sorted(self.nets):
            ni = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(ni)
            self.netmap[name] = ni
        self.pad_net = {}
        for name, nodes in self.nets.items():
            for node in nodes:
                self.pad_net[node] = name
        self.fps = {}
        self.pads = {}            # (ref, pad) -> dict; for footprints with repeated numbers, the first
        self.allpads = []         # every pad, for obstacles
        self.qgeom, self.oageom = {}, {}
        self.problems = []
        self.segments, self.vias, self.hops, self.via_at = [], [], [], {}
        self.stub_dir, self.rail_vias = {}, []

    # ------------------------------------------------------------ parts --
    def place(self):
        for ref, info in sorted(self.comps.items()):
            if ref not in L.PLACE:
                raise SystemExit(f"{ref} has no entry in layout.PLACE")
            x, y, rot = L.PLACE[ref]
            fp = load_fp(info["footprint"])
            fp.SetFPIDAsString(info["footprint"])
            if info["tstamp"]:
                fp.SetPath(pcbnew.KIID_PATH("/" + info["tstamp"]))
            fp.SetSheetname("/")
            fp.SetSheetfile(os.path.basename(self.out_path).replace(".kicad_pcb", ".kicad_sch"))
            fp.SetReference(ref)
            fp.SetValue(info["value"])
            for fname, fval in info["fields"].items():
                fp.SetField(fname, fval)
            for f in fp.GetFields():
                if f.GetName() in ("Reference", "Value"):
                    continue
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
            if fp.HasField("Description"):
                fp.SetField("Description", "")
            self.swap_missing_models(fp, info["footprint"])
            self.board.Add(fp)
            fp.SetPosition(pt(x, y))
            if rot:
                fp.SetOrientationDegrees(rot)
            for pad in fp.Pads():
                key = (ref, pad.GetNumber())
                if key in self.pad_net:
                    pad.SetNet(self.netmap[self.pad_net[key]])
            if ref[:2] == "MH":
                fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM
                                 | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
                fp.Value().SetVisible(False)
                fp.Reference().SetVisible(False)
            self.fps[ref] = fp
        for ref, fp in self.fps.items():
            for pad in fp.Pads():
                b = pad.GetBoundingBox()
                d = dict(ref=ref, num=pad.GetNumber(),
                         x=tomm(pad.GetPosition().x), y=tomm(pad.GetPosition().y),
                         x0=tomm(b.GetLeft()), y0=tomm(b.GetTop()), x1=tomm(b.GetRight()), y1=tomm(b.GetBottom()),
                         through=pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH),
                         net=pad.GetNetname())
                self.allpads.append(d)
                self.pads.setdefault((ref, pad.GetNumber()), d)
        self.board.GetDesignSettings().SetAuxOrigin(pt(0, L.BOARD_H))
        board_outline(self.board)

    STAND_INS = {"Fuse_2920_7451Metric": "Fuse_2920.wrl"}

    def swap_missing_models(self, fp, fpid):
        name = fpid.split(":")[1]
        if name not in self.STAND_INS:
            return
        share3d = os.path.join(os.path.dirname(SHARE_FP), "3dmodels")
        models = list(fp.Models())
        if models and all(os.path.exists(m.m_Filename.replace("${KICAD10_3DMODEL_DIR}", share3d)) for m in models):
            return
        fp.Models().clear()
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = "${KIPRJMOD}/lib/earthnmr.3dshapes/" + self.STAND_INS[name]
        m.m_Scale = pcbnew.VECTOR3D(1 / 2.54, 1 / 2.54, 1 / 2.54)
        fp.Models().push_back(m)

    # ----------------------------------------------------------- copper --
    def resolve(self, p):
        """A wire point: (x, y), or (ref, pad) for that pad's centre (an op-amp's
        or transistor's pad: where its lead leaves the drawn symbol)."""
        if isinstance(p[0], str):
            pad = self.pads.get((p[0], p[1]))
            if pad is None:
                raise SystemExit(f"wire: no pad {p[0]}.{p[1]}")
            if p[0] in L.TRANSISTORS:
                return self.q_geometry(p[0])["exit"][p[1]], pad["net"]
            if p[0] in L.OPAMPS:
                return self.oa_geometry(p[0])["exit"][p[1]], pad["net"]
            return (pad["x"], pad["y"]), pad["net"]
        return (float(p[0]), float(p[1])), None

    def track(self, a, b, width, net, layer=pcbnew.F_Cu):
        if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
            return
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(pt(*a)); t.SetEnd(pt(*b))
        t.SetWidth(mm(width)); t.SetLayer(layer)
        t.SetNet(self.netmap[net])
        self.board.Add(t)
        self.segments.append((net, a, b, layer, width))

    def via(self, x, y, net, dia=VIA_DIA, drill=VIA_DRILL):
        for (vn, vx, vy, vd) in self.vias:          # one already there (within 0.05 mm) is the same via
            if math.hypot(vx - x, vy - y) < 0.05:
                x, y = vx, vy
                break
        key = (round(x, 3), round(y, 3))
        if key in self.via_at:
            if self.via_at[key] != net:
                self.problems.append(f"two vias at {key}: {self.via_at[key]!r} and {net!r}")
            return
        self.via_at[key] = net
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(pt(x, y))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetDrill(mm(drill)); v.SetWidth(mm(dia))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.netmap[net])
        v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        self.board.Add(v)
        self.vias.append((net, x, y, dia))

    @staticmethod
    def split_at_hops(pts):
        """Insert each hop's two ends into the segment of the wire that contains
        them, so a hop can be named by where it is, whatever the wire's corners."""
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            inner = []
            for (h0, h1) in L.HOPS:
                if all(seg_dist(h, a, b) < 1e-6 for h in (h0, h1)):
                    for h in (h0, h1):
                        if math.hypot(h[0] - a[0], h[1] - a[1]) > 1e-6 and math.hypot(h[0] - b[0], h[1] - b[1]) > 1e-6:
                            inner.append(h)
            inner.sort(key=lambda h: math.hypot(h[0] - a[0], h[1] - a[1]))
            out += [(float(h[0]), float(h[1])) for h in inner] + [b]
        return out

    def wires(self):
        hops = set()
        for (a, b) in L.HOPS:
            hops.add((round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3)))
            hops.add((round(b[0], 3), round(b[1], 3), round(a[0], 3), round(a[1], 3)))
        bad = []
        for w in L.WIRES:
            points, width = w[0], w[1]
            res = [self.resolve(p) for p in points]
            nets = {n for (_, n) in res if n}
            if len(w) > 2:                      # a wire that names its net (it touches no pad's centre)
                nets.add(w[2])
            if len(nets) != 1:
                bad.append(f"wire {points}: its pad ends are on {sorted(nets) or 'no pad'}")
                continue
            net = nets.pop()
            if net in PLANE_NETS:
                self.problems.append(f"wire {points} is on the plane net {net}: planes are not drawn")
            pts = self.split_at_hops([p for (p, _) in res])
            for a, b in zip(pts, pts[1:]):
                key = (round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3))
                if key in hops:
                    vd, vr = (1.0, 0.5) if width > 1.0 else (VIA_DIA, VIA_DRILL)
                    for e in (a, b):
                        self.via(*e, net, dia=vd, drill=vr)
                    self.track(a, b, width, net, pcbnew.B_Cu)
                    self.hops.append((net, a, b, width))
                else:
                    self.track(a, b, width, net)
        if bad:
            raise SystemExit("\n".join(bad))
        for ref in L.TRANSISTORS:
            g = self.q_geometry(ref)
            for num, path in g["copper"].items():
                net = self.pads[(ref, num)]["net"]
                for a, b in zip(path, path[1:]):
                    self.track(a, b, L.W_SIG, net)
        for ref in L.OPAMPS:
            g = self.oa_geometry(ref)
            for num, path in g["copper"].items():
                net = self.pads[(ref, num)]["net"]
                for a, b in zip(path, path[1:]):
                    self.track(a, b, L.W_SIG, net)
            for num, (vx, vy) in g["vias"].items():
                net = self.pads[(ref, num)]["net"]
                self.track(g["pad"][num], (vx, vy), L.W_SIG, net)
                self.via(vx, vy, net)

    # ------------------------------------------------- plane connections --
    def obstacles(self, net):
        """Everything a new via of `net` must keep clear of: other nets' pads
        (with their boxes), tracks of any net, vias, the board's edge."""
        return ([p for p in self.allpads if p["net"] != net or p["through"]],
                [s for s in self.segments], list(self.vias))

    def via_spot(self, pad, net, prefer=None):
        """A spot for a via beside `pad`: the first of a ring of candidates (the
        preferred direction first) that clears every other pad by 0.25 mm, every
        track by 0.25 mm and every via by 0.3 mm."""
        cx, cy = pad["x"], pad["y"]
        hw, hh = (pad["x1"] - pad["x0"]) / 2, (pad["y1"] - pad["y0"]) / 2
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
        if prefer:
            dirs.remove(prefer) if prefer in dirs else None
            dirs.insert(0, prefer)
        pads, segs, vias = self.obstacles(net)
        r = VIA_DIA / 2
        for gap in (0.45, 0.8, 1.2, 1.7):
            for (ux, uy) in dirs:
                n = math.hypot(ux, uy)
                ux, uy = ux / n, uy / n
                # from the pad's edge along the direction, out by the gap
                ex = hw if abs(ux) > 1e-6 else 0
                ey = hh if abs(uy) > 1e-6 else 0
                vx = cx + ux * (ex + gap + r) if ex else cx + ux * (gap + r)
                vy = cy + uy * (ey + gap + r) if ey else cy + uy * (gap + r)
                if abs(ux) > 1e-6 and abs(uy) > 1e-6:
                    vx, vy = cx + ux * (hw + gap + r), cy + uy * (hh + gap + r)
                ok = True
                if not (1.0 < vx < L.BOARD_W - 1.0 and 1.0 < vy < L.BOARD_H - 1.0):
                    continue
                for p in pads:
                    if p is pad:
                        continue
                    same = p["net"] == net and not p["through"]
                    if box_dist((vx, vy), (p["x0"], p["y0"], p["x1"], p["y1"])) < r + (0.15 if same else 0.25):
                        ok = False
                        break
                if not ok:
                    continue
                for (sn, a, b, layer, w) in segs:
                    if seg_dist((vx, vy), a, b) < r + w / 2 + (0.0 if sn == net else 0.25):
                        if sn != net:
                            ok = False
                            break
                if not ok:
                    continue
                for (vn, x, y, d) in vias:
                    if math.hypot(vx - x, vy - y) < r + d / 2 + 0.3:
                        ok = False
                        break
                if ok:
                    return (vx, vy)
        return None

    def plane_vias(self):
        """A via beside every SMD pad on a plane's net, with a stub to it, and a
        ground symbol or rail flag drawn there.  THT pads reach the planes
        themselves."""
        done = {(ref, num) for ref in L.OPAMPS for num in self.oa_geometry(ref)["vias"]}
        for p in sorted(self.allpads, key=lambda d: (d["ref"], d["num"])):
            net = p["net"]
            if net not in PLANE_NETS or p["through"]:
                continue
            key = (p["ref"], p["num"])
            if key in done or p["ref"] in L.TRANSISTORS and False:
                continue
            done.add(key)
            if key in getattr(L, "MULTI_VIAS", {}):
                spots = L.MULTI_VIAS[key]
                for spot in spots:
                    self.track((p["x"], p["y"]), spot, L.W_POL, net)
                    self.via(*spot, net, dia=1.0, drill=0.5)
                spot, start = spots[0], (p["x"], p["y"])
                dx, dy = spot[0] - start[0], spot[1] - start[1]
                n = math.hypot(dx, dy) or 1.0
                if net == "GND":
                    self.stub_dir[(round(spot[0], 3), round(spot[1], 3))] = (dx / n, dy / n)
                continue
            want = L.VIA_AT.get(key)
            start = (p["x"], p["y"])
            if p["ref"] in L.TRANSISTORS:
                # beyond the lead's exit from the drawn symbol, along the lead
                g = self.q_geometry(p["ref"])
                ex = g["exit"][p["num"]]
                ux, uy = ex[0] - g["cx"], ex[1] - g["cy"]
                n = math.hypot(ux, uy)
                start = ex
                if want is None:
                    want = (ex[0] + ux / n * 1.3, ex[1] + uy / n * 1.3)
            if isinstance(want, tuple) and isinstance(want[0], (int, float)) and len(want) == 2 and abs(want[0]) > 1.5:
                spot = want                                   # an explicit (x, y)
                for (vn, vx, vy, vd) in self.vias:
                    if math.hypot(vx - spot[0], vy - spot[1]) < 0.05:
                        spot = (vx, vy)
            else:
                spot = self.via_spot(p, net, prefer=want)
            if spot is None:
                self.problems.append(f"no room for a {net} via beside {p['ref']}.{p['num']}")
                continue
            self.track(start, spot, L.W_SIG, net)
            self.via(*spot, net)
            if key in getattr(L, "NO_MARK", ()):
                continue
            dx, dy = spot[0] - start[0], spot[1] - start[1]
            n = math.hypot(dx, dy) or 1.0
            if net == "GND":
                self.stub_dir[(round(spot[0], 3), round(spot[1], 3))] = (dx / n, dy / n)
            else:
                self.rail_vias.append((net, spot[0], spot[1], (dx / n, dy / n)))

    def planes(self):
        for net, layer in PLANE_NETS.items():
            z = pcbnew.ZONE(self.board)
            z.SetLayer(layer)
            z.SetNet(self.netmap[net])
            z.SetAssignedPriority(0)
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.5))
            z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(0.25))
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            o = z.Outline(); o.NewOutline()
            m = 0.3
            for (x, y) in ((m, m), (L.BOARD_W - m, m), (L.BOARD_W - m, L.BOARD_H - m), (m, L.BOARD_H - m)):
                o.Append(mm(x), mm(y))
            self.board.Add(z)
        # no copper on any layer under a mounting screw's head (an M3 pan head is 5.5 mm across)
        for ref, fp in self.fps.items():
            if ref[:2] != "MH":
                continue
            cx, cy = tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)
            ra = pcbnew.ZONE(self.board)
            ra.SetIsRuleArea(True)
            ls = pcbnew.LSET()
            for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                ls.AddLayer(layer)
            ra.SetLayerSet(ls)
            ra.SetDoNotAllowZoneFills(True); ra.SetDoNotAllowTracks(True); ra.SetDoNotAllowVias(True)
            ra.SetDoNotAllowPads(False); ra.SetDoNotAllowFootprints(False)
            o = ra.Outline(); o.NewOutline()
            for i in range(24):
                a = 2 * math.pi * i / 24
                o.Append(mm(cx + MH_KEEPOUT * math.cos(a)), mm(cy + MH_KEEPOUT * math.sin(a)))
            self.board.Add(ra)
        # the polarizing current's pads join their copper solidly
        for (ref, num) in L.SOLID_PADS:
            for pad in self.fps[ref].Pads():
                if pad.GetNumber() == num:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        self.board.BuildConnectivity()
        pcbnew.ZONE_FILLER(self.board).Fill(self.board.Zones())
        zones = {z.GetNetname(): z for z in self.board.Zones()}
        for (net, x, y, d) in self.vias:
            if net in PLANE_NETS and not zones[net].HitTestFilledArea(PLANE_NETS[net], pt(x, y), 0):
                self.problems.append(f"the {net} plane does not reach the via at ({x:.2f}, {y:.2f})")

    # ------------------------------------------------------- silkscreen --
    def _line(self, a, b, layer=pcbnew.F_SilkS, width=SILK_W):
        if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
            return
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b))
        s.SetLayer(layer); s.SetWidth(mm(width))
        self.board.Add(s)

    def _dashed(self, a, b, dash=1.2, gap=0.7, width=0.2):
        L_ = math.hypot(b[0] - a[0], b[1] - a[1])
        if L_ < 1e-6:
            return
        ux, uy = (b[0] - a[0]) / L_, (b[1] - a[1]) / L_
        t = 0.0
        while t < L_:
            e = min(t + dash, L_)
            self._line((a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e), width=width)
            t = e + gap

    def _circle(self, cx, cy, r, filled=False, width=SILK_W, layer=pcbnew.F_SilkS):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetCenter(pt(cx, cy)); s.SetEnd(pt(cx + r, cy))
        s.SetFilled(filled); s.SetWidth(mm(width)); s.SetLayer(layer)
        self.board.Add(s)

    def _arc(self, cx, cy, r, a0, sweep, width=SILK_W):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(pt(cx, cy))
        s.SetStart(pt(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(sweep, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.F_SilkS); s.SetWidth(mm(width))
        self.board.Add(s)

    def _arc3(self, cx, cy, r, a0, a1, width=SILK_W):
        def at(a):
            return pt(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(at(a0), at((a0 + a1) / 2.0), at(a1))
        s.SetLayer(pcbnew.F_SilkS); s.SetWidth(mm(width))
        self.board.Add(s)

    def _poly(self, points, filled=True, layer=pcbnew.F_SilkS):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([pt(*p) for p in points])
        s.SetFilled(filled); s.SetWidth(mm(0.1)); s.SetLayer(layer)
        self.board.Add(s)

    def _text(self, x, y, txt, size, thickness=0.15, justify="center", angle=0, layer=pcbnew.F_SilkS):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(txt)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(thickness))
        t.SetLayer(layer)
        if layer in (pcbnew.B_SilkS, pcbnew.B_Cu):
            t.SetMirrored(True)
        t.SetTextAngleDegrees(angle)
        t.SetHorizJustify({"center": pcbnew.GR_TEXT_H_ALIGN_CENTER, "left": pcbnew.GR_TEXT_H_ALIGN_LEFT,
                           "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}[justify])
        t.SetPosition(pt(x, y))
        self.board.Add(t)
        return t

    def keepouts(self):
        boxes = []
        for p in self.allpads:
            boxes.append((p["x0"] - SILK_CLEAR, p["y0"] - SILK_CLEAR, p["x1"] + SILK_CLEAR, p["y1"] + SILK_CLEAR))
        for ref, fp in self.fps.items():
            if ref[:2] in ("TP", "MH") or ref in L.OPAMPS:
                continue
            poly = fp.GetCourtyard(pcbnew.F_CrtYd)
            if poly.OutlineCount():
                bb = poly.BBox()
                boxes.append((tomm(bb.GetLeft()) - 0.4, tomm(bb.GetTop()) - 0.4,
                              tomm(bb.GetRight()) + 0.4, tomm(bb.GetBottom()) + 0.4))
        for (net, x, y, d) in self.vias:
            boxes.append((x - d / 2 - 0.2, y - d / 2 - 0.2, x + d / 2 + 0.2, y + d / 2 + 0.2))
        self.boxes = boxes
        self.circles = [(g["cx"], g["cy"], g["R"] + 0.1) for g in (self.q_geometry(r) for r in L.TRANSISTORS)]
        # an op-amp's triangle: its wires stop at the triangle's edge (the box of the package)
        for ref in L.OPAMPS:
            g = self.oa_geometry(ref)
            boxes.append((g["xl"] + 0.05, g["cy"] - 2.6, g["xr"] - 0.05, g["cy"] + 2.6))

    def clip(self, a, b):
        (x1, y1), (x2, y2) = a, b
        dx, dy = x2 - x1, y2 - y1
        cuts = []
        for (bx0, by0, bx1, by1) in self.boxes:
            t0, t1 = 0.0, 1.0
            ok = True
            for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1), (-dy, y1 - by0), (dy, by1 - y1)):
                if abs(p) < 1e-9:
                    if q < 0:
                        ok = False
                        break
                    continue
                r = q / p
                if p < 0:
                    t0 = max(t0, r)
                else:
                    t1 = min(t1, r)
            if ok and t0 < t1:
                cuts.append((max(0.0, t0), min(1.0, t1)))
        for (qx, qy, qr) in self.circles:
            fx, fy = x1 - qx, y1 - qy
            A = dx * dx + dy * dy
            if A < 1e-12:
                continue
            B = 2 * (fx * dx + fy * dy)
            C = fx * fx + fy * fy - qr * qr
            disc = B * B - 4 * A * C
            if disc <= 0:
                continue
            r = math.sqrt(disc)
            t0, t1 = (-B - r) / (2 * A), (-B + r) / (2 * A)
            if t1 > 0 and t0 < 1:
                cuts.append((max(0.0, t0), min(1.0, t1)))
        cuts.sort()
        pieces, t = [], 0.0
        for (c0, c1) in cuts:
            if c0 > t:
                pieces.append((t, c0))
            t = max(t, c1)
        if t < 1.0:
            pieces.append((t, 1.0))
        out = []
        for (p0, p1) in pieces:
            if (p1 - p0) * math.hypot(dx, dy) < 0.25:
                continue
            out.append(((x1 + dx * p0, y1 + dy * p0), (x1 + dx * p1, y1 + dy * p1)))
        return out

    def silk_wires(self):
        self.keepouts()
        hopset = {(round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3)) for (_, a, b, _) in self.hops}
        hopset |= {(round(b[0], 3), round(b[1], 3), round(a[0], 3), round(a[1], 3)) for (_, a, b, _) in self.hops}
        drawn = [sg for sg in self.segments if sg[0] not in PLANE_NETS]
        for (net, a, b, layer, w) in drawn:
            key = (round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3))
            if key in hopset:
                cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                r = max(0.6, w / 2 + 0.5)
                ux, uy = (b[0] - a[0]), (b[1] - a[1])
                n = math.hypot(ux, uy)
                ux, uy = ux / n, uy / n
                p1, p2 = (cx - ux * r, cy - uy * r), (cx + ux * r, cy + uy * r)
                for (p, q) in self.clip(a, p1) + self.clip(p2, b):
                    self._line(p, q)
                ang = math.degrees(math.atan2(uy, ux))
                self._arc(cx, cy, r, ang + 180, 180)
                continue
            if layer != pcbnew.F_Cu:
                continue
            for (p, q) in self.clip(a, b):
                self._line(p, q, width=SILK_W if w < 1.0 else 0.45)
        # junction dots where three or more ends of one net meet, or one ends mid-segment
        count = {}
        front = [sg for sg in drawn if sg[3] == pcbnew.F_Cu]
        for (net, a, b, layer, w) in front:
            for e in (a, b):
                k = (net, round(e[0], 2), round(e[1], 2))
                count[k] = count.get(k, 0) + 1
        for (net, a, b, layer, w) in front:
            for e in (a, b):
                for (n2, c, d, l2, w2) in front:
                    if n2 != net or (c, d) == (a, b):
                        continue
                    if self._interior(e, c, d):
                        k = (net, round(e[0], 2), round(e[1], 2))
                        count[k] = max(count[k], 3)
        for (net, x, y), n in count.items():
            if n >= 3 and not self._on_pad(x, y):
                self._circle(x, y, 0.5, filled=True, width=0)

    @staticmethod
    def _interior(p, a, b, tol=0.01):
        (px, py), (ax, ay), (bx, by) = p, a, b
        if abs(ay - by) < tol and abs(py - ay) < tol:
            return min(ax, bx) + tol < px < max(ax, bx) - tol
        if abs(ax - bx) < tol and abs(px - ax) < tol:
            return min(ay, by) + tol < py < max(ay, by) - tol
        return False

    def _on_pad(self, x, y, margin=0.55):
        for p in self.allpads:
            if p["x0"] - margin <= x <= p["x1"] + margin and p["y0"] - margin <= y <= p["y1"] + margin:
                return True
        return False

    def silk_grounds(self):
        """A ground symbol at every ground via, continuing the stub's direction;
        a small rail flag at every +15 V and -15 V via."""
        for (net, x, y, d) in self.vias:
            if net != "GND":
                continue
            key = (round(x, 3), round(y, 3))
            if key not in self.stub_dir:
                continue
            ux, uy = self.stub_dir[key]
            self.ground_symbol(x, y, ux, uy)
        for (net, x, y, (ux, uy)) in self.rail_vias:
            if net not in ("+15V", "-15V"):
                continue
            self.rail_flag(x, y, ux, uy, "+15" if net == "+15V" else "-15")
        # a through-hole pin on a plane: the mark beside it, a stub from the pad's edge
        for mark in getattr(L, "MARKS", ()):
            kind, ref, num, ux, uy = mark[:5]
            extra = mark[5] if len(mark) > 5 else 0.0      # further out, past a body's outline
            p = self.pads[(ref, num)]
            want = {"gnd": "GND", "+15": "+15V", "-15": "-15V"}[kind]
            if p["net"] != want:
                self.problems.append(f"MARKS: {ref}.{num} is on {p['net']}, not {want}")
            r = max(p["x1"] - p["x0"], p["y1"] - p["y0"]) / 2 + SILK_CLEAR + extra
            x, y = p["x"] + ux * r, p["y"] + uy * r
            self._line((x, y), (x + ux * 0.8, y + uy * 0.8), width=0.2)
            x, y = x + ux * 0.8, y + uy * 0.8
            if kind == "gnd":
                self.ground_symbol(x - ux * 0.55, y - uy * 0.55, ux, uy)
            else:
                self.rail_flag(x - ux * 0.75, y - uy * 0.75, ux, uy, kind)

    def ground_symbol(self, x, y, ux, uy, start=0.55):
        px, py = -uy, ux
        s0 = start + 0.4
        self._line((x + ux * start, y + uy * start), (x + ux * s0, y + uy * s0), width=0.2)
        for i, w in enumerate((1.3, 0.85, 0.4)):
            s = s0 + i * 0.4
            cx, cy = x + ux * s, y + uy * s
            self._line((cx - px * w / 2, cy - py * w / 2), (cx + px * w / 2, cy + py * w / 2), width=0.2)

    def rail_flag(self, x, y, ux, uy, text):
        """A bar across the via's outward direction and the rail's name beyond it."""
        px, py = -uy, ux
        s = 0.75
        cx, cy = x + ux * s, y + uy * s
        self._line((cx - px * 0.7, cy - py * 0.7), (cx + px * 0.7, cy + py * 0.7), width=0.2)
        tx, ty = x + ux * 1.9, y + uy * 1.9
        just = "left" if ux > 0.5 else "right" if ux < -0.5 else "center"
        if just == "center":
            tx, ty = x + ux * 2.0, y + uy * 2.0
        self._text(tx, ty, text, 0.8, 0.15, justify=just)

    # ------------------------------------------------------ op-amps --
    def oa_geometry(self, ref):
        """The triangle round op-amp or comparator `ref` (SOT-23-5 at rotation
        270, where pads 3, 2, 1 run along the top and 4, 5 along the bottom):
        the + of an OPA197 (- of a TS391) enters the left edge at cy - OA_IN,
        the other input at cy + OA_IN, the output leaves the right vertex at cy.
        Pad 2 (V-) goes up to a via inside the triangle; pad 5 (V+) down to a
        via just below the package; the planes take them from there."""
        if ref in self.oageom:
            return self.oageom[ref]
        fp = self.fps[ref]
        cx, cy = tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)
        if abs(fp.GetOrientationDegrees() - (-90.0)) > 0.01 and abs(fp.GetOrientationDegrees() - 270.0) > 0.01:
            raise SystemExit(f"{ref}: op-amps and comparators are laid at rotation 270 only "
                             f"({fp.GetOrientationDegrees()})")
        H, W, d = L.OA_H, L.OA_W, L.OA_IN
        xl, xr = cx - W / 2, cx + W / 2
        P = {n: (self.pads[(ref, n)]["x"], self.pads[(ref, n)]["y"]) for n in "12345"}
        assert P["3"][0] < P["1"][0] and P["3"][1] < P["4"][1], (ref, P)
        g = Q_STUB_GAP
        exit = {"3": (xl, cy - d), "4": (xl, cy + d), "1": (xr, cy)}
        ox = P["1"][0] + 1.25
        copper = {"3": [P["3"], (P["3"][0], cy - d), exit["3"]],
                  "4": [P["4"], (P["4"][0], cy + d), exit["4"]],
                  "1": [P["1"], (ox, P["1"][1]), (ox, cy), exit["1"]]}
        stubs = {"3": [(P["3"][0], P["3"][1] - 0.66 - g), (P["3"][0], cy - d), exit["3"]],
                 "4": [(P["4"][0], P["4"][1] + 0.66 + g), (P["4"][0], cy + d), exit["4"]],
                 "1": [(P["1"][0] + 0.3 + g, P["1"][1]), (ox, P["1"][1]), (ox, cy), exit["1"]]}
        vias = {"2": (P["2"][0], P["2"][1] - 1.5), "5": (P["5"][0], P["5"][1] + 1.5)}
        comp = self.comps[ref]["value"] == "TS391"
        geom = dict(cx=cx, cy=cy, xl=xl, xr=xr, exit=exit, copper=copper, stubs=stubs, vias=vias, pad=P,
                    via_mark={"2": (0, -1), "5": (0, 1)},
                    tri=[(xl, cy - H / 2), (xr, cy), (xl, cy + H / 2)],
                    top=(xl + 1.3, cy - d + 1.05), bot=(xl + 1.3, cy + d - 1.05),
                    top_sign="-" if comp else "+", bot_sign="+" if comp else "-")
        self.oageom[ref] = geom
        return geom

    def silk_opamps(self):
        for ref in L.OPAMPS:
            fp = self.fps[ref]
            for item in list(fp.GraphicalItems()):
                if item.GetLayer() == pcbnew.F_SilkS:
                    fp.Remove(item)
            g = self.oa_geometry(ref)
            t = g["tri"]
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                self._line(a, b, width=Q_W_LEAD)
            for num, path in g["stubs"].items():
                for a, b in zip(path, path[1:]):
                    self._line(a, b, width=Q_W_STUB)
            self._text(*g["top"], g["top_sign"], 1.1, 0.2)
            self._text(*g["bot"], g["bot_sign"], 1.1, 0.2)

    # ------------------------------------------------------ transistors --
    def q_geometry(self, ref):
        """The textbook symbol round SOT-23 transistor `ref` (the op-amp board's
        q_geometry: a circle, the base bar, the legs, the emitter arrow)."""
        if ref in self.qgeom:
            return self.qgeom[ref]
        kind, side = L.TRANSISTORS[ref]
        fp = self.fps[ref]
        cx, cy = tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)
        m = 1 if side == "left" else -1
        n = 1 if kind == "NPN" else -1
        R, BX, BH, BEND = 4.0, Q_BAR_X, Q_BAR_H, Q_BEND
        roles = (("1", "B"), ("2", "E"), ("3", "C"))

        def P(x, y):
            return (cx + m * x, cy + n * y)

        pins = {}
        for num, name in roles:
            p = self.pads[(ref, num)]
            pins[name] = (m * (p["x"] - cx), n * (p["y"] - cy), (p["x1"] - p["x0"]) / 2, (p["y1"] - p["y0"]) / 2)
        xb, yb, hwb, hhb = pins["B"]
        xe, ye, hwe, hhe = pins["E"]
        xc, yc, hwc, hhc = pins["C"]
        if not (xb < -0.5 and xe > 0.5 and abs(xc) < 0.1):
            raise SystemExit(f"{ref}: the package is not turned with its base pad on the bar's side "
                             f"(B {xb:.2f}, E {xe:.2f}, C {xc:.2f})")
        g = Q_STUB_GAP
        L_ = math.hypot(BX, BEND - BH)
        u = (BX / L_, (BEND - BH) / L_)

        def foot(sx, sy):
            t = (sx + BX) * u[0] + (sy - BH) * u[1]
            return (-BX + t * u[0], BH + t * u[1])

        stubs, copper = {}, {}
        # the base pad sits between the bar and the legs: its hairline leaves the edge facing the bar
        stubs["1"] = [(xb - hwb - g if xb > -BX else xb + hwb + g, yb), (-BX + Q_W_BAR / 2, yb)]
        copper["1"] = [(-R, 0), (-BX, 0), (-BX, yb), (xb, yb)]
        stubs["3"] = [(0, yc - hhc - g), (0, -BEND)]
        copper["3"] = [(0, -R), (0, yc)]
        if ye > 0:
            e_s = (xe, ye + hhe + g)
            e_f = foot(*e_s)
            stubs["2"] = [e_s, e_f]
            copper["2"] = [(0, R), (0, BEND), e_f, e_s, (xe, ye)]
        else:
            e_s, e_m = (xe, ye + hhe + g), (xe, 2.1)
            e_f = foot(*e_m)
            stubs["2"] = [e_s, e_m, e_f]
            copper["2"] = [(0, R), (0, BEND), e_f, e_m, e_s, (xe, ye)]
        if kind == "NPN":
            tip = (0, BEND)
            tail = (tip[0] - u[0] * 1.1, tip[1] - u[1] * 1.1)
        else:
            tip = (-BX + u[0] * 0.12, BH + u[1] * 0.12)
            tail = (tip[0] + u[0] * 1.1, tip[1] + u[1] * 1.1)
        px, py = -u[1], u[0]
        arrow = [tip, (tail[0] + px * 0.5, tail[1] + py * 0.5), (tail[0] - px * 0.5, tail[1] - py * 0.5)]
        geom = dict(cx=P(0, 0)[0], cy=P(0, 0)[1], R=R,
                    exit={"1": P(-R, 0), "3": P(0, -R), "2": P(0, R)},
                    bar=[P(-BX, -BH), P(-BX, BH)],
                    leads=[[P(-R, 0), P(-BX, 0)], [P(-BX, -BH), P(0, -BEND), P(0, -R)],
                           [P(-BX, BH), P(0, BEND), P(0, R)]],
                    arrow=[P(*q) for q in arrow],
                    stubs={k: [P(*q) for q in v] for k, v in stubs.items()},
                    copper={k: [P(*q) for q in v] for k, v in copper.items()},
                    letters={"B": P(-3.0, -0.9), "C": P(1.15, -3.0), "E": P(1.15, 3.0)})
        self.qgeom[ref] = geom
        return geom

    def silk_transistors(self):
        for ref in L.TRANSISTORS:
            fp = self.fps[ref]
            for item in list(fp.GraphicalItems()):
                if item.GetLayer() == pcbnew.F_SilkS:
                    fp.Remove(item)
            g = self.q_geometry(ref)
            self._circle(g["cx"], g["cy"], g["R"], width=Q_W_CIRCLE)
            self._line(g["bar"][0], g["bar"][1], width=Q_W_BAR)
            for lead in g["leads"]:
                for a, b in zip(lead, lead[1:]):
                    self._line(a, b, width=Q_W_LEAD)
            self._poly(g["arrow"])
            for path in g["stubs"].values():
                for a, b in zip(path, path[1:]):
                    self._line(a, b, width=Q_W_STUB)
            for name, (lx, ly) in g["letters"].items():
                self._text(lx, ly, name, 0.8, 0.15, justify="center")

    # ------------------------------------------------------- text and boxes --
    def silk_fields(self):
        """Reference and value beside each part, where layout.FIELD_AT says."""
        for ref, fp in self.fps.items():
            if ref[:2] == "MH":
                continue
            cx, cy = tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)
            r, v = fp.Reference(), fp.Value()
            for t in (r, v):
                t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); t.SetTextThickness(mm(0.15))
                t.SetTextAngleDegrees(0); t.SetLayer(pcbnew.F_SilkS)
                t.SetKeepUpright(True)
            if ref.startswith("TP"):
                r.SetVisible(False)
                v.SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
                where = L.TP_LABEL.get(ref, (2.6, 0.0, "left"))
                if where is None:
                    v.SetVisible(False)
                    continue
                dx, dy, j = where
                v.SetPosition(pt(cx + dx, cy + dy))
                v.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                                   "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[j])
                continue
            at = L.FIELD_AT.get(ref)
            if at is None:
                rot = L.PLACE[ref][2] % 180
                at = ((0.0, -1.75), (0.0, 1.75)) if rot == 0 else ((1.7, -0.7), (1.7, 0.7))
            for t, off, hide in ((r, at[0], ref in L.HIDE_REF), (v, at[1], ref in L.HIDE_VALUE)):
                if hide or off is None:
                    t.SetVisible(False)
                    continue
                t.SetVisible(True)
                t.SetPosition(pt(cx + off[0], cy + off[1]))
                if len(off) > 2:
                    t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                                       "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[off[2]])
                    if len(off) > 3:
                        t.SetTextAngleDegrees(off[3])
                    continue
                t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if off[0] > 0.5 else
                                  pcbnew.GR_TEXT_H_ALIGN_RIGHT if off[0] < -0.5 else pcbnew.GR_TEXT_H_ALIGN_CENTER)

    def silk_boxes(self):
        for (x0, y0, x1, y1, titles) in L.BOXES:
            for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                for (p, q) in self.clip(a, b):
                    self._dashed(p, q)
            for t in titles:
                title, tx, ty = t[:3]
                self._text(tx, ty, title, t[3] if len(t) > 3 else 0.95, 0.18, justify="left")

    def silk_texts(self):
        for (x, y, txt, size, thick, just, ang) in L.TEXTS:
            self._text(x, y, txt, size, thick, justify=just, angle=ang)
        for (a, b) in getattr(L, "SILK_LINES", ()):
            self._line(a, b, width=0.2)
        for (cx, cy, r) in getattr(L, "SILK_DOTS", ()):
            self._circle(cx, cy, r, filled=True, width=0)

    def silk_back(self):
        tx, ty = L.BACK_TITLE_AT
        self._text(tx, ty, parts.BOARD_NAME.upper(), 3.0, 0.5, layer=pcbnew.B_SilkS)
        self._text(tx, ty + 4.5, "Jason Gallicchio and Claude, rev " + parts.REV + ", " + parts.BOARD_DATE,
                   1.1, 0.15, layer=pcbnew.B_SilkS)
        for i, line in enumerate(L.BACK_TEXT):
            if isinstance(line, str):
                line = (0, line)
            y = L.BACK_Y + i * L.BACK_PITCH
            for k in range(0, len(line), 2):
                if line[k + 1]:
                    self._text(L.BACK_X - line[k], y, line[k + 1], L.BACK_SIZE, 0.15,
                               justify="left", layer=pcbnew.B_SilkS)
        qx, qy = L.QR_AT
        n, rects = self.add_qr("https://" + parts.PROJECT_URL, qx, qy, L.QR_MODULE)
        half = n * L.QR_MODULE / 2
        self._text(qx, qy + half + 2.4, "https://" + parts.PROJECT_URL, 1.1, 0.15, layer=pcbnew.B_SilkS)
        self._text(qx, qy + half + 4.6, "circuit, scripts, handbook", 1.0, 0.15, layer=pcbnew.B_SilkS)

    def add_qr(self, url, cx, cy, module):
        import qrcode_gen
        m = qrcode_gen.encode(url, "M")
        n = len(m)
        x0, y0 = cx - n * module / 2.0, cy - n * module / 2.0
        rects = []
        for r in range(n):
            c = 0
            while c < n:
                if not m[r][c]:
                    c += 1
                    continue
                a = c
                while c < n and m[r][c]:
                    c += 1
                sh = pcbnew.PCB_SHAPE(self.board)
                sh.SetShape(pcbnew.SHAPE_T_RECT)
                sh.SetStart(pt(x0 + (n - c) * module, y0 + r * module))
                sh.SetEnd(pt(x0 + (n - a) * module, y0 + (r + 1) * module))
                sh.SetFilled(True); sh.SetWidth(0); sh.SetLayer(pcbnew.B_SilkS)
                self.board.Add(sh)
                rects.append((x0 + (n - c) * module, y0 + r * module, x0 + (n - a) * module, y0 + (r + 1) * module))
        ok = 0
        for r in range(n):
            for c in range(n):
                x = x0 + (n - 1 - c) * module + module / 2.0
                y = y0 + r * module + module / 2.0
                hit = any(rx0 <= x <= rx1 and ry0 <= y <= ry1 for (rx0, ry0, rx1, ry1) in rects)
                if hit == bool(m[r][c]):
                    ok += 1
        if ok != n * n:
            self.problems.append(f"QR: {n * n - ok} module(s) drawn wrong")
        for p in self.allpads:
            if p["through"] and x0 - 1 < p["x"] < x0 + n * module + 1 and y0 - 1 < p["y"] < y0 + n * module + 1:
                self.problems.append(f"QR: through-hole pad {p['ref']}.{p['num']} is under the code")
        for (net, vx, vy, d) in self.vias:
            if x0 - 1 < vx < x0 + n * module + 1 and y0 - 1 < vy < y0 + n * module + 1:
                self.problems.append(f"QR: via at ({vx:.2f}, {vy:.2f}) is under the code")
        return n, len(rects)

    def fiducials(self):
        for (x, y) in L.FIDUCIALS:
            for layer, r in ((pcbnew.F_Cu, 0.5), (pcbnew.F_Mask, 1.0)):
                c = pcbnew.PCB_SHAPE(self.board)
                c.SetShape(pcbnew.SHAPE_T_CIRCLE)
                c.SetLayer(layer)
                c.SetStart(pt(x, y)); c.SetEnd(pt(x + r, y))
                c.SetFilled(True); c.SetWidth(0)
                self.board.Add(c)

    def layer_markers(self):
        """Each copper layer's number in copper on that layer, all at one spot."""
        x, y = L.LAYER_MARK_AT
        for i, layer in enumerate((pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
            self._text(x + 2.2 * i, y, str(i + 1), 1.5, 0.3, layer=layer)
        # keep the planes clear of the markers on the inner layers
        for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            ra = pcbnew.ZONE(self.board)
            ra.SetIsRuleArea(True)
            ls = pcbnew.LSET()
            ls.AddLayer(layer)
            ra.SetLayerSet(ls)
            ra.SetDoNotAllowZoneFills(True); ra.SetDoNotAllowTracks(False); ra.SetDoNotAllowVias(False)
            ra.SetDoNotAllowPads(False); ra.SetDoNotAllowFootprints(False)
            o = ra.Outline(); o.NewOutline()
            for (px, py) in ((x - 1.5, y - 1.6), (x + 8.5, y - 1.6), (x + 8.5, y + 1.6), (x - 1.5, y + 1.6)):
                o.Append(mm(px), mm(py))
            self.board.Add(ra)

    # ------------------------------------------------------- the whole ---
    def build(self):
        self.place()
        self.wires()
        self.plane_vias()
        self.layer_markers()
        self.planes()
        self.silk_wires()
        self.silk_grounds()
        self.silk_opamps()
        self.silk_transistors()
        self.silk_fields()
        self.silk_boxes()
        self.silk_texts()
        self.silk_back()
        self.fiducials()
        stabilise_uuids(self.board)
        pcbnew.SaveBoard(self.out_path, self.board)
        write_stackup(self.out_path)
        self.export_geometry()
        return self

    def export_geometry(self):
        import json
        pads = [dict(ref=p["ref"], pad=p["num"], net=p["net"], x=p["x"], y=p["y"], w=p["x1"] - p["x0"],
                     h=p["y1"] - p["y0"], through=p["through"]) for p in self.allpads]
        path = os.path.join(os.path.dirname(self.out_path), "..", "out", "pcb_geom.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump({"board_w": L.BOARD_W, "board_h": L.BOARD_H, "pads": pads,
                   "tracks": len(self.segments), "vias": len(self.vias), "hops": len(self.hops)},
                  open(path, "w"), indent=1)


def stabilise_uuids(board):
    import uuid as _uuid

    def kiid(key):
        return pcbnew.KIID(str(_uuid.uuid5(_uuid.NAMESPACE_URL, "earth-nmr-pcb://" + key)))

    def mm2(pos):
        return f"{tomm(pos.x):.4f},{tomm(pos.y):.4f}"

    n = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        fp.SetUuid(kiid(f"fp/{ref}"))
        for pad in fp.Pads():
            n += 1
            pad.SetUuid(kiid(f"fp/{ref}/pad/{pad.GetNumber()}/{mm2(pad.GetPosition())}/{n}"))
        for i, it in enumerate(fp.GraphicalItems()):
            it.SetUuid(kiid(f"fp/{ref}/gfx/{i}/{it.GetClass()}"))
        for f in fp.GetFields():
            f.SetUuid(kiid(f"fp/{ref}/field/{f.GetName()}"))
    for i, t in enumerate(board.GetTracks()):
        if isinstance(t, pcbnew.PCB_VIA):
            t.SetUuid(kiid(f"via/{mm2(t.GetPosition())}/{t.GetNetname()}/{i}"))
        else:
            t.SetUuid(kiid(f"trk/{t.GetLayerName()}/{mm2(t.GetStart())}/{mm2(t.GetEnd())}/{t.GetNetname()}/{i}"))
    for i, z in enumerate(board.Zones()):
        z.SetUuid(kiid(f"zone/{z.GetLayerName()}/{z.GetNetname()}/{i}"))
    for i, d in enumerate(board.GetDrawings()):
        txt = d.GetText() if hasattr(d, "GetText") else ""
        d.SetUuid(kiid(f"gfx/{d.GetLayerName()}/{d.GetClass()}/{mm2(d.GetPosition())}/{txt[:40]}/{i}"))


if __name__ == "__main__":
    netlist = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "..", "out", "earthnmr.net")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HW, "earthnmr.kicad_pcb")
    b = Board(netlist, out).build()
    ntr = sum(1 for t in b.board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA))
    print(f"  wrote {os.path.relpath(out)}: {len(b.fps)} footprints, {ntr} tracks, {len(b.vias)} vias, "
          f"{len(b.hops)} hops")
    if b.problems:
        print(f"  !! {len(b.problems)} problem(s):")
        for p in b.problems:
            print(f"     {p}")
        raise SystemExit(1)
