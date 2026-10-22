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

# --- Target Bank & Mock Portals ---
BANK_PORTALS = [
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
    },
    {
        "name": "National e-GP Portal (Public Banks & Gov)",
        "url": "https://www.eprocure.gov.bd",
        "base_url": "https://www.eprocure.gov.bd",
        "is_mock": False
    },
    {
        "name": "Sonali Bank PLC",
        "url": "https://www.sonalibank.com.bd/tender.php",
        "base_url": "https://www.sonalibank.com.bd",
        "is_mock": False
    },
    {
        "name": "Islami Bank Bangladesh PLC",
        "url": "https://www.islamibankbd.com/tender-notice",
        "base_url": "https://www.islamibankbd.com",
        "is_mock": False
    },
    {
        "name": "Dutch-Bangla Bank PLC",
        "url": "https://www.dutchbanglabank.com/tender/tender.html",
        "base_url": "https://www.dutchbanglabank.com/tender/",
        "is_mock": False
    },
    {
        "name": "Prime Bank PLC",
        "url": "https://www.primebank.com.bd/tender",
        "base_url": "https://www.primebank.com.bd",
        "is_mock": False
    },
    {
        "name": "City Bank PLC",
        "url": "https://www.thecitybank.com/eoi",
        "base_url": "https://www.thecitybank.com",
        "is_mock": False
    },
    {
        "name": "BRAC Group e-Tender",
        "url": "https://tender.brac.net",
        "base_url": "https://tender.brac.net",
        "is_mock": False
    },
    {
        "name": "Social Islami Bank PLC (SIBL)",
        "url": "https://www.siblbd.com/about/tender",
        "base_url": "https://www.siblbd.com",
        "is_mock": False
    },
    {
        "name": "Reserve Bank of India (RBI)",
        "url": "https://www.rbi.org.in/Scripts/BS_ViewTenders.aspx",
        "base_url": "https://www.rbi.org.in",
        "is_mock": False
    },
    {
        "name": "State Bank of India (SBI)",
        "url": "https://sbi.co.in/web/sbi-in-the-news/procurement-news",
        "base_url": "https://sbi.co.in",
        "is_mock": False
    }
]

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

# --- Scraper Engine ---
def scrape_all_tenders():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    new_tenders = []

    for bank in BANK_PORTALS:
        bank_name = bank['name']
        url = bank['url']
        is_mock = bank.get('is_mock', False)

        try:
            res = requests.get(url, headers=headers, timeout=12, verify=False)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, 'html.parser')

            # 1. Local Mock Portal scraper
            if is_mock:
                for item in soup.find_all('div', class_='tender-item'):
                    a_elem = item.find('a', class_='tender-link')
                    if a_elem and a_elem.get('href'):
                        href = a_elem['href'].strip()
                        title = a_elem.get_text(strip=True)
                        desc_elem = item.find('div', style=lambda v: v and 'color: #475569' in v)
                        desc = desc_elem.get_text(strip=True) if desc_elem else ""

                        if not is_already_seen(href):
                            new_tenders.append({
                                'title': title,
                                'link': href,
                                'snippet': desc,
                                'source': bank_name,
                                'is_mock': True
                            })

            # 2. Bangladesh Bank scraper
            elif "bb.org.bd" in url:
                table = soup.find('table')
                if table:
                    for tr in table.find_all('tr')[1:]:
                        tds = [td.get_text(separator=' ', strip=True) for td in tr.find_all('td')]
                        if len(tds) >= 4 and 'no data available' not in tds[0].lower():
                            a_elem = tr.find('a', attrs={'pdf-link': True}) or tr.find('a', href=True)
                            pdf = a_elem.get('pdf-link') or a_elem.get('href') if a_elem else ""
                            if pdf and not is_already_seen(pdf):
                                new_tenders.append({
                                    'title': tds[3].replace('details...', '').strip(),
                                    'link': pdf,
                                    'snippet': f"Published: {tds[1]} | Closes: {tds[2]}",
                                    'source': bank_name,
                                    'is_mock': False
                                })

            # 3. Other bank portals (Search specifically for tenders, procurement, RFPs)
            else:
                seen_on_bank = set()
                # Scrape up to top 10 current notices per bank page
                for a in soup.find_all('a', href=True):
                    txt = a.get_text(separator=' ', strip=True)
                    href = a['href'].strip()
                    txt_lower = txt.lower()

                    is_notice = any(k in txt_lower for k in ['tender', 'rfp', 'eoi', 'quotation', 'procurement', 'notice', 'corrigendum'])
                    is_noise = any(n in txt_lower for n in ['home', 'login', 'about us', 'contact', 'career', 'privacy', 'terms', 'all rights', 'sitemap', 'faqs'])

                    if is_notice and not is_noise and len(txt) > 15:
                        if href and not href.startswith('#') and not href.startswith('javascript'):
                            clean_href = href.split('?')[0]
                            full = clean_href if clean_href.startswith('http') else bank['base_url'].rstrip('/') + '/' + clean_href.lstrip('/')
                            if full not in seen_on_bank:
                                seen_on_bank.add(full)
                                if not is_already_seen(full):
                                    new_tenders.append({
                                        'title': txt[:140],
                                        'link': full,
                                        'snippet': f"Active tender notice on {bank_name} procurement portal",
                                        'source': bank_name,
                                        'is_mock': False
                                    })
                                if len(seen_on_bank) >= 10:
                                    break

        except Exception as e:
            pass

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
    msg['Subject'] = f"🚨 নতুন টেন্ডার অ্যালার্ট: {len(tenders)}টি নতুন টেন্ডার প্রকাশিত হয়েছে! ({first_title}...)"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; background-color: #f8fafc; margin: 0; padding: 20px;">
        <div style="max-width: 850px; margin: 0 auto; background: #ffffff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e2e8f0;">
            
            <div style="background: linear-gradient(135deg, #0d47a1, #1e88e5); color: #ffffff; padding: 22px;">
                <h2 style="margin: 0; font-size: 22px;">⚡ নতুন টেন্ডার নোটিফিকেশন অ্যালার্ট</h2>
                <p style="margin: 6px 0 0 0; opacity: 0.95; font-size: 14px;">
                    পোর্টালে নতুন টেন্ডার প্রকাশিত হওয়ার সাথে সাথে স্বয়ংক্রিয়ভাবে প্রেরিত ({len(tenders)} টি নতুন টেন্ডার)
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
                                টেন্ডার দেখুন &rarr;
                            </a>
                        </td>
                    </tr>
        """
        # Save to CSV immediately so it's NEVER sent twice
        mark_as_seen(t['title'], t['link'], t['source'], score)

    html_content += """
                </table>

                <br>
                <div style="border-top: 1px solid #e2e8f0; padding-top: 14px; font-size: 12px; color: #64748b; text-align: center;">
                    এই ইমেইলটি SWIFT & Bank Tender Instant Alert Automation Engine থেকে স্বয়ংক্রিয়ভাবে পাঠানো হয়েছে।
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [email.strip() for email in RECEIVER_EMAIL.split(',')], msg.as_string())
        server.quit()
        print(f"🎉 [SUCCESS] ইমেইল অ্যালার্ট সফলভাবে {RECEIVER_EMAIL} এ পাঠানো হয়েছে!\n")
    except Exception as e:
        print(f"❌ [ERROR] Email sending failed: {e}\n")

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
            mark_as_seen(c['title'], c['link'], c['source'], eval_result.get('relevance_score', 0))

    if verified_tenders:
        send_instant_email(verified_tenders)

if __name__ == "__main__":
    run_scan_cycle()
