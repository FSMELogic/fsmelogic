# How I checked the room was not doing it

**Isolation protocol for the Open Lab experiment**
FSME Logic, Edmonton. July 2026. fsmelogic.ca/lab.html

---

## Why this document exists

The Open Lab measures how long a Raspberry Pi's hardware noise source takes to
respond. The obvious objection is that I am not measuring the silicon at all, I
am measuring the room: footsteps, radio, sound, heat, or software quietly
rewriting the output before I see it.

So I tested each of those separately and wrote down what I got. Every number
below is measured, not estimated. The apparatus is household junk, which I am
going to describe accurately rather than dress up, because a result that survives
a crude test is worth more than one that needs a clean room.

---

## The apparatus, honestly

Three nested layers, all of it from a kitchen:

- **Outer:** a microwave oven, unplugged at the wall, door shut, never switched
  on. A microwave door is built to keep radio waves in, which means it keeps them
  out. That is roughly forty dollars of RF shielding for free.
- **Middle:** ice packs for thermal mass, with a styrofoam block on top acting as
  a slow thermal filter, and a dish towel over that.
- **Inner:** a steel lunchbox lined with aluminium foil. The Pi and its battery
  sit on kitchen sponges inside it, with silica gel packets for humidity.

The Pi runs on a USB battery bank, not mains. Wi-Fi, Bluetooth, and HDMI off.

I went through three versions before this one. The first was just the board
wrapped in foil. The second was a cardboard box fully wrapped with a vent hole.
The third is the one described above.

---

## Test 1: vibration

**Why it matters.** The clock crystal is piezoelectric. Squeeze it and the
frequency moves. Footsteps and a desk fan are both enough, which I found out the
hard way when an early run had a fan pointed at it.

**What I did.** Put a phone running Phyphox next to the rig, then stomped and
jumped beside it. Recorded the accelerometer with the Pi unprotected, then again
with everything assembled. Not a calibrated shaker. Me, jumping.

**What I got.**

| | Unprotected | Inside the box |
|---|---|---|
| Peak impact | 12.82 m/s² | 0.81 m/s² |
| RMS noise floor | 1.40 m/s² | 0.08 m/s² |

**17.5x attenuation on the RMS floor.** The 0.08 residual is at or below what a
phone accelerometer can resolve, so the real isolation may be better than that
and I cannot tell from here.

---

## Test 2: radio

**Why it matters.** RF is the interference nobody sees.

**What I did.** Used GPS as the probe. GPS arrives at about -130 dBm, which makes
it one of the weakest signals in ordinary use and therefore a strict test: if GPS
gets through, everything does. Put a phone logging GPS inside the chamber for
sixty seconds and watched the satellite count.

**What I got.**

| | Satellites | Accuracy |
|---|---|---|
| Open air | 25 | 8.2 m |
| Inside | **-1 (no fix)** | none |
| Reopened | 21 immediately | 22.4 m |

**Total signal loss inside, instant recovery on opening.** That confirms the box
did it rather than the phone failing. Since 1.575 GHz is fully blocked, 2.4 GHz
Wi-Fi and Bluetooth are too. Cellular, which sits between 0.7 and 2.6 GHz,
measured 20 to 30 dB down rather than gone.

For scale: a certified EMC chamber does 60 to 100 dB. Mine does somewhere above
40. It is not lab equipment and I am not claiming it is.

---

## Test 3: sound

**Why it matters.** Same piezoelectric problem as vibration. Acoustic pressure
physically deforms the crystal.

**What I did.** Phyphox audio scope, and I clapped and yelled at it.

**What I got.** Baseline outside -15.7 dB, inside during the same noise -30.3 dB.
**14.6 dB attenuation**, about a 5x amplitude reduction.

The loudest thing in the whole recording was not the yelling. It was me touching
the box, at -4.8 dB. So the protocol says do not touch it once it starts, and
that is why.

---

## Test 4: heat

**Why it matters.** This is the one that would fool you. Crystal frequency drifts
with temperature, and a slow thermal ramp produces exactly the kind of long-memory
statistics the experiment is looking for. If the result tracked temperature, the
result would be temperature.

**What I did.** Logged CPU temperature alongside every single measurement, then
correlated the two.

**What I got.** Correlation of **0.0457**. Effectively zero. The signal is not
following the heat.

---

## Test 5: software

**Why it matters.** This is the one that invalidates everything if you miss it.
Linux ships daemons that "whiten" the hardware noise source, rewriting the output
to look more random. If one is running you are measuring the daemon.

**What I did.** Killed and removed `rngd`. Killed `cron` and `ModemManager` so
nothing schedules I/O mid-run. Disabled Wi-Fi, Bluetooth, HDMI, and the status
LEDs, the last of these because they sit near photodiodes. Audited startup
scripts for anything else that spawns.

`pi_lab.py` re-checks for both `rngd` and `haveged` on every run and refuses to
start if either is alive. You do not have to take my word for the setup because
the tool enforces it on your machine.

---

## The control that matters more than any of the above

All five tests are about removing interference. None of them prove the remaining
signal means anything. Two things in the measurement itself do that work:

**The matched pair.** Every iteration times the hardware source and a software
random number generator, in the same loop, on the same CPU, in the same thermal
state, microseconds apart. If both arms move together, it is the machine.

**The shuffle.** The analysis runs on the recorded series and on a shuffled copy
of that same series. Shuffling destroys the ordering and changes literally
nothing else: same values, same spread, same everything. If the real run and its
own shuffle agree, there was nothing there.

That second one is the important one. It means you do not have to trust my
shielding, my apparatus, or me. You have to trust a shuffle.

---

## What this does and does not establish

**Does:** the persistence seen in these readings is not coming from vibration,
radio, sound, thermal drift, or software whitening. Each was tested and each came
back clean.

**Does not:** tell you what it is. That is a different argument and this document
does not make it.

Run it yourself: **fsmelogic.ca/lab.html**
