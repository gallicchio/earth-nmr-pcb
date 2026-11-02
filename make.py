#!/usr/bin/env python3
"""Build everything: the design arithmetic, footprints, models, schematic,
simulation, board, checks, fab package and the generated documents.

    ./make.py              build and check everything
    ./make.py --stage sch  run one stage only (design, libs, sim, sch, pcb, out, docs)
    ./make.py --clean      delete everything the build generates

Every stage stops the build on a failed check: ERC or DRC not clean, the
netlist not the circuit (scripts/check_circuit.py), the simulation not
agreeing with the design arithmetic (sim/nmr_sim.py), the fab package not
what a fab's importer expects (scripts/check_outputs.py).
"""
import argparse, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, "scripts")
SIM = os.path.join(ROOT, "sim")
HW = os.path.join(ROOT, "hardware")
OUT = os.path.join(ROOT, "out")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, SCRIPTS)
import kienv                                     # noqa: E402

STEM = "earthnmr"
GENERATED = [
    f"hardware/{STEM}.kicad_sch", f"hardware/{STEM}.kicad_pcb", f"hardware/{STEM}.kicad_pro",
    "hardware/sym-lib-table", "hardware/fp-lib-table", "hardware/lib/earthnmr.kicad_sym",
    "hardware/lib/earthnmr.pretty/", "hardware/lib/earthnmr.3dshapes/",
    "sim/design.json", "sim/results.json",
    "docs/images/", "docs/MANUFACTURING.md", "out/", "build/",
]
ALSO_TRANSIENT = [f"hardware/{STEM}.kicad_prl", "hardware/fp-info-cache"]


class Fail(Exception):
    pass


def banner(txt):
    print(f"\n=== {txt} " + "=" * max(0, 64 - len(txt)))


def run_py(path, *args):
    r = subprocess.run([sys.executable, path, *args], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stdout.write(r.stderr)
        raise Fail(f"{os.path.relpath(path, ROOT)} failed")
    return r.stdout


def sys_py(script, *args):
    return run_py(os.path.join(SCRIPTS, script), *args)


def kicad_py(script, *args):
    """A script that imports pcbnew, under a Python that has it (kienv.pcbnew_python)."""
    r = subprocess.run(kienv.python_cmd(os.path.join(SCRIPTS, script), *args), capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stdout.write(r.stderr)
        raise Fail(f"{script} failed")
    return r.stdout


def count_violations(path):
    return sum(1 for line in open(path) if line.startswith("["))


def export_netlist():
    os.makedirs(OUT, exist_ok=True)
    net = os.path.join(OUT, STEM + ".net")
    kienv.cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, os.path.join(HW, STEM + ".kicad_sch"))
    return net


def stage_design():
    banner("design arithmetic")
    run_py(os.path.join(SIM, "design.py"))


def stage_libs():
    banner("symbols, footprints, models and project files")
    sys_py("gen_symbols.py")
    sys_py("gen_models.py")
    sys_py("gen_footprints.py")
    kienv.cli("fp", "upgrade", os.path.join(HW, "lib", "earthnmr.pretty"), "--force")
    sys_py("gen_project.py")


def stage_sim():
    banner("simulation (ngspice, from the schematic's netlist)")
    # the simulation reads the netlist the schematic exports: draw the sheet
    # and export it first (a fresh clone has none: out/*.net is not committed)
    sys_py("gen_sch.py")
    export_netlist()
    r = subprocess.run([sys.executable, os.path.join(SIM, "nmr_sim.py"), "--plots"], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stdout.write(r.stderr)
        raise Fail("the simulation disagrees with the design, or did not run (is ngspice installed?)")


def stage_sch():
    banner("schematic")
    sys_py("gen_sch.py")
    sch = os.path.join(HW, STEM + ".kicad_sch")
    kienv.cli("sch", "upgrade", sch)
    os.makedirs(OUT, exist_ok=True)
    rpt = os.path.join(OUT, "erc.rpt")
    kienv.cli("sch", "erc", "--format", "report", "--severity-all", "-o", rpt, sch, check=False)
    n = count_violations(rpt)
    print(f"  ERC: {n} violation(s)")
    if n:
        raise Fail(f"ERC reported {n} violations -- see {os.path.relpath(rpt, ROOT)}")
    net = export_netlist()
    out = sys_py("check_circuit.py", net)
    if "all circuit checks passed" not in out:
        raise Fail("the netlist is not the circuit")
    out = sys_py("check_schematic.py", sch)
    if "no text overlaps" not in out:
        raise Fail("the schematic sheet has overlapping or stray text")


def stage_pcb():
    banner("PCB")
    pcb = os.path.join(HW, STEM + ".kicad_pcb")
    net = os.path.join(OUT, STEM + ".net")
    if not os.path.exists(net):
        net = export_netlist()
    kicad_py("gen_pcb.py", net, pcb)
    sys_py("gen_project.py")
    rpt = os.path.join(OUT, f"drc-{STEM}.rpt")
    kienv.cli("pcb", "drc", "--format", "report", "--severity-all", "--schematic-parity",
              "-o", rpt, pcb, check=False)
    n = count_violations(rpt)
    print(f"  DRC: {n} violation(s), all severities, with schematic parity")
    if n:
        raise Fail(f"DRC reported {n} violations -- see {os.path.relpath(rpt, ROOT)}")


def stage_out():
    banner("manufacturing outputs")
    sys_py("gen_outputs.py")
    out = sys_py("check_outputs.py")
    if "ALL FAB CHECKS PASSED" not in out:
        raise Fail("the fab package did not pass its checks")


def stage_docs():
    banner("documentation")
    sys_py("gen_docs.py")


def clean():
    banner("clean")
    locked = any(n.startswith("~") and n.endswith(".lck") for n in os.listdir(HW)) if os.path.isdir(HW) else False
    for rel in GENERATED + ([] if locked else ALSO_TRANSIENT):
        path = os.path.join(ROOT, rel.rstrip("/"))
        if rel.endswith("/"):
            if os.path.isdir(path):
                shutil.rmtree(path)
                print(f"  removed {rel}")
        elif os.path.exists(path):
            os.remove(path)
            print(f"  removed {rel}")


STAGES = [("design", stage_design), ("libs", stage_libs), ("sim", stage_sim), ("sch", stage_sch),
          ("pcb", stage_pcb), ("out", stage_out), ("docs", stage_docs)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--stage", action="append", choices=[n for n, _ in STAGES])
    a = ap.parse_args()
    if a.clean:
        clean()
        return 0
    print(kienv.describe())
    try:
        for name, fn in STAGES:
            if a.stage and name not in a.stage:
                continue
            fn()
    except Fail as e:
        print(f"\nBUILD FAILED: {e}")
        return 1
    print("\nBUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
