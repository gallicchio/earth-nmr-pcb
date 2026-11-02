#!/usr/bin/env python3
"""Write hardware/lib/earthnmr.kicad_sym: the symbols KiCad's library lacks.

TS391: ST's single comparator in SOT-23-5, TS391ILT pinout (datasheet DocID6324
Rev 8, Figure 2, top view): 1 OUT, 2 VCC-, 3 IN-, 4 IN+, 5 VCC+.  KiCad's
Comparator:LM397 is the same drawing with the LM397's pin numbers (1 -, 3 +,
4 out); the graphics are taken from it and only the numbers are changed, so
the sheet shows the familiar comparator triangle.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kienv
from sexp_parse import SymbolLibs, Node, Sym, _clone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "hardware", "lib", "earthnmr.kicad_sym")

# LM397 pin number -> TS391ILT pin number, by function
TS391_FROM_LM397 = {"1": "3", "3": "4", "4": "1", "2": "2", "5": "5"}


def renumber(sym, mapping):
    for sub in sym.kids("symbol"):
        for p in sub.kids("pin"):
            num = p.first("number")
            num.items = [mapping[num.atom(0)]] + num.items[1:]


def set_prop(sym, name, value):
    for p in sym.kids("property"):
        if p.atom(0) == name:
            p.items = [p.items[0], value] + p.items[2:]


def rename(sym, old, new):
    sym.items = [new] + sym.items[1:]
    for sub in sym.kids("symbol"):
        a = sub.atom(0)
        if a.startswith(old + "_"):
            sub.items = [new + a[len(old):]] + sub.items[1:]


def main():
    libs = SymbolLibs(kienv.share_dir())
    lm = libs.get("Comparator", "LM397")
    ts = _clone(lm)
    rename(ts, "Comparator:LM397", "TS391")
    for sub in ts.kids("symbol"):
        a = sub.atom(0)
        if a.startswith("LM397_"):
            sub.items = ["TS391" + a[len("LM397"):]] + sub.items[1:]
    renumber(ts, TS391_FROM_LM397)
    set_prop(ts, "Value", "TS391")
    set_prop(ts, "Footprint", "Package_TO_SOT_SMD:SOT-23-5")
    set_prop(ts, "Datasheet", "https://www.st.com/resource/en/datasheet/ts391.pdf")
    set_prop(ts, "Description", "Single comparator, 2-36 V, open collector, SOT-23-5, "
                                "TS391ILT pinout: 1 OUT, 2 V-, 3 IN-, 4 IN+, 5 V+")
    # HFD3: KiCad's G5V-2_Split (unit 1 the coil, units 2 and 3 the poles, each
    # arm drawn resting on its left contact, the normally closed one) with the
    # HFD3's pin numbers (= Omron G6S-2's): coil 1 (+) and 12; pole A common 4,
    # NC 3, NO 5; pole B common 9, NC 10, NO 8 (HFD3 datasheet, wiring diagram).
    g5 = libs.get("Relay", "G5V-2_Split")
    k = _clone(g5)
    rename(k, "Relay:G5V-2_Split", "HFD3_Split")
    for sub in k.kids("symbol"):
        a = sub.atom(0)
        if a.startswith("G5V-2_Split_"):
            sub.items = ["HFD3_Split" + a[len("G5V-2_Split"):]] + sub.items[1:]
    HFD3_FROM_G5V2 = {("1", "1"): "1", ("1", "16"): "12",
                      ("2", "4"): "4", ("2", "6"): "3", ("2", "8"): "5",
                      ("3", "13"): "9", ("3", "11"): "10", ("3", "9"): "8"}
    for sub in k.kids("symbol"):
        unit = sub.atom(0).split("_")[-2]
        for p in sub.kids("pin"):
            num = p.first("number")
            num.items = [HFD3_FROM_G5V2[(unit, num.atom(0))]] + num.items[1:]
    set_prop(k, "Value", "HFD3/12")
    set_prop(k, "Footprint", "Relay_THT:Relay_DPDT_Omron_G6S-2")
    set_prop(k, "Datasheet", "https://www.hongfa.com/")
    set_prop(k, "Description", "Hongfa HFD3 DPDT signal relay, split: coil 1/12, pole A 4 COM 3 NC 5 NO, "
                               "pole B 9 COM 10 NC 8 NO (the Omron G6S-2's pinout)")
    upins = {}
    for sub in k.kids("symbol"):
        unit = sub.atom(0).split("_")[-2]
        for p in sub.kids("pin"):
            a = p.first("at")
            upins[(unit, p.first("number").atom(0))] = (float(a.atom(0)), float(a.atom(1)))
    # COM at the bottom, NC on the left (where the arm rests), NO on the right
    for u, com, nc, no in (("2", "4", "3", "5"), ("3", "9", "10", "8")):
        assert upins[(u, com)][1] < 0 and upins[(u, nc)][0] < 0 < upins[(u, no)][0], (u, upins)
    root = Node("kicad_symbol_lib", [])
    root.items = [Node("version", [Sym("20241209")]), Node("generator", ["earthnmr-gen"]),
                  Node("generator_version", ["10.0"]), ts, k]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(root.render() + "\n")
    # the check: every pin by its function
    pins = {}
    for sub in ts.kids("symbol"):
        for p in sub.kids("pin"):
            pins[p.first("name").atom(0)] = p.first("number").atom(0)
    assert pins == {"-": "3", "+": "4", "": "1", "V-": "2", "V+": "5"}, pins
    print(f"  wrote {os.path.relpath(OUT)}: TS391 (OUT 1, V- 2, IN- 3, IN+ 4, V+ 5), "
          f"HFD3_Split (coil 1/12, A 4/3/5, B 9/10/8)")


if __name__ == "__main__":
    main()
