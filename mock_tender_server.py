import http.server
import socketserver
import json
import os
import sys
import urllib.parse
from datetime import datetime

# Ensure proper UTF-8 stdout/stderr handling on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

PORT = 5000
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_tenders.json")

def load_tenders():
    if not os.path.exists(DATA_FILE):
        initial = [
            {
                "id": "1",
                "title": "Procurement of Core Banking Server Upgrade for Mock Bank",
                "bank": "Demo Commercial Bank PLC",
                "deadline": "2026-11-15",
                "link": "http://127.0.0.1:5000/tender/1",
                "description": "Supply and installation of enterprise database servers.",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2)
        return initial
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_tenders(tenders):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tenders, f, indent=2)

class MockBankTenderHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # 1. Clear endpoint
        if parsed.path == "/clear":
            save_tenders([])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        # 2. Individual tender page viewer
        if parsed.path.startswith("/tender/"):
            tid = parsed.path.replace("/tender/", "").strip()
            tenders = load_tenders()
            found = next((t for t in tenders if str(t.get("id")) == tid), None)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if found:
                resp = f"<html><body style='font-family:Arial;padding:30px;'><h2>{found.get('title')}</h2><p><b>Bank:</b> {found.get('bank')}</p><p><b>Deadline:</b> {found.get('deadline')}</p><p>{found.get('description')}</p><hr><a href='/'>&larr; Back to Portal</a></body></html>"
            else:
                resp = "<html><body><h2>Tender not found</h2><a href='/'>Back</a></body></html>"
            self.wfile.write(resp.encode("utf-8"))
            return

        # 3. API endpoint to get JSON
        if parsed.path == "/api/tenders":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            tenders = load_tenders()
            self.wfile.write(json.dumps(tenders).encode("utf-8"))
            return

        # 2. Main HTML Portal & Interactive Creator
        tenders = load_tenders()
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Procurement & Tender Portal (Testing Environment)</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; font-family: 'Inter', sans-serif; }}
        body {{ background: #f0f4f8; margin: 0; padding: 20px; color: #1e293b; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #0f172a, #1e3a8a); color: white; padding: 28px; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
        .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1.4fr; gap: 24px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        .card h2 {{ margin-top: 0; font-size: 18px; color: #0f172a; border-bottom: 2px solid #f1f5f9; padding-bottom: 12px; }}
        label {{ display: block; margin-bottom: 6px; font-weight: 600; font-size: 13px; color: #334155; }}
        input, textarea, select {{ width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }}
        input:focus, textarea:focus {{ outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.15); }}
        .btn {{ background: #2563eb; color: white; border: none; padding: 12px 18px; border-radius: 8px; font-weight: 600; cursor: pointer; width: 100%; font-size: 14px; transition: background 0.2s; }}
        .btn:hover {{ background: #1d4ed8; }}
        .quick-btn {{ background: #f1f5f9; color: #1e293b; border: 1px dashed #94a3b8; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; margin-right: 6px; margin-bottom: 8px; display: inline-block; }}
        .quick-btn:hover {{ background: #e2e8f0; }}
        .tender-item {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 12px; transition: transform 0.15s, box-shadow 0.15s; background: #ffffff; }}
        .tender-item:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .tender-title {{ font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }}
        .tender-meta {{ font-size: 12px; color: #64748b; margin-bottom: 8px; }}
        .tender-badge {{ background: #e0e7ff; color: #3730a3; padding: 3px 8px; border-radius: 4px; font-weight: 600; }}
        .tender-link {{ color: #2563eb; text-decoration: none; font-weight: 600; font-size: 13px; }}
        .tender-link:hover {{ text-decoration: underline; }}
        .status-pill {{ display: inline-block; width: 10px; height: 10px; background: #22c55e; border-radius: 50%; margin-right: 6px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>🏛️ Real-Time Bank Tender Test Environment</h1>
                    <p>Live mock portal for testing your automated SWIFT / Bank tender detection scanner.</p>
                </div>
                <div style="background: rgba(255,255,255,0.15); padding: 8px 16px; border-radius: 30px; font-size: 13px;">
                    <span class="status-pill"></span> Live at http://127.0.0.1:{PORT}
                </div>
            </div>
        </div>

        <div class="grid">
            <!-- Form Card -->
            <div class="card">
                <h2>➕ Publish a New Tender</h2>
                
                <div style="margin-bottom: 14px;">
                    <span style="font-size: 12px; font-weight: 600; color: #64748b; display: block; margin-bottom: 6px;">⚡ Quick Test Templates:</span>
                    <button class="quick-btn" style="border-color:#16a34a;color:#16a34a;background:#f0fdf4;" onclick="fillTemplate('swift_csp')">🟢 SWIFT CSP (Alerts Email)</button>
                    <button class="quick-btn" style="border-color:#16a34a;color:#16a34a;background:#f0fdf4;" onclick="fillTemplate('swift_cscf')">🟢 SWIFT CSCF (Alerts Email)</button>
                    <button class="quick-btn" style="border-color:#0284c7;color:#0284c7;background:#f0f9ff;" onclick="fillTemplate('related_is')">🔵 Related IS Audit (Alerts Email)</button>
                    <button class="quick-btn" style="border-color:#dc2626;color:#dc2626;background:#fef2f2;" onclick="fillTemplate('irrelevant')">🔴 Non-Related (Ignored/No Email)</button>
                </div>

                <form method="POST" action="/publish">
                    <label>Issuing Bank Name</label>
                    <input type="text" id="bank" name="bank" required value="Sonali Bank PLC">

                    <label>Tender / RFP Title</label>
                    <input type="text" id="title" name="title" required placeholder="e.g. Request for Proposal for SWIFT CSP Assessment">

                    <label>Closing / Submission Deadline</label>
                    <input type="date" id="deadline" name="deadline" value="2026-11-30">

                    <label>Short Description / Scope</label>
                    <textarea id="description" name="description" rows="3" placeholder="Enter tender scope or requirements..."></textarea>

                    <button type="submit" class="btn">🚀 Publish Tender Immediately</button>
                </form>
            </div>

            <!-- Published List Card -->
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f1f5f9; padding-bottom: 12px; margin-bottom: 16px;">
                    <h2 style="margin: 0; border: none; padding: 0;">📋 Active Tenders ({len(tenders)})</h2>
                    <a href="/clear" style="color: #ef4444; font-size: 12px; text-decoration: none; font-weight: 600;">Clear All</a>
                </div>

                <div id="tenders-list">
    """
        for t in reversed(tenders):
            html += f"""
                    <div class="tender-item">
                        <div class="tender-title">
                            <a class="tender-link" href="{t.get('link')}" target="_blank">{t.get('title')}</a>
                        </div>
                        <div class="tender-meta">
                            <span class="tender-badge">{t.get('bank')}</span> • Closes: <b>{t.get('deadline')}</b> • Posted: {t.get('created_at')}
                        </div>
                        <div style="font-size: 13px; color: #475569;">
                            {t.get('description')}
                        </div>
                    </div>
            """

        html += f"""
                </div>
            </div>
        </div>
    </div>

    <script>
        function fillTemplate(type) {{
            if (type === 'swift_csp') {{
                document.getElementById('bank').value = 'Dutch-Bangla Bank PLC';
                document.getElementById('title').value = 'Request for Proposal (RFP) for SWIFT Customer Security Programme (CSP) Assessment';
                document.getElementById('description').value = 'Inviting proposals from eligible audit and cybersecurity firms to perform the mandatory independent assessment for SWIFT CSP CSCF controls.';
            }} else if (type === 'swift_cscf') {{
                document.getElementById('bank').value = 'Bangladesh Bank';
                document.getElementById('title').value = 'Appointment of Certified Cybersecurity Firm for SWIFT CSCF Independent Security Assessment';
                document.getElementById('description').value = 'Central bank seeks independent cybersecurity assessors for comprehensive SWIFT CSCF audit and compliance verification.';
            }} else if (type === 'related_is') {{
                document.getElementById('bank').value = 'State Bank of India (SBI)';
                document.getElementById('title').value = 'RFP for Banking Information Security (IS) Audit and Vulnerability Assessment (VAPT)';
                document.getElementById('description').value = 'Comprehensive cybersecurity assessment, network penetration testing, and ISO 27001 compliance audit.';
            }} else if (type === 'irrelevant') {{
                document.getElementById('bank').value = 'Sonali Bank PLC';
                document.getElementById('title').value = 'Procurement of 500 Units Laser Printers and Office Paper Shredders';
                document.getElementById('description').value = 'Tender for the supply and maintenance of brand new office peripherals and stationery.';
            }}
        }}
    </script>
</body>
</html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/publish":
            length = int(self.headers.get('content-length', 0))
            post_data = self.rfile.read(length).decode('utf-8')
            fields = urllib.parse.parse_qs(post_data)

            tenders = load_tenders()
            new_id = str(len(tenders) + 1)
            bank = fields.get('bank', ['Test Bank'])[0]
            title = fields.get('title', ['Test Tender'])[0]
            deadline = fields.get('deadline', ['2026-12-31'])[0]
            description = fields.get('description', [''])[0]

            new_tender = {
                "id": new_id,
                "title": title,
                "bank": bank,
                "deadline": deadline,
                "link": f"http://127.0.0.1:{PORT}/tender/{new_id}",
                "description": description,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            tenders.append(new_tender)
            save_tenders(tenders)

            # Redirect back to home
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

    def do_GET_clear(self):
        if self.path == "/clear":
            save_tenders([])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MockBankTenderHandler) as httpd:
        print(f"🌍 Mock Tender Portal Server running at: http://127.0.0.1:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
