# Design notes

Why each block is what it is.  Every value below comes from `sim/design.py`, which
does the arithmetic and writes `sim/design.json`; the sheet, the board's silkscreen
and the generated documents read their numbers from there, and the simulation
(`sim/nmr_sim.py`, ngspice on the exported netlist) checks the arithmetic.

## The measurement, in numbers

- **The site.**  Harvey Mudd College, Claremont CA: IGRF-14 for 2026-11-01 gives
  46,028 nT, inclination 58.9 degrees, declination 11.2 degrees east.  The protons'
  Larmor frequency is 42.577 Hz/µT x 46.03 µT = 1959.8 Hz.  The world's field runs
  22-67 µT, 937-2853 Hz; the tank reaches all of it.
- **The coil.**  916 turns of AWG 20 in four layers on an 89 mm former, 200 mm long:
  26.8 mH, 8.86 ohm, Q 37 at 1960 Hz, 5.2 mT per amp at the centre.  A litre of water
  fills it.
- **Polarizing.**  1.5 A from a 13 V supply: 7.8 mT, 170 times the Earth's field,
  20 W in the coil while it is on.  The protons' magnetization grows toward its
  equilibrium in this field with the water's T1 (2-3 s).
- **The signal.**  At the switch-off that magnetization is left square to the Earth's
  field and precesses about it, inducing 1.2 µV in the coil; the tank's Q makes that
  45 µV across the tank.  At OUT on HIGH (x20301 from the tank) it is 0.88 V by the
  arithmetic, 0.83 V in the simulation.
- **The noise.**  Referred to the tank: its own thermal noise (the tank's 12.3 kohm
  at resonance) 14.1 nV/rtHz, the two OPA197 7.8, the two 1k input resistors 5.7, the
  gain resistor 1.8, the bias resistors 1.1: 17.2 nV/rtHz in all, a noise figure of
  1.7 dB over the coil alone.  In the tank's 83 Hz noise bandwidth that is a
  single-shot SNR of about 46 dB (the simulation: 46 dB).

## The blocks

### Polarizing supply

The polarizing current comes from its own supply (6-30 V, up to 3 A), not from the
±15 V: 20 W for seconds at a time is more than a bench ±15 V wants to give, a
battery is the quietest source there is, and keeping the two apart keeps the
polarizing current's return away from the receiver.  It returns through the ground
plane from R4 to J2, along the board's left edge, away from the preamplifier.
F1 (3 A hold, resettable) is first; D5 (SS34) across the supply after it blows it
if the supply is reversed; D6 (SMBJ33A) takes a hot-plugged lead's ringing; C5
(470 µF) holds the supply up at the board.

### The coil and the relay

One coil polarizes and receives.  K1, a DPDT relay, connects it either to the
polarizing supply and the switch (energized) or across the tank (at rest).  Both
of the coil's ends move, so at rest the coil floats on the tank alone, and while
it polarizes the receiver sees only the tank's capacitors.

The relay never switches current.  The sequencer (below) closes it 18 ms before
Q1 turns on and opens it 15 ms after Q1 has turned off, when the coil's current
has been gone for 14 ms: its gold-flashed contacts carry the microvolt signal and
the polarizing current but never make or break either.  That is what lets a 3 A
signal relay do this job.

### The polarizing switch

Q1 (IRFS4227, 200 V, 26 mohm) turns the current on and off.  At switch-off the
coil's current must go somewhere: D7 (SMCJ100A, from drain to source) clamps the
drain at about 125-130 V, and the coil's current falls in a straight line,
dI/dt = V/L, to zero in 0.39 ms (the simulation: 127 V peak, 0.39 ms, 30 mJ into D7).

A straight line matters.  The protons follow the field's direction adiabatically
while it turns slowly compared with their Larmor period, and are left behind when
it turns fast.  The field's direction swings from the coil's axis to the Earth's
field while the polarizing field falls through the last few times the Earth's
field: on this ramp that takes 7 µs, against a Larmor period of 500 µs, so the
magnetization is left along the coil's axis, square to the Earth's field, and
precesses.  An RC or resistor-limited decay slows exactly where it must be fast.

R5 (47 ohm) damps the gate; R6 (100k) holds it off with nothing driving it; R4
(0.1 ohm, 2 W) is the I POL loop, 0.1 V per amp.

### The tank

The coil and the bank of C0G capacitors resonate at the Larmor frequency: the
tank's Q (36 in the simulation) gives the signal x35 before any amplifier, and
the tank is the first filter.  The eight switches of SW1 add binary weights of
3.3 nF each (3.3, 6.8, 13.3, 26.8, 53.8, 106.8, 210, 420 nF), so any value to 841 nF
is within half a step; one step moves the tank 13 Hz near 2 kHz, a quarter of its
54 Hz width.  C0G because the tank must not move with temperature or the
voltage across it.  Here 246 nF tunes it: switches 1, 2, 4, 7, 246.9 nF, 1956 Hz.

D9 (SMBJ12CA, bidirectional) across the tank is idle unless the relay ever opens
with coil current flowing (it must not, but a wiring fault could): then it takes
the coil's energy instead of the capacitors and the preamplifier's inputs.

### CAL IN

R14 (1M) injects a known current into the tank, 1 µA per volt from a generator
terminated in R13 (51 ohm).  It is how the tank is tuned without protons: sweep a
sine and find the peak at OUT (1 V gives about 4 V at OUT on LOW at the peak).

### The preamplifier

A three-op-amp instrumentation amplifier, x101 (Rg = R19, 200 ohm, with 10k
feedback resistors), across the two ends of the tank, so the coil's cable can pick
up mains common-mode and the receiver ignore it.  OPA197: 5.5 nV/rtHz at 1 kHz,
femtoamp input current (the tank's 12 kohm sees no current noise worth counting),
36 V, rail to rail, on JLCPCB's shelf.  R15 and R16 (1k) in series with the inputs
limit the current into their protection diodes if anything ever reaches the tank;
R11 and R12 (1M) give the inputs a DC path to ground.  U3 is a unity difference
amplifier.

### The filters and the gain

The high-pass (two Sallen-Key stages, 726 Hz Q 0.55 and 670 Hz Q 1.31: fourth order,
-3 dB at 688 Hz) takes out 60 Hz (-85 dB) and its harmonics (120 Hz -61 dB, 180 Hz
-47 dB), and the relay's step.  The low-pass (4.1 kHz, Q 0.72) bounds the noise.
The band, -3 dB from 688 Hz to 4.2 kHz, passes the whole world's Larmor range
(937-2853 Hz) within 0.9 dB.  U7 then gives x21 or x201 (SW2), x2121 or x20301 from
the tank to OUT.  OUT goes through 1k to its BNC, safe into a sound card's input.

### The headphones

The FID is an audio tone, so the board lets you hear it.  OUT also feeds R58 (62k)
and the VOLUME knob, RV3 (10k, an ALPS RK09K; its pin 3, the clockwise end, on R58,
so clockwise is louder): at most x0.139 of OUT reaches the wiper, and OUT carries
72 kohm more, nothing to U7.  U12, an OPA197 follower, drives both ears with the same
signal through 100 ohm each (R56 to the tip, R57 to the ring): x0.242 into a 32 ohm
earpiece, x0.034 of OUT at full volume.  A 0.8 V FID on HIGH is 30 mV in the ear,
about 81 dB SPL in a 100 dB/mW earpiece (3 mV, 62 dB, on LOW); OUT at a rail, as at
the relay's hand-over, would be 0.5 V, about 106 dB, so the handbook says to start
low.  The 100 ohm keep the follower stable into a cable and limit a mono plug, which
shorts the ring to the sleeve, to 21 mA: 42 mW in an 0805 rated 125 mW, and both
ears shorted are within the OPA197's 65 mA.  The simulation (the netlist with the
knob fully clockwise and 32 ohm in each ear) gives x0.0337, the arithmetic's
number.

J9 is Same Sky's SJ1-3523N (C20182914), a through-hole right-angle stereo jack whose
datasheet (09/12/2024) numbers its pins 1 sleeve, 2 tip, 3 ring.  KiCad's footprint
for it names the same three holes S, T and R, and JLCPCB's land pattern, numbered
1-3, lies on ours hole for hole, pegs included, with that map
(`scripts/check_rotations.py`): three sources that agree.  Both ears carry the same
signal, so even a tip and ring swapped would be harmless; the sleeve is what must be
right, and it is the pin on its own, nearest the opening.  The draft's PJ-320D was dropped
because its datasheet shows no pin roles.

### The sequencer

A 555 (U11) runs astable with diode-steered charge and discharge, so POLARIZE TIME
(RV1, through D10) and LISTEN TIME (RV2, through D11) are independent, each 0.2 to
4.7 s with 3 µF of polypropylene film (C50-C52: film because the timer swings them
through 5 V and X7R would move).  SEQUENCE (SW3) picks the timer or POLARIZE IN
(U8, a comparator at 1.33 V with 0.15 V of hysteresis, clamped by D12); MODE (SW4)
runs it or holds POL CMD low (listen only, for tuning).

From POL CMD two comparators against half the rail make the order of things: U10
drives RELAY high at once (D14 charges C56) and holds it 15 ms after POL CMD falls
(R50, C56); U9 drives GATE high 18 ms after POL CMD rises (R49, C55) and low at once
(D13 discharges C55).  Q3 follows POL CMD to SYNC OUT, the scope's trigger.

### Power

±15 V through series Schottkys (reverse protection), Schottky clamps to ground for
an open rail, bulk and bypass capacitors and a lamp each.  Every IC has its own
100 nF at each supply pin (C80-C99).

## The simulation

`sim/nmr_sim.py` builds ngspice decks from the netlist the schematic exports (the
board's own connections, not a separate model) with behavioural models of the
op-amps, comparators, relay and switch, and checks against the arithmetic: the tank's
peak and Q, the receiver's gain and band, 60/180 Hz rejection, noise and SNR, the CAL
response, the switch-off (peak voltage, ramp time, energy), the sequencer's
delays and the headphones' level.  The build fails if they disagree beyond a stated tolerance.  Results are in
`sim/results.json` and `docs/images/sim_receiver.png`, `docs/images/sim_switch_off.png`.

## The board

- **The silkscreen is the schematic.**  Every wire on the top copper is drawn on the
  silkscreen where it runs (`scripts/layout.py` lists them; `scripts/gen_pcb.py` lays
  each as copper and as silkscreen, so the two cannot disagree).  Op-amps and
  comparators are triangles with their + and -; transistors are circles with bar,
  arrow and letters; the relay's pins are numbered and its legend says which
  contacts make when.
- **Four layers**: ground on In1 (solid), +15 V on In2, -15 V on the back.  The rails
  are not drawn: every pad on one has its own via, and the silkscreen marks it with a
  ground symbol or a rail flag.  Each op-amp's two 100 nF hang from its own supply vias.
- **Three hops**, each a short dive to the back layer drawn as a hop on the silkscreen:
  U2's + input under the gain-setting column, and GATE under the coil's loop and
  under the threshold bus.  The polarizing current needs none: the coil's two leads
  close a loop round the polarizing switch, Q1 sitting inside it.
- The polarizing current's tracks are 2 mm (3 A on 1 oz outer copper); its ground pads
  (R4, D5, D6, C5) have two or three 1 mm vias each.
- Every BNC faces off an edge; the terminal blocks' wire openings face their edges;
  the headphone jack's opening is at the right edge, its nose past it as Same Sky's
  drawing puts it (KiCad's footprint for it draws an edge notch and marks it out of
  the BOM and placement file: `gen_pcb.py` removes the first and clears the second).
- 243 x 150 mm: the signal chain wants to be one row.

## Decisions taken along the way

| when | decision | why |
|---|---|---|
| circuit | one coil, a DPDT relay, dry switching | the simplest way to keep 3 A and 130 V out of a microvolt receiver |
| circuit | TVS clamp, linear switch-off | a fast, non-adiabatic switch-off with the energy dumped in a part made for it |
| circuit | binary C0G bank on a DIP switch | tunes anywhere on Earth in 13 Hz steps, no trimmer capacitor to drift |
| circuit | the PJ-320D audio jack dropped | its tip/ring/sleeve pinout could not be confirmed from the datasheet |
| circuit (prompt 2) | a headphone output: VOLUME knob, OPA197 follower, 100 ohm each ear, Same Sky SJ1-3523N | the FID is audible; the jack's pinout is in the maker's table, KiCad's footprint and JLCPCB's numbered land pattern, all agreeing |
| circuit (prompt 2) | both ears the same signal, at x0.034 of OUT into 32 ohm | the FID is mono; 81 dB SPL for a typical FID, a rail at full volume 106 dB, not more |
| schematic | J3's terminals: shield on top, A in the middle, B at the bottom | the board's floorplan: the coil's leads reach the relay without crossing |
| schematic | SW3's throws: 1 EXT, 3 INT | lets the sequencer lay out flat, the switch's common between its two sources |
| board | 0.6 / 0.3 mm vias | JLCPCB's standard for four layers, annular ring 0.15 mm |
| parts | the 47 nF C0G of column 5: Holy Stone C1206N473J050T (C5451690) | the 100 V part first chosen (C20617849) had sold out on 2026-11-02 |

## Not yet proven: check on the first board

The risks for a board that does not work out of the box, most likely first:

1. **The relay's pinout.**  HFD3 as the Omron G6S-2 (1 coil +, 12 coil -; pole A 4
   COM, 3 NC, 5 NO; pole B 9 COM, 10 NC, 8 NO), read from Hongfa's drawing.  JLCPCB's
   own land pattern for it lies on ours hole for hole (`scripts/check_rotations.py`),
   but its symbol carries numbers only, so the roles rest on the drawing.  With the
   relay at rest, TANK+ to TANK- should measure the coil's 8.9 ohm through J3.
2. **TS391's pinout.**  The symbol (`scripts/gen_symbols.py`) is drawn for 1 OUT, 2 V-,
   3 IN-, 4 IN+, 5 V+ from ST's datasheet, and JLCPCB's symbol for C71896 says the same
   pin for pin (`scripts/check_pinouts.py`).  Were the inputs swapped the sequencer
   would invert: bring-up 5.2 shows it at once.
3. **The polarizing transient.**  127 V and 0.4 ms are simulated with an ideal coil.
   A real coil's interwinding capacitance rings after the clamp; watch DRAIN with a
   x10 probe on the first switch-off, at a low polarizing voltage first.
4. **Ground currents.**  The polarizing current returns through the ground plane,
   away from the preamplifier but through the same plane; it flows only while the
   receiver is disconnected, but its switch-off edge could upset the receiver for a
   few milliseconds.  The 19 ms before the relay hands the coil over should cover it.
5. **The DIP switch's ON side.**  ON is taken as toward pads 1-8; the silkscreen says
   so.  If the switches work backwards, read them inverted.
6. **The slide switches' sense.**  The MSK12C02's knob connects the common to the
   terminal it slides toward (as on the other boards); the silkscreen's LOW/HIGH,
   EXT/TIMER and LISTEN/RUN assume it.
7. **Thin stock.**  The BNC jacks (215 on JLCPCB's shelf on 2026-11-02, four a board) and
   the headphone jack (353, one a board; SJ1-3524-SMT-TR, C20182907, is the same jack in
   surface mount, on another footprint).
8. **JLCPCB's placements.**  Their drawings of the relay (+270, origin the pin field's
   middle), the 555 (+270), the SOT-23s (+180), the SOT-23-5s (+180), the D2PAK (its
   origin 2.56 mm off KiCad's) and the terminal blocks (+180) are turned or shifted
   from KiCad's; the upload CPL corrects each, and `scripts/check_rotations.py` lays
   their drawing where the upload puts it: every pad within 0.3 mm of ours (D9's SMB
   0.44 mm, its pads drawn larger) and every body inside our courtyard, facing the
   right way.  Look at them in the preview (`PLACEMENT_CHECKS.txt`).
9. **The headphones' click.**  The arithmetic says OUT can reach a rail at the relay's
   hand-over; nobody has listened yet.  If it is loud at a comfortable FID volume, the
   limiter of rev B (two diodes at RV3's wiper) can be added by hand.

## Ideas for rev B

- A pulse coil or the same coil driven at the Larmor frequency after polarizing, for
  spin echoes and T2 rather than T2*.
- A gradiometer: two coils wound in opposition, one with water and one without, to
  cancel distant interference.
- A limiter at the VOLUME knob's wiper (two diodes to ground), to take the relay's
  click in the headphones down 10 dB without touching the FID.
- Constant-current polarizing (so the field is the same whatever the battery's
  voltage), and a soft turn-on.
- A smaller board: the signal chain folded once.
