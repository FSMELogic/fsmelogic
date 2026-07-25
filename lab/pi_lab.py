#!/usr/bin/env python3
"""
FSME OPEN LAB - pi_lab.py

A reproducible hardware measurement you can run yourself.

WHAT IT DOES
  Times how long your machine's hardware noise source takes to respond, over
  and over, for a few hours. In the same loop it also times a software random
  number generator as a control. Same processor, same clock, same temperature,
  same moment.

  Then it looks for structure in both series, and in a shuffled copy of your
  own data. Shuffling destroys any memory in the ordering and changes nothing
  else, so if your real run and your shuffled run agree, there was nothing
  there.

WHAT IT DOES NOT DO
  It does not phone home. It does not upload anything. It writes files in the
  current directory and prints a result card. What you do with the card is
  entirely up to you.

REQUIREMENTS
  Python 3.8+ and nothing else. Standard library only, on purpose, so it runs
  on a freshly flashed Pi with the network switched off.

USAGE
  python3 pi_lab.py                 # default 2 hour run
  python3 pi_lab.py --hours 12      # longer is better
  python3 pi_lab.py --quick         # 60 seconds, to check it works
  python3 pi_lab.py --analyse f.csv # re-analyse a finished run

MIT licensed. fsmelogic.ca
"""

import argparse
import csv
import hashlib
import math
import os
import platform
import random
import subprocess
import sys
import time

VERSION = "1.0.0"
HWRNG = "/dev/hwrng"
READ_BYTES = 4

# Baselines. These are what each number looks like when there is nothing to see.
BASELINE = {
    "persistence": 0.50,
    "smoothing": -1.00,
    "compressibility": 1.00,
}


# ----------------------------------------------------------------------------
# PREFLIGHT
# ----------------------------------------------------------------------------

def _proc_running(name):
    try:
        r = subprocess.run(["pgrep", "-x", name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return None


def _read_first_line(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def preflight(strict=True):
    """Check the machine is in a fit state to measure. Returns a summary dict."""
    print("=" * 68)
    print("  FSME OPEN LAB  " + VERSION + "   preflight")
    print("=" * 68)

    checks = {}
    fatal = []

    # 1. Hardware noise source present and readable.
    ok = False
    if not os.path.exists(HWRNG):
        print("  [FAIL] no %s on this machine" % HWRNG)
        print("         this experiment needs a hardware noise source.")
        print("         most Raspberry Pi models have one. most laptops do not")
        print("         expose it this way.")
        fatal.append("no hardware noise source at %s" % HWRNG)
    else:
        try:
            with open(HWRNG, "rb") as f:
                f.read(READ_BYTES)
            ok = True
            print("  [ ok ] hardware noise source found at %s" % HWRNG)
        except PermissionError:
            print("  [FAIL] %s exists but this user cannot read it" % HWRNG)
            print("         fix, either one:")
            print("           sudo python3 %s ..." % os.path.basename(sys.argv[0]))
            print("           sudo chmod a+r %s      (until next reboot)" % HWRNG)
            fatal.append("cannot read %s, permission denied" % HWRNG)
        except Exception as e:
            print("  [FAIL] %s exists but cannot be read: %s" % (HWRNG, e))
            fatal.append("cannot read %s" % HWRNG)
    checks["hwrng"] = ok

    # 2. The whitening daemon must be dead. This is the critical one.
    rngd = _proc_running("rngd")
    if rngd is True:
        print("  [FAIL] rngd is running. it rewrites the raw output and you would")
        print("         be measuring the daemon, not the hardware.")
        print("         fix:  sudo pkill rngd     (and disable it, then reboot)")
        fatal.append("rngd running")
    elif rngd is False:
        print("  [ ok ] rngd is not running, raw output is intact")
    else:
        print("  [ ?? ] could not check for rngd, continuing anyway")
    checks["rngd_dead"] = (rngd is False)

    # 3. Radios off. Not fatal, but it matters and we record it.
    radios = []
    for iface in ("wlan0", "wlp2s0", "eth0"):
        st = _read_first_line("/sys/class/net/%s/operstate" % iface)
        if st == "up":
            radios.append(iface)
    if radios:
        print("  [warn] network interfaces still up: %s" % ", ".join(radios))
        print("         better results with the radios off and the lid closed")
    else:
        print("  [ ok ] no network interfaces reporting up")
    checks["radios_quiet"] = (len(radios) == 0)

    # 4. Somewhere to record temperature, so we can log the thermal history.
    t = read_temp()
    if t is not None:
        print("  [ ok ] temperature sensor readable, currently %.1f C" % t)
    else:
        print("  [warn] no temperature sensor found, thermal history will be blank")
    checks["temp"] = (t is not None)

    print("-" * 68)
    if fatal:
        print("  CANNOT RUN: " + "; ".join(fatal))
        print("=" * 68)
        if strict:
            sys.exit(1)
    else:
        print("  preflight passed. close the box and do not touch it again.")
        print("=" * 68)
    print()
    return checks


# ----------------------------------------------------------------------------
# SENSORS
# ----------------------------------------------------------------------------

def read_temp():
    v = _read_first_line("/sys/class/thermal/thermal_zone0/temp")
    if v is None:
        return None
    try:
        return int(v) / 1000.0
    except Exception:
        return None


def read_cpu_freq():
    v = _read_first_line("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    try:
        return int(v)
    except Exception:
        return 0


def time_hardware_read():
    """Nanoseconds taken to pull a few bytes from the hardware noise source."""
    t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    with open(HWRNG, "rb") as f:
        f.read(READ_BYTES)
    t1 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    return t1 - t0


def time_software_read():
    """The control. Same shape of work, no hardware source involved."""
    t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    random.random()
    t1 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    return t1 - t0


def burst_check():
    """Back to back reads. Separates a slow source from an empty buffer."""
    t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    with open(HWRNG, "rb") as f:
        f.read(READ_BYTES)
        f.read(READ_BYTES)
    t1 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    return t1 - t0


# ----------------------------------------------------------------------------
# COLLECTION
# ----------------------------------------------------------------------------

def collect(out_path, hours, interval):
    total_s = hours * 3600.0
    started = time.time()
    ends_at = started + total_s
    n = 0

    print("recording for %.2f hours, one pair every %.2f s" % (hours, interval))
    print("writing to %s" % out_path)
    print("leave it alone. ctrl-c stops early and keeps what it has.\n")

    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["elapsed_s", "hw_ns", "sw_ns", "burst_ns", "temp_c", "cpu_hz"])
        try:
            while time.time() < ends_at:
                loop_start = time.time()

                # Matched pair, taken as close together as we can manage.
                hw = time_hardware_read()
                sw = time_software_read()
                bc = burst_check()
                tc = read_temp()
                hz = read_cpu_freq()

                w.writerow([round(loop_start - started, 3), hw, sw, bc,
                            "" if tc is None else round(tc, 2), hz])
                n += 1

                if n % 200 == 0:
                    fh.flush()
                    left = (ends_at - time.time()) / 60.0
                    sys.stdout.write("\r  %d samples, %.0f min remaining   " % (n, max(0, left)))
                    sys.stdout.flush()

                slack = interval - (time.time() - loop_start)
                if slack > 0:
                    time.sleep(slack)
        except KeyboardInterrupt:
            print("\n  stopped early at %d samples, keeping the data" % n)

    print("\n  collected %d samples\n" % n)
    return n


# ----------------------------------------------------------------------------
# THE THREE NUMBERS
# All three are standard published time series statistics. Nothing proprietary
# happens in this file.
# ----------------------------------------------------------------------------

def _mean(xs):
    return sum(xs) / float(len(xs))


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(len(xs)))


def persistence(series):
    """
    Rescaled range analysis. Asks whether the past predicts the future.

      0.50  no memory, each step independent of the last
      >0.50 persistent, moves tend to be followed by moves the same way
      <0.50 anti-persistent, moves tend to reverse

    Standard method, described in any long-memory time series text.
    """
    n = len(series)
    if n < 128:
        return None

    sizes = []
    s = 16
    while s <= n // 4:
        sizes.append(s)
        s *= 2
    if len(sizes) < 3:
        return None

    xs, ys = [], []
    for size in sizes:
        rs_vals = []
        for start in range(0, n - size + 1, size):
            chunk = series[start:start + size]
            m = _mean(chunk)
            dev, cum = 0.0, []
            for v in chunk:
                dev += (v - m)
                cum.append(dev)
            r = max(cum) - min(cum)
            sd = _std(chunk)
            if sd > 0 and r > 0:
                rs_vals.append(r / sd)
        if rs_vals:
            xs.append(math.log(size))
            ys.append(math.log(_mean(rs_vals)))

    if len(xs) < 3:
        return None
    return _ols_slope(xs, ys)


def smoothing(series):
    """
    Variance scaling. Asks how fast the variation shrinks when you zoom out by
    averaging neighbouring samples together.

      -1.00  pure noise, variance halves every time you double the window
      >-1.00 the variation refuses to average away as fast as noise should
    """
    n = len(series)
    if n < 128:
        return None

    xs, ys = [], []
    k = 1
    while k <= n // 16:
        blocks = []
        for start in range(0, n - k + 1, k):
            chunk = series[start:start + k]
            if len(chunk) == k:
                blocks.append(_mean(chunk))
        if len(blocks) > 8:
            v = _std(blocks) ** 2
            if v > 0:
                xs.append(math.log(k))
                ys.append(math.log(v))
        k *= 2

    if len(xs) < 3:
        return None
    return _ols_slope(xs, ys)


def compressibility(series):
    """
    Lempel-Ziv complexity of the series turned into a bit string at its median.
    Asks how much repeating structure is hiding in the ordering.

      1.00  no structure found, as incompressible as random bits
      <1.00 structure present, the sequence repeats itself more than chance
    """
    n = len(series)
    if n < 128:
        return None

    med = sorted(series)[n // 2]
    bits = "".join("1" if v > med else "0" for v in series)

    # Lempel-Ziv 1976 phrase count.
    i, c, l = 0, 1, 1
    k, kmax = 1, 1
    while l + k <= len(bits):
        if bits[i + k - 1] == bits[l + k - 1]:
            k += 1
        else:
            kmax = max(kmax, k)
            i += 1
            if i == l:
                c += 1
                l += kmax
                i, k, kmax = 0, 1, 1
            else:
                k = 1
    if k != 1:
        c += 1

    norm = len(bits) / math.log(len(bits), 2)
    return c / norm if norm > 0 else None


def _ols_slope(xs, ys):
    n = float(len(xs))
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else None


def analyse(series):
    return {
        "persistence": persistence(series),
        "smoothing": smoothing(series),
        "compressibility": compressibility(series),
    }


# ----------------------------------------------------------------------------
# RESULT CARD
# ----------------------------------------------------------------------------

def _fmt(v):
    return "  n/a " if v is None else "%6.3f" % v


def _load(path):
    hw, sw, temps = [], [], []
    with open(path, "r") as fh:
        for row in csv.DictReader(fh):
            try:
                hw.append(float(row["hw_ns"]))
                sw.append(float(row["sw_ns"]))
            except Exception:
                continue
            if row.get("temp_c"):
                try:
                    temps.append(float(row["temp_c"]))
                except Exception:
                    pass
    return hw, sw, temps


def build_card(csv_path, checks=None, seed=None):
    hw, sw, temps = _load(csv_path)
    if len(hw) < 128:
        print("not enough samples to analyse (%d). run it for longer." % len(hw))
        return None

    shuffled = list(hw)
    rnd = random.Random(seed if seed is not None else 12345)
    rnd.shuffle(shuffled)

    rows = [
        ("YOUR DATA", analyse(hw)),
        ("SHUFFLED CONTROL", analyse(shuffled)),
        ("SOFTWARE CHANNEL", analyse(sw)),
    ]

    with open(csv_path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    L = []
    L.append("=" * 68)
    L.append("  FSME OPEN LAB - RESULT CARD          pi_lab " + VERSION)
    L.append("=" * 68)
    L.append("  Machine       : %s  %s" % (platform.machine(), platform.system()))
    L.append("  Model         : %s" % (_read_first_line("/proc/device-tree/model") or "unknown"))
    L.append("  Samples       : %d" % len(hw))
    if temps:
        L.append("  Temperature   : %.1f C to %.1f C over the run" % (min(temps), max(temps)))
    if checks:
        passed = sum(1 for v in checks.values() if v)
        L.append("  Preflight     : %d of %d checks passed" % (passed, len(checks)))
    L.append("")
    L.append("  %-18s %8s %10s %16s" % ("", "PERSIST", "SMOOTHING", "COMPRESSIBILITY"))
    for label, m in rows:
        L.append("  %-18s %8s %10s %16s" % (
            label, _fmt(m["persistence"]), _fmt(m["smoothing"]),
            _fmt(m["compressibility"])))
    L.append("")
    L.append("  %-18s %8.2f %10.2f %16.2f" % (
        "NOTHING-TO-SEE", BASELINE["persistence"], BASELINE["smoothing"],
        BASELINE["compressibility"]))
    L.append("")
    L.append("  Read it like this. If all three rows sit near the bottom line,")
    L.append("  your run found nothing, and that is a real result worth sending.")
    L.append("  If YOUR DATA sits away from the bottom line while SHUFFLED CONTROL")
    L.append("  and SOFTWARE CHANNEL sit on it, the difference is in the ordering")
    L.append("  of your own measurements.")
    L.append("")
    L.append("  Data file     : %s" % os.path.basename(csv_path))
    L.append("  Card ID       : %s" % digest[:16])
    L.append("=" * 68)

    card = "\n".join(L)
    print()
    print(card)
    print()

    card_path = os.path.splitext(csv_path)[0] + "_card.txt"
    with open(card_path, "w") as fh:
        fh.write(card + "\n")
    print("card saved to %s" % card_path)
    return card_path


# ----------------------------------------------------------------------------
# STRATUM HAND-OFF
# ----------------------------------------------------------------------------

def emit_stratum(csv_path, out_st="pi_lab_run.st", target=400):
    """
    Write a Stratum program with a decimated copy of the measurements baked in,
    so the FSME detector can be pointed at the same data.

    Stratum has no file reading capability by design, so the data travels as
    literals. This is generated code and is meant to be read, not edited.
    """
    hw, _, _ = _load(csv_path)
    if len(hw) < 128:
        print("not enough samples for the Stratum step")
        return None

    step = max(1, len(hw) // target)
    sample = hw[::step][:target]

    m = _mean(sample)
    scaled = [v / m * 1000.0 for v in sample] if m else sample

    L = []
    L.append("// generated by pi_lab %s from %s" % (VERSION, os.path.basename(csv_path)))
    L.append("// %d measurements, decimated from %d" % (len(scaled), len(hw)))
    L.append("// run:  stratum --grant console,entropic,self_heal,concurrency %s" % out_st)
    L.append("")
    L.append("module pi_lab_run;")
    L.append("")
    L.append("actor Series do")
    L.append("    state n: Int = 0;")
    L.append("    state fired: Bool = false;")
    L.append("")
    L.append("    handle Sample(v: Float) effects [entropic] do")
    L.append("        n = n + 1;")
    L.append("        monitor(v);")
    L.append("    end handle")
    L.append("")
    L.append("    privileged handle OnPhaseTransition(event: PhaseEvent) effects [console] do")
    L.append("        if fired == false do")
    L.append("            print(\"structural change detected at measurement\", n);")
    L.append("            print(\"  class:\", event.detection_class);")
    L.append("            print(\"  phase:\", event.phase);")
    L.append("            fired = true;")
    L.append("        end if")
    L.append("    end handle")
    L.append("end actor")
    L.append("")
    L.append("fn main() -> Unit effects [console, entropic, self_heal, concurrency] do")
    L.append("    print(\"feeding %d measurements through the detector\");" % len(scaled))
    L.append("    print(\"anything printed below is a structural change in your own data.\");")
    L.append("    print(\"no further output means your run was structurally steady.\");")
    L.append("    print(\"---\");")
    L.append("    let s = spawn Series;")
    for v in scaled:
        L.append("    s.Sample(%.4f);" % v)
    L.append("    ()")
    L.append("end fn")

    with open(out_st, "w") as fh:
        fh.write("\n".join(L) + "\n")

    print()
    print("Stratum program written to %s" % out_st)
    print("to run the same data through the detector:")
    print("    pip install stratum-lang")
    print("    stratum --grant console,entropic,self_heal,concurrency %s" % out_st)
    return out_st


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="FSME Open Lab. Measure your own hardware noise source.")
    ap.add_argument("--hours", type=float, default=2.0,
                    help="how long to record, default 2. longer is better")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="seconds between measurement pairs, default 1.0")
    ap.add_argument("--quick", action="store_true",
                    help="60 second run, to check everything works")
    ap.add_argument("--out", default=None, help="output csv name")
    ap.add_argument("--analyse", default=None,
                    help="skip recording, analyse an existing csv")
    ap.add_argument("--no-stratum", action="store_true",
                    help="skip writing the Stratum program")
    ap.add_argument("--force", action="store_true",
                    help="run even if preflight fails. results will be suspect")
    args = ap.parse_args()

    if args.analyse:
        card = build_card(args.analyse)
        if card and not args.no_stratum:
            emit_stratum(args.analyse)
        return

    hours = (60.0 / 3600.0) if args.quick else args.hours
    interval = 0.05 if args.quick else args.interval
    out = args.out or ("pi_lab_%s.csv" % time.strftime("%Y%m%d_%H%M"))

    checks = preflight(strict=not args.force)
    n = collect(out, hours, interval)
    if n < 128:
        print("only %d samples, too few to analyse. try a longer run." % n)
        return

    card = build_card(out, checks=checks)
    if card and not args.no_stratum:
        emit_stratum(out)

    print()
    print("Send your card to alex-kalyniuk@fsmelogic.ca and it goes on the")
    print("results page at fsmelogic.ca/lab.html, including if it found nothing.")


if __name__ == "__main__":
    main()
