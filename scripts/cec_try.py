"""Try one HDMI-CEC command at a time and show what the bus says back.

For working out what this TV and Roku will honour before building on it. Every
step is a single short cec-client session; nothing here changes BobTV's settings.

    python3 scripts/cec_try.py who          # ask the bus which device is on screen
    python3 scripts/cec_try.py pause 4      # press Pause on the device at logical address 4
    python3 scripts/cec_try.py play 4       # press Play on it
    python3 scripts/cec_try.py take         # BobTV takes the screen (what the doorbell does)
    python3 scripts/cec_try.py inactive     # BobTV says it has nothing to show
    python3 scripts/cec_try.py stream 3.0.0.0   # ask to show the input at that address
"""
import re
import subprocess
import sys
import time

# CEC user-control codes (HDMI-CEC 1.4, table 27).
KEYS = {"pause": 0x46, "play": 0x44}


def session(lines, hold=3.0):
    """Send cec-client commands, keep listening for `hold` seconds, return its log."""
    process = subprocess.Popen(["cec-client", "-d", "8"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(2.5)  # let it open the adapter and claim an address
    for line in lines:
        process.stdin.write(line + "\n")
        process.stdin.flush()
        time.sleep(0.6)
    time.sleep(hold)
    process.stdin.write("q\n")
    process.stdin.flush()
    try:
        out, _ = process.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        out, _ = process.communicate()
    return out


def own_address(log):
    match = re.search(r"logical address\(es\) = .*?\((\d+)\)", log)
    return int(match[1]) if match else 1


def traffic(log):
    return [line.split("\t")[-1].strip() for line in log.splitlines() if "TRAFFIC" in line]


def report(log, note):
    frames = traffic(log)
    ours = own_address(log)
    print(f"BobTV's own CEC address this session: {ours}")
    interesting = [f for f in frames if not re.fullmatch(r"[<>]{2} [0-9a-f]{2}", f)]  # drop address polls
    print(f"{len(interesting)} messages on the bus ({note}):")
    for frame in interesting:
        print("  ", frame)
    errors = [line.strip() for line in log.splitlines() if "ERROR" in line]
    for line in errors[-3:]:
        print("   error:", line.split("\t")[-1])


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("who", "pause", "play", "take", "inactive", "stream"):
        print(__doc__)
        return 2
    step = sys.argv[1]
    if step == "who":
        # <Request Active Source>, broadcast. The device on screen must answer
        # <Active Source> (opcode 82) with its physical address.
        log = session(["tx 1F:85"], hold=3)
        report(log, "look for :82: from the device that is on screen")
        answers = [f for f in traffic(log) if re.search(r":82:([0-9a-f]{2}):([0-9a-f]{2})", f)]
        for frame in answers:
            a, b = re.search(r":82:([0-9a-f]{2}):([0-9a-f]{2})", frame).groups()
            phys = f"{int(a[0], 16)}.{int(a[1], 16)}.{int(b[0], 16)}.{int(b[1], 16)}"
            print(f"ON SCREEN: device {frame.split()[-1][0]} at {phys}")
        if not answers:
            print("ON SCREEN: nobody answered")
        return 0
    if step in KEYS:
        target = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        ours = 1
        code = KEYS[step]
        log = session([f"tx {ours:x}{target:x}:44:{code:02x}", f"tx {ours:x}{target:x}:45"], hold=2)
        report(log, f"{step} sent to device {target}")
        return 0
    if step == "take":
        log = session(["on 0", "as"], hold=5)
        report(log, "wake the TV and claim BobTV's input")
        return 0
    if step == "inactive":
        # <Inactive Source> to the TV, with BobTV's physical address 2.0.0.0.
        log = session(["tx 10:9d:20:00"], hold=4)
        report(log, "BobTV gives up the screen")
        return 0
    if step == "stream":
        parts = [int(p) for p in (sys.argv[2] if len(sys.argv) > 2 else "3.0.0.0").split(".")]
        a, b = f"{parts[0]:x}{parts[1]:x}", f"{parts[2]:x}{parts[3]:x}"
        # <Set Stream Path> is meant to come from the TV; the adapter may refuse it.
        log = session([f"tx 1F:86:{a}:{b}"], hold=4)
        report(log, f"ask for the input at {sys.argv[2] if len(sys.argv) > 2 else '3.0.0.0'}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
