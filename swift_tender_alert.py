import os
import sys
import csv
import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Ensure proper UTF-8 stdout/stderr handling on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Configuration ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

CSV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenders.csv")
CSV_FIELDNAMES = ["link", "title", "source", "relevance_score", "found_date"]

# --- CSV Deduplication Engine ---
def get_seen_links():
    """Returns a set of all previously seen tender links from tenders.csv."""
    if not os.path.exists(CSV_FILE_PATH):
        return set()
    seen = set()
    try:
        with open(CSV_FILE_PATH, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and len(row) > 0:
                    link = row[0].strip()
                    if link and link != "link":
                        seen.add(link)
    except Exception as e:
        print(f"[ERROR] Error reading seen links from CSV: {e}")
    return seen

def is_already_seen(link):
    if not link:
        return False
    return link.strip() in get_seen_links()

def mark_as_seen(title, link, source="", relevance_score=0):
    if not link:
        return
    link = link.strip()
    if is_already_seen(link):
        return
    file_exists = os.path.exists(CSV_FILE_PATH) and os.path.getsize(CSV_FILE_PATH) > 0
    with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["link", "title", "source", "relevance_score", "found_date"])
        writer.writerow([
            link,
            title.strip(),
            source.strip(),
            relevance_score,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])

# --- Target Bank & Mock Portals Registry (Loaded from bank_portals.json) ---
PORTALS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank_portals.json")

def load_bank_portals():
    """Dynamically loads bank and tender portal registry from bank_portals.json."""
    if os.path.exists(PORTALS_JSON_PATH):
        try:
            with open(PORTALS_JSON_PATH, mode="r", encoding="utf-8") as f:
                data = json.load(f)
                banks = data.get("banks", [])
                portals = []
                for b in banks:
                    if b.get("status", "active") == "active":
                        is_mock_item = b.get("is_mock", False)
                        p_url = b.get("tender_url")
                        p_base = b.get("base_url")

                        # Cloud compatibility: if mock portal, allow dynamic port or external cloud URL
                        if is_mock_item:
                            cloud_mock_url = os.getenv("MOCK_PORTAL_URL")
                            port_env = os.getenv("PORT", "5000")
                            if cloud_mock_url:
                                p_url = cloud_mock_url.rstrip("/")
                                p_base = cloud_mock_url.rstrip("/")
                            elif "127.0.0.1" in str(p_url) or "localhost" in str(p_url):
                                p_url = f"http://127.0.0.1:{port_env}"
                                p_base = f"http://127.0.0.1:{port_env}"

                        portals.append({
                            "id": b.get("id"),
                            "name": b.get("name"),
                            "url": p_url,
                            "base_url": p_base,
                            "country": b.get("country"),
                            "category": b.get("category"),
                            "is_mock": is_mock_item
                        })
                if portals:
                    return portals
        except Exception as e:
            print(f"[WARN] Failed to read bank_portals.json, using built-in list: {e}")

    # Fallback to defaults
    return [
        {
            "name": "Local Mock Bank Portal (Live Testing Sandbox)",
            "url": "http://127.0.0.1:5000",
            "base_url": "http://127.0.0.1:5000",
            "is_mock": True
        },
        {
            "name": "Bangladesh Bank (Procurements Underway)",
            "url": "https://www.bb.org.bd/en/index.php/about/tenders",
            "base_url": "https://www.bb.org.bd",
            "is_mock": False
        }
    ]

BANK_PORTALS = load_bank_portals()


# --- AI & Smart Keyword Engine ---
SWIFT_KEYWORDS = [
    'swift', 'csp', 'cscf', 'customer security programme', 'customer security program',
    'customer security controls', 'swift assessment', 'swift audit', 'swift environment'
]

RELATED_IS_AUDIT_KEYWORDS = [
    'is audit', 'information security audit', 'cyber security audit',
    'cybersecurity assessment', 'vulnerability assessment', 'penetration testing',
    'vapt', 'iso 27001', 'pci dss', 'soc2', 'security operation center'
]

IRRELEVANT_KEYWORDS = [
    'laser printer', 'paper shredder', 'furniture', 'toner', 'photocopier',
    'air conditioner', 'generator', 'stationery', 'cctv repair', 'sanitary',
    'cleaning', 'vehicle', 'car rental', 'building renovation'
]

def evaluate_tender_smart(title, snippet="", source="", is_mock=False):
    """
    Evaluates tender relevance strictly:
    - Matches SWIFT CSP/CSCF (Score 100)
    - Matches related Bank IS / Cyber Security Audits (Score 80-90)
    - Filters OUT unrelated non-relevant tenders (printers, stationery, building, general items)
    """
    full_text = f"{title} {snippet}".lower()

    # 1. Check explicit irrelevant items
    if any(irr in full_text for irr in IRRELEVANT_KEYWORDS):
        return {
            "is_relevant": False,
            "relevance_score": 10,
            "summary": snippet if snippet else title,
            "ai_reasoning": "Non-relevant tender (Hardware/General Maintenance)."
        }

    # 2. Check SWIFT CSP/CSCF Audit relevance (Top Priority - matches user RFQ)
    is_swift = any(k in full_text for k in SWIFT_KEYWORDS)
    if is_swift:
        return {
            "is_relevant": True,
            "relevance_score": 100,
            "summary": snippet if snippet else title,
            "ai_reasoning": "Direct Match: SWIFT CSP / CSCF Security Assessment & Audit."
        }

    # 3. Check closely related IS / Cybersecurity Bank Audits
    is_related_audit = any(k in full_text for k in RELATED_IS_AUDIT_KEYWORDS)
    if is_related_audit:
        return {
            "is_relevant": True,
            "relevance_score": 85,
            "summary": snippet if snippet else title,
            "ai_reasoning": "Related Match: Banking Cyber Security & IS Audit."
        }

    # 4. Otherwise, it is not related to the requested SWIFT scope
    return {
        "is_relevant": False,
        "relevance_score": 30,
        "summary": snippet if snippet else title,
        "ai_reasoning": "Unrelated bank tender (Not related to SWIFT/Cybersecurity assessment)."
    }

# --- Scraper Engine (Direct Bank Portal & Full-Page Keyword Scanner) ---
def find_keyword_context(full_text, keyword, window=160):
    """Extracts a readable snippet around the matched keyword."""
    idx = full_text.lower().find(keyword.lower())
    if idx == -1:
        return f"Keyword '{keyword}' matched on tender portal."
    start = max(0, idx - 60)
    end = min(len(full_text), idx + window)
    snippet = full_text[start:end].replace('\n', ' ').strip()
    return f"...{snippet}..."

def scrape_all_tenders():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    new_tenders = []
    total_portals = len(BANK_PORTALS)
    print(f"📡 Scanning {total_portals} registered portals for SWIFT & Cyber Security tenders...")

    for idx, bank in enumerate(BANK_PORTALS, 1):
        bank_name = bank.get('name', 'Unknown Bank')
        tender_portal_url = bank.get('url', '')
        country = bank.get('country', '')
        is_mock = bank.get('is_mock', False)
        prefix = f"[{idx}/{total_portals}] {bank_name}"

        try:
            res = requests.get(tender_portal_url, headers=headers, timeout=5, verify=False)
            
            if res.status_code != 200:
                print(f"  🌐 {prefix} -> ⚠️ [HTTP {res.status_code}] ({tender_portal_url})", flush=True)
                continue

            soup = BeautifulSoup(res.text, 'html.parser')

            # 1. Local Mock Portal Sandbox (Test each newly added mock tender individually)
            if is_mock:
                mock_items = soup.find_all('div', class_='tender-item')
                found_in_mock = 0
                for item in mock_items:
                    a_elem = item.find('a', class_='tender-link')
                    if a_elem and a_elem.get('href'):
                        href = a_elem['href'].strip()
                        title = a_elem.get_text(strip=True)
                        desc_elem = item.find('div', style=lambda v: v and 'color: #475569' in v)
                        desc = desc_elem.get_text(strip=True) if desc_elem else ""

                        # If not already alerted for this specific mock tender
                        if not is_already_seen(href):
                            eval_res = evaluate_tender_smart(title, desc, bank_name, is_mock=True)
                            if eval_res.get('is_relevant'):
                                found_in_mock += 1
                                new_tenders.append({
                                    'title': title,
                                    'link': href,
                                    'dedup_key': href,
                                    'snippet': desc if desc else title,
                                    'source': f"{bank_name} ({country})",
                                    'relevance_score': eval_res.get('relevance_score', 100),
                                    'ai_summary': eval_res.get('summary', desc),
                                    'is_mock': True
                                })
                            else:
                                # Mark irrelevant mock items so they don't re-trigger
                                mark_as_seen(title, href, bank_name, eval_res.get('relevance_score', 0))

                if found_in_mock > 0:
                    print(f"  🌐 {prefix} -> 🎯 Found {found_in_mock} NEW relevant tender(s)!", flush=True)
                else:
                    print(f"  🌐 {prefix} -> 🔍 Checked {len(mock_items)} mock items (No new matching tenders)", flush=True)
                continue

            # 2. Live Bank Portals (Check whole page for desired SWIFT / Cyber keywords)
            # Extract clean page text
            for script_or_style in soup(['script', 'style', 'nav', 'footer']):
                script_or_style.decompose()

            page_text = soup.get_text(separator=' ', strip=True)
            page_text_lower = page_text.lower()

            # Check SWIFT top-priority keywords
            matched_keyword = None
            category = "SWIFT Security Audit"
            score = 100

            for kw in SWIFT_KEYWORDS:
                if kw in page_text_lower:
                    matched_keyword = kw
                    category = "SWIFT CSP / CSCF Assessment"
                    score = 100
                    break

            # Check related Cybersecurity & IS Audit keywords if not SWIFT
            if not matched_keyword:
                for kw in RELATED_IS_AUDIT_KEYWORDS:
                    if kw in page_text_lower:
                        matched_keyword = kw
                        category = "Cybersecurity & Bank IS Audit"
                        score = 85
                        break

            # If our desired keyword matched on this bank's portal
            if matched_keyword:
                context_snippet = find_keyword_context(page_text, matched_keyword)
                
                # Deduplication key is the tender_portal_url + keyword to avoid re-alerting unless new keyword
                dedup_key = f"{tender_portal_url}#{matched_keyword}"

                if not is_already_seen(dedup_key):
                    title = f"[{country}] {bank_name} - {category} (Matched: '{matched_keyword.upper()}')"
                    new_tenders.append({
                        'title': title,
                        'link': tender_portal_url,
                        'dedup_key': dedup_key,
                        'snippet': f"Matched Keyword: '{matched_keyword}'. Context: {context_snippet}",
                        'source': f"{bank_name} ({country})",
                        'relevance_score': score,
                        'ai_summary': f"Keyword '{matched_keyword}' found on portal. {context_snippet}",
                        'is_mock': is_mock
                    })
                    print(f"  🌐 {prefix} -> 🎯 MATCH FOUND: '{matched_keyword}' ({category})", flush=True)
                else:
                    print(f"  🌐 {prefix} -> ℹ️ Keyword '{matched_keyword}' present (already reported)", flush=True)
            else:
                print(f"  🌐 {prefix} -> ⚪ Checked (No matching SWIFT/Cyber tenders)", flush=True)

        except requests.exceptions.Timeout:
            print(f"  🌐 {prefix} -> ⏱️ Timeout (Site slow or down)", flush=True)
        except requests.exceptions.ConnectionError:
            print(f"  🌐 {prefix} -> ❌ Connection Failed (Unreachable)", flush=True)
        except Exception as e:
            print(f"  🌐 {prefix} -> ⚠️ Scan error: {e}", flush=True)

    return new_tenders

# --- Instant Email Sender ---
def send_instant_email(tenders):
    if not tenders:
        print("[STATUS] No new un-alerted tenders found.")
        return

    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("[WARNING] Email credentials not configured. Printing new tenders:")
        for t in tenders:
            print(f"- [{t['source']}] {t['title']} -> {t['link']}")
            mark_as_seen(t['title'], t['link'], t['source'], t.get('relevance_score', 0))
        return

    print(f"\n🚀 Sending INSTANT Email Alert for {len(tenders)} new tender(s) to: {RECEIVER_EMAIL}...")

    msg = MIMEMultipart()
    first_title = tenders[0]['title'][:40]
    msg['Subject'] = f"🚨 Tender Alert: {len(tenders)} New Tender Notice(s) Found! ({first_title}...)"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; background-color: #f8fafc; margin: 0; padding: 20px;">
        <div style="max-width: 850px; margin: 0 auto; background: #ffffff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e2e8f0;">
            
            <div style="background: linear-gradient(135deg, #0d47a1, #1e88e5); color: #ffffff; padding: 22px;">
                <h2 style="margin: 0; font-size: 22px;">⚡ New Tender Notification Alert</h2>
                <p style="margin: 6px 0 0 0; opacity: 0.95; font-size: 14px;">
                    Automated alert triggered for newly discovered tenders ({len(tenders)} new tender notice(s))
                </p>
            </div>

            <div style="padding: 24px;">
                <table border="0" cellpadding="10" cellspacing="0" style="width: 100%; border-collapse: collapse; font-size: 13px;">
    """

    for idx, t in enumerate(tenders, 1):
        bg = "#f8fafc" if idx % 2 == 0 else "#ffffff"
        score = t.get('relevance_score', 100)
        badge_color = "#16a34a" if score >= 80 else "#2563eb"

        html_content += f"""
                    <tr style="background-color: {bg}; border-bottom: 1px solid #e2e8f0;">
                        <td style="width: 75%; vertical-align: top;">
                            <span style="background-color: {badge_color}; color: white; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                                {t['source']}
                            </span>
                            <h4 style="margin: 8px 0 4px 0; color: #0f172a; font-size: 15px;">{t['title']}</h4>
                            <p style="margin: 0; color: #475569; font-size: 13px;">{t.get('ai_summary', t['snippet'])}</p>
                        </td>
                        <td style="width: 25%; text-align: right; vertical-align: middle;">
                            <a href="{t['link']}" target="_blank" style="background-color: #0d47a1; color: #ffffff; text-decoration: none; padding: 7px 12px; border-radius: 6px; font-size: 12px; font-weight: bold; display: inline-block;">
                                View Tender &rarr;
                            </a>
                        </td>
                    </tr>
        """

    html_content += """
                </table>

                <br>
                <div style="border-top: 1px solid #e2e8f0; padding-top: 14px; font-size: 12px; color: #64748b; text-align: center;">
                    This email was automatically generated and sent by the SWIFT & Banking Tender Alert Automation Engine.
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_content, 'html'))

    receiver_list = [email.strip() for email in RECEIVER_EMAIL.split(',') if email.strip()]
    sent = False

    # Method 1: Resend HTTP API (Recommended for Cloud / Render - No Port Blocking)
    if RESEND_API_KEY:
        try:
            print("  📨 Dispatching email via Resend HTTPS API...", flush=True)
            resend_url = "https://api.resend.com/emails"
            resend_headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            # Resend default free sender is "onboarding@resend.dev"
            sender_addr = "Swift Tender Alert <onboarding@resend.dev>" if ("@" not in SENDER_EMAIL or "gmail" in SENDER_EMAIL) else SENDER_EMAIL

            resend_payload = {
                "from": sender_addr,
                "to": receiver_list,
                "subject": msg['Subject'],
                "html": html_content
            }
            response = requests.post(resend_url, headers=resend_headers, json=resend_payload, timeout=15)
            if response.status_code in (200, 201):
                sent = True
                print(f"🎉 [SUCCESS] Email alert sent successfully via Resend API to {RECEIVER_EMAIL}!\n", flush=True)
            else:
                print(f"  ⚠️ Resend API responded with {response.status_code}: {response.text}", flush=True)
        except Exception as re_err:
            print(f"  ⚠️ Resend API failed: {re_err}. Falling back to standard SMTP...", flush=True)

    # Method 2: Standard TLS SMTP (Port 587)
    if not sent and SENDER_PASSWORD:
        try:
            print(f"  ✉️ Connecting to {SMTP_SERVER}:{SMTP_PORT} (TLS)...", flush=True)
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_list, msg.as_string())
            server.quit()
            sent = True
            print(f"🎉 [SUCCESS] Email alert sent successfully to {RECEIVER_EMAIL}!\n", flush=True)
        except Exception as e1:
            print(f"  ⚠️ TLS (Port {SMTP_PORT}) failed: {e1}. Retrying with SSL (Port 465)...", flush=True)

    # Method 3: Fallback to SSL (Port 465)
    if not sent and SENDER_PASSWORD:
        try:
            print(f"  ✉️ Connecting to {SMTP_SERVER}:465 (SSL)...", flush=True)
            server_ssl = smtplib.SMTP_SSL(SMTP_SERVER, 465, timeout=20)
            server_ssl.ehlo()
            server_ssl.login(SENDER_EMAIL, SENDER_PASSWORD)
            server_ssl.sendmail(SENDER_EMAIL, receiver_list, msg.as_string())
            server_ssl.quit()
            sent = True
            print(f"🎉 [SUCCESS] Email alert sent successfully via SSL to {RECEIVER_EMAIL}!\n", flush=True)
        except Exception as e2:
            print(f"❌ [ERROR] Email sending completely failed: {e2}\n", flush=True)

    # Mark as seen in CSV ONLY if email was successfully sent
    if sent:
        for t in tenders:
            dedup_ref = t.get('dedup_key', t['link'])
            mark_as_seen(t['title'], dedup_ref, t['source'], t.get('relevance_score', 100))

# --- Main Scan & Evaluate Pipeline ---
def run_scan_cycle():
    raw_candidates = scrape_all_tenders()
    if not raw_candidates:
        print("[STATUS] No new un-alerted tenders found across any bank.")
        return

    print(f"🔍 Found {len(raw_candidates)} newly discovered tender(s). Evaluating...")
    verified_tenders = []

    for c in raw_candidates:
        eval_result = evaluate_tender_smart(c['title'], c['snippet'], c['source'], c.get('is_mock', False))
        if eval_result.get('is_relevant', True):
            c['relevance_score'] = eval_result.get('relevance_score', 100)
            c['ai_summary'] = eval_result.get('summary', c['snippet'])
            verified_tenders.append(c)
        else:
            # Mark irrelevant notices in CSV so we don't re-crawl them
            dedup_ref = c.get('dedup_key', c['link'])
            mark_as_seen(c['title'], dedup_ref, c['source'], eval_result.get('relevance_score', 0))

    if verified_tenders:
        send_instant_email(verified_tenders)

if __name__ == "__main__":
    run_scan_cycle()
