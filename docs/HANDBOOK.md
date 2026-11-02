# Handbook

How to wind the coil, tune the board for where you are, bring it up one block at
a time, and see the protons.  The numbers quoted come from the design arithmetic
(`sim/design.py`, written to `sim/design.json`) and the ngspice simulation of the
exported netlist (`sim/nmr_sim.py`, `sim/results.json`); the first boards will say
how close they are.

## 1. What you need besides the board

- **The coil** (section 2) and a litre of water in a plastic bottle that fits inside it.
- **±15 V**, 100 mA each rail, into POWER (J1: +15 V, ground, -15 V, left to right).
- **A polarizing supply**, 6-30 V and up to 3 A, into POLARIZE SUPPLY (J2, + at the
  bottom pin).  A 12 V lead-acid or LiFePO4 battery is the quietest choice; a bench
  supply works, and its ripple does not matter (the receiver listens only while the
  supply is disconnected from the coil).
- **A shielded twisted pair** from the coil to COIL (J3: shield, A, B from the top).
- **An oscilloscope** on OUT, triggered from SYNC OUT.  A computer's sound card
  (through OUT's 1k and a BNC-to-3.5 mm lead) records the signal for a Fourier transform.
- A signal generator for CAL IN, for tuning.

## 2. The coil

The design assumes (and `sim/design.py` computes for) 916 turns of AWG 20
enamelled copper (0.81 mm), wound in 4 layers on a 89 mm (3.5 inch) former 200 mm
long: about 266 m of wire.  That gives about 26.8 mH and 8.9 ohm, a Q of 37 at the
Larmor frequency here, and a polarizing field of 5.2 mT per amp at the middle.  Any
former that is not metal will do: PVC drain pipe, a cardboard tube varnished hard.
Keep the layers tight and even; a layer of tape between layers is fine.

The tank tunes any coil from 7.8 mH to 1.8 H to the protons here, so a different
coil works too: wind what you have, measure its inductance, and recompute the
capacitance (section 4).  More turns give more signal and more resistance; with the
coil above, the receiver adds 1.7 dB to the coil's own thermal noise.

Wire A and B to the coil's two ends (either way round) and the cable's shield to
the shield pin only, at the board end only.

## 3. Where

The protons precess about the Earth's field, so the field must be the same all
through the bottle: a steel desk, a radiator, a car or a reinforced floor nearby
spreads the frequencies and the signal dies in milliseconds instead of a second.
Mains wiring, transformers and computers put 60 Hz and its harmonics into the coil.
Outdoors, a few metres from anything, is best; a wooden table in a quiet room can
work.

Point the coil's axis **horizontal and east-west** (magnetic), so it is square to the
Earth's field, which here dips 59 degrees below horizontal toward magnetic north
(declination 11 degrees east).  The signal goes as the sine of the angle between the
coil's axis and the field, twice: once for polarizing, once for listening.

## 4. Tuning the tank

The protons' frequency is f = 42.577 Hz/µT x B.  Find B for your site from NOAA's
magnetic field calculator (the IGRF model).  In Claremont, B = 46.0 µT and the Larmor
frequency is 1960 Hz; the Earth's field runs from 22 to 67 µT, 937 to 2853 Hz.

The tank resonates at f = 1 / (2 pi sqrt(L C)).  For the coil above, 1960 Hz needs
246 nF.  SW1's eight switches add, when ON (the side marked ON, toward the
capacitors), the capacitance printed under each column:

| switch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| nF | 3.3 | 6.8 | 13.3 | 26.8 | 53.8 | 106.8 | 210 | 420 |

Add the switches up to the capacitance you need: switches 1 2 4 7 ON for 246.9 nF,
1956 Hz.  One step of 3.3 nF moves the tank about 13 Hz near 2 kHz; the tank is 54 Hz
wide (Q 36), so one step either way is close enough.

Check it with CAL IN (section 5.3): the tank's peak, read at OUT as you sweep the
generator, should sit at the Larmor frequency.

## 5. Bring-up

### 5.1 Power alone

Set the switches first: **MODE** (SW4) to LISTEN, **SEQUENCE** (SW3) to TIMER,
**GAIN** (SW2) to LOW.  Nothing on COIL or POLARIZE SUPPLY.  Power ±15 V with the
supply's current limit at 100 mA: both green lamps (LED1, LED2) light.  The series
Schottkys D1 and D2 protect the board from a reversed supply (neither lamp lights,
nothing is hurt).

| loop | node | expect |
|---|---|---|
| +15V, -15V | the rails after the diodes | +14.6 V, -14.6 V |
| POL CMD | the sequencer's command | 0 V (MODE at LISTEN) |
| RELAY, GATE | the relay driver's and the switch's drive | 0 V |
| TANK+, TANK- | the tank, through the relay's rest contacts | 0 V |
| INA A, INA B, PREAMP, HP1, HP, LP, OUT | the receiver | 0 V within a few mV, and noise |

### 5.2 The sequencer

MODE to RUN, still no polarizing supply.  The timer runs: TIMER ramps between 5 and
10 V, POL CMD is a square wave between 0 and about 13 V, RV1 (POLARIZE TIME) sets its
high time and RV2 (LISTEN TIME) its low time, each 0.2 to 4.7 s.  On each rising edge
of POL CMD, RELAY goes high at once (the relay clicks, LED4 lights) and GATE 18 ms
after; on each falling edge GATE drops at once and RELAY 15 ms after.  So the relay
always closes before the switch turns on and opens after it has turned off: its
contacts never make or break the polarizing current.

| loop | expect |
|---|---|
| TIMER | a ramp between 5 V and 10 V |
| POL CMD | 0 / 13 V, the polarizing command |
| DELAY | the RC ramp toward POL CMD (220k, 100 nF) that turns GATE on |
| HOLD | the RC fall from POL CMD (270k, 100 nF) that holds RELAY |
| RELAY | 0 / 15 V |
| GATE | 0 / 15 V, GATE 18 ms after RELAY |
| EXT | POLARIZE IN's comparator (SEQUENCE at EXT): high above 1.3 V in |

MODE back to LISTEN.

### 5.3 The receiver, with the coil

Connect the coil.  MODE at LISTEN: the relay rests, the coil is the tank's inductor.
OUT shows the receiver's noise, about 12 mV rms on HIGH, and whatever the room puts
into the coil (60 Hz is mostly filtered: x1 at OUT on HIGH, against x700,000 for the
protons).  Put a 1 V sine into CAL IN and sweep it through 2 kHz: OUT on LOW peaks at
about 4 V where the tank resonates.  Set SW1 so the peak is at the Larmor frequency.

### 5.4 Polarizing

Connect the polarizing supply (12 V; the V POL lamp, LED3, lights) and set MODE to
RUN, POLARIZE TIME to about 3 s, LISTEN TIME to about 2 s.  With a x10 probe:

| loop | expect |
|---|---|
| V POL | the supply |
| I POL | 0.1 V per amp: 0.15 V at 1.5 A (13 V into the coil above) |
| DRAIN | about 0.2 V while polarizing; at switch-off it peaks near 127 V for 0.4 ms (D7 clamps it), then rings down to 0 |

Then, on GAIN HIGH, triggered on SYNC OUT's falling edge: a few tens of milliseconds
of relay settling, then the free induction decay, a sine at the Larmor frequency
fading over a second or two, about 0.8 V at the start for a litre of water polarized
at 1.5 A.  If it is not there: check the coil's direction (east-west), the tuning
(CAL IN), and look for steel and mains nearby.

**Caution:** DRAIN, the coil and its cable reach about 130 V at every switch-off.  The
coil dissipates 20 W while it polarizes at 1.5 A; at a 50 % duty cycle it gets warm.
Keep the polarizing supply under 30 V and 3 A.

## 6. Probe loops

| loop | node |
|---|---|
| V POL | the polarizing supply, after the fuse |
| DRAIN | Q1's drain (pole B's NO contact) |
| I POL | the sense resistor: 0.1 V per amp |
| GATE | the switch's drive, before the 47 ohm |
| TANK+, TANK- | the tank, the preamplifier's two inputs |
| INA A, INA B | U1's and U2's outputs |
| PREAMP | U3: the tank x101 |
| HP1, HP | after the first and second high-pass stages |
| LP | after the low-pass |
| OUT | U7, before the 1k to the OUT jack |
| POL CMD, DELAY, HOLD, RELAY, TIMER, EXT | the sequencer (section 5.2) |
| +15V, -15V | the rails |
| GND (four) | ground, for the scope's clip |

## 7. Experiments

1. **Measure the Earth's field.**  Record the FID (a sound card at 48 kHz, or the
   scope's FFT) and find its frequency: B = f / 42.577 Hz/µT.  A good FID gives it to a
   fraction of a hertz, a few nanotesla: watch it drift through the day.
2. **T2\*.**  The envelope's decay time.  Bring a steel tool near the coil and watch the
   decay shorten: the field is no longer the same all through the bottle.
3. **T1.**  Vary POLARIZE TIME and plot the FID's starting amplitude against it: it
   grows as 1 - exp(-t/T1).  Tap water is about 2-3 s; a pinch of copper sulphate
   shortens it a lot.  For exact times, set SEQUENCE to EXT and drive POLARIZE IN from
   a signal generator or a computer (high, above 1.3 V, polarizes).
4. **Other samples.**  Oil, alcohol, vinegar: other T1s, other amplitudes (the
   proton density).
5. **The tank.**  Sweep CAL IN with the coil connected and plot OUT against frequency:
   the resonance, its width, the effect of each switch of SW1.

## 8. Limits

- The polarizing current is up to 3 A (the relay's contacts and F1); the supply up to
  30 V (D6 clamps above 33 V).
- The polarizing switch-off is the clamp's: about 130 V at 3 A, 162 V at most, against
  Q1's 200 V.
- The receiver saturates on HIGH for an FID above about 13 V at OUT, which a larger
  sample or a bigger coil could reach: use LOW.
