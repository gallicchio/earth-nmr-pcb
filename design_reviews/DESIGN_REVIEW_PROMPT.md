# Design review brief: Earth's Field NMR, rev A

**Nothing you say in the chat will be read or kept.  Your review exists only if it is a
file in your directory.**  Make a directory

    design_reviews/<YYYY-MM-DD>_<YourModel-Version>/

at the top of this repository, dated the day you start and named after yourself
(letters, digits, dots, hyphens and underscores only), and write your report as
`REPORT.md` inside it.  Creating that directory and writing into it is **required**; it
is not a change to the project.  Write your verdict and your findings table into the
report first, then fill in the details, so a half-finished report survives an
interruption.

**Look for problems at every level**, from whether the instrument will see protons at
all down to whether the copper will work.  A finding that the board will not measure
what it claims is worth as much as a short circuit; so is a number in a document that
the board does not deliver.  Nothing is out of scope because the author decided it: the
decisions are in `CLAUDE_CODE_CHAT.md` with their reasons, and a reasoned case against
one is welcome.

## 0. Ground rules

- **Only ever create, edit or delete files inside your own directory.**
- **Do not change git**: no add, commit, checkout, reset, stash, branch, pull or push.
  Reading commands (log, show, diff, blame, grep) are fine.
- **Do not run `./make.py` in place**, nor any `scripts/gen_*.py`, `sim/design.py` or
  `sim/nmr_sim.py`, `scripts/jlc_api.py`, `scripts/easyeda.py`: they rewrite
  `hardware/`, `out/`, `docs/`, `sim/*.json` and the caches that other reviewers are
  reading.  To build or try a change, copy the project into your directory first:

  ```bash
  D=design_reviews/<YYYY-MM-DD>_<YourModel-Version>
  mkdir -p "$D"
  rsync -a --exclude .git --exclude build/ --exclude datasheets/ --exclude design_reviews/ ./ "$D/project/"
  cd "$D/project" && ./make.py          # about two minutes; needs KiCad 10 and ngspice
  ```

  Put any change you propose in your report as a patch against the generators.
- **Everything the build makes is committed**, so nothing has to be built to review it:
  `hardware/earthnmr.kicad_sch` and `.kicad_pcb`, `out/earthnmr/` (gerbers, BOM, CPL,
  prints, `PLACEMENT_CHECKS.txt`), `sim/design.json` and `sim/results.json`,
  `docs/images/`.
- **Datasheets are not in git** (copyright).  Fetch what you need
  (`python3 scripts/jlc_datasheet.py <LCSC code>` in your copy) or read the makers' pages.
- **Settle disagreements with a datasheet, a calculation or a simulation**, not by
  memory or majority.
- Other reviewers' directories may already be there.  Do not read them until your own
  report is written.

## 1. What it is

An Earth's-field proton precession instrument: a 243 x 150 mm four-layer board whose
silkscreen is its schematic.  A coil (916 turns of AWG 20, 26.8 mH, wound by the user)
around a litre of water is polarized with 1.5 A from its own supply; Q1 switches the
current off through a 130 V clamp in 0.4 ms; a DPDT relay, which by design never makes
or breaks current, then hands the coil to a tank tuned to the protons (1960 Hz in
Claremont, set on an eight-switch binary C0G bank); an OPA197 instrumentation
amplifier (x101), a 688 Hz-4.2 kHz band-pass and a x21/x201 gain stage bring the
1.2 µV free induction decay to about 0.8 V at OUT.  A 555 and two comparators sequence
it; POLARIZE IN and SYNC OUT let a computer run it.

| read | for |
|---|---|
| `README.md`, `docs/HANDBOOK.md`, `docs/DESIGN_NOTES.md` | the summary, the user's guide, the reasoning and the known risks |
| `docs/MANUFACTURING.md` | the order form, the costs (estimated), the JLCPCB rotations, the parts and their stock |
| `CLAUDE_CODE_CHAT.md` | what was asked, the decisions and the dead-on-arrival risks |
| `sim/design.py`, `sim/design.json` | the arithmetic: every value on the sheet and board comes from it |
| `sim/nmr_sim.py`, `sim/results.json` | the ngspice simulation of the exported netlist and its checks |
| `scripts/parts.py` | every part, its LCSC code and stock, the JLCPCB rotation table |
| `scripts/gen_sch.py`, `scripts/check_circuit.py` | the sheet and the 365 netlist assertions |
| `scripts/layout.py`, `scripts/gen_pcb.py` | the board: placements and wires, and how each wire becomes copper and silkscreen |

## 2. The claim to break

"Built by JLCPCB from `out/earthnmr/` as it stands, with the coil of the handbook and a
12 V battery, outdoors in Claremont, it shows the protons' free induction decay at OUT,
and nothing on the board or in its documents is wrong."  The build's own checks: ERC 0;
DRC 0 at every severity with schematic parity; 365 circuit assertions; the simulation
within tolerance of the arithmetic; the fab-package checks; 13 document claims.

## 3. What to attack

1. **The physics.**  Polarizing field and time, the switch-off (`docs/DESIGN_NOTES.md`:
   is 7 µs through the Earth's-field region really non-adiabatic enough, and does the
   clamp's linear ramp hold with a real coil?), the relay's dead time (19 ms after
   switch-off before the receiver listens), the coil's orientation, the signal and noise
   estimates against published Earth's-field NMR instruments.
2. **The receiver.**  Is the OPA197 the right choice against the tank's 12 kohm?  Bias,
   protection (R15/R16, D9), overload recovery after the relay's step, the filters'
   rejection of 60 Hz harmonics, the gain plan, OUT into a sound card.
3. **The polarizing path.**  Q1, D7, R4, F1, D5, D6, C5 at 6-30 V and up to 3 A: power,
   SOA, the 2 mm tracks and the ground return through In1, the relay's contacts.
4. **The sequencer.**  The order RELAY-on, GATE-on, GATE-off, RELAY-off in every case,
   at power-up, with MODE and SEQUENCE switched mid-cycle, with POLARIZE IN driven fast.
5. **Pinouts.**  The two symbols drawn here (TS391, HFD3) and every footprint against
   its datasheet; the BAV99; the D2PAK; the DIP switch's ON side; the slide switches'
   sense.
6. **The board.**  The silkscreen as a schematic (can a student read it?), clearances,
   the planes and their vias, the hops, assembly by JLCPCB (rotations, THT parts).
7. **The documents.**  Every number in README, HANDBOOK, DESIGN_NOTES and on the board
   against `sim/design.json`, `sim/results.json` and the board.

## 4. The report

`REPORT.md`: a verdict (order as is / order after named fixes / do not order), then a
table of findings (number, severity: blocker / major / minor / nit, where, what, the
evidence, the fix), then the details.  Put anything you built or simulated beside it.
