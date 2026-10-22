import time
import subprocess
import sys
import os

INTERVAL_SECONDS = 30  # প্রতি ৩০ সেকেন্ড পর পর সব পোর্টাল চেক করবে

print(f"🔄 SWIFT Tender Always-On Daemon started.")
print(f"⏱️ Scanning banks & test portal every {INTERVAL_SECONDS} seconds...")
print(f"Press Ctrl+C anytime to stop.\n")

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swift_tender_alert.py")

iteration = 1
while True:
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Starting scan #{iteration}...")
    try:
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, encoding='utf-8')
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                print(f"  {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if "InsecureRequestWarning" not in line:
                    print(f"  [ERROR] {line}")
    except Exception as e:
        print(f"Scan execution error: {e}")

    print(f"😴 Next scan in {INTERVAL_SECONDS} seconds...")
    iteration += 1
    time.sleep(INTERVAL_SECONDS)
