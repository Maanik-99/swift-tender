import subprocess
import sys
import time
import os

print("🚀 [STARTUP] Initializing Swift Tender Cloud System...")

# 1. Start the Mock Tender Web Portal
web_port = os.getenv("PORT", "5000")
print(f"🌐 Launching Mock Portal Web Server on port {web_port}...")
web_process = subprocess.Popen(
    [sys.executable, "-u", "mock_tender_server.py"],
    stdout=sys.stdout,
    stderr=sys.stderr
)

# Brief wait to ensure web server is bound
time.sleep(2)

# 2. Start the Always-on Scanner Daemon
print("🔍 Launching 24/7 Always-On Tender Scanner Daemon...")
scanner_process = subprocess.Popen(
    [sys.executable, "-u", "always_on_scanner.py"],
    stdout=sys.stdout,
    stderr=sys.stderr
)

try:
    # Keep master supervisor alive
    while True:
        if web_process.poll() is not None:
            print("⚠️ Web server exited, restarting...")
            web_process = subprocess.Popen([sys.executable, "-u", "mock_tender_server.py"])
        if scanner_process.poll() is not None:
            print("⚠️ Scanner exited, restarting...")
            scanner_process = subprocess.Popen([sys.executable, "-u", "always_on_scanner.py"])
        time.sleep(10)
except KeyboardInterrupt:
    print("🛑 Shutting down processes...")
    web_process.terminate()
    scanner_process.terminate()
