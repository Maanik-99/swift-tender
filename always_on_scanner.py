import time
import subprocess
import sys
import os

# প্রতি কত সেকেন্ড পর পর সব পোর্টাল চেক করবে (Render Environment Variable দিয়েও কন্ট্রোল করা যাবে)
INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "300"))  # Default 300s (5 minutes)

print(f"🔄 SWIFT Tender Always-On Daemon started.")
print(f"⏱️ Scanning banks & test portal every {INTERVAL_SECONDS} seconds ({round(INTERVAL_SECONDS/60, 1)} minutes)...")
print(f"Press Ctrl+C anytime to stop.\n")

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swift_tender_alert.py")

iteration = 1
while True:
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Starting scan #{iteration}...")
    try:
        process = subprocess.Popen(
            [sys.executable, "-u", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1
        )
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"  {line.rstrip()}")
        process.stdout.close()
        return_code = process.wait()

        stderr_output = process.stderr.read()
        if stderr_output:
            for line in stderr_output.strip().split("\n"):
                if "InsecureRequestWarning" not in line and line.strip():
                    print(f"  [ERROR] {line}")
    except Exception as e:
        print(f"Scan execution error: {e}")

    print(f"😴 Next scan in {INTERVAL_SECONDS} seconds...")
    iteration += 1
    time.sleep(INTERVAL_SECONDS)
