import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Ensure proper UTF-8 stdout/stderr handling on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

BANK_PORTALS = [
    {
        "name": "Bangladesh Bank (Central Bank)",
        "url": "https://www.bb.org.bd/en/index.php/about/tenders",
        "base_url": "https://www.bb.org.bd",
        "type": "bb"
    },
    {
        "name": "National e-GP Portal (Public Banks & Gov)",
        "url": "https://www.eprocure.gov.bd",
        "base_url": "https://www.eprocure.gov.bd",
        "type": "standard"
    },
    {
        "name": "Sonali Bank PLC",
        "url": "https://www.sonalibank.com.bd/tender.php",
        "base_url": "https://www.sonalibank.com.bd",
        "type": "standard"
    },
    {
        "name": "Islami Bank Bangladesh PLC",
        "url": "https://www.islamibankbd.com/tender-notice",
        "base_url": "https://www.islamibankbd.com",
        "type": "standard"
    },
    {
        "name": "Dutch-Bangla Bank PLC",
        "url": "https://www.dutchbanglabank.com/tender/tender.html",
        "base_url": "https://www.dutchbanglabank.com/tender/",
        "type": "standard"
    },
    {
        "name": "Prime Bank PLC",
        "url": "https://www.primebank.com.bd/tender",
        "base_url": "https://www.primebank.com.bd",
        "type": "standard"
    },
    {
        "name": "City Bank PLC",
        "url": "https://www.thecitybank.com/eoi",
        "base_url": "https://www.thecitybank.com",
        "type": "standard"
    },
    {
        "name": "BRAC Group e-Tender",
        "url": "https://tender.brac.net",
        "base_url": "https://tender.brac.net",
        "type": "standard"
    },
    {
        "name": "Reserve Bank of India (RBI)",
        "url": "https://www.rbi.org.in/Scripts/BS_ViewTenders.aspx",
        "base_url": "https://www.rbi.org.in",
        "type": "standard"
    },
    {
        "name": "State Bank of India (SBI)",
        "url": "https://sbi.co.in/web/sbi-in-the-news/procurement-news",
        "base_url": "https://sbi.co.in",
        "type": "standard"
    }
]

def scrape_all_10_banks():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    bank_results = []
    total_tenders_found = 0

    print("🚀 ১০টি শীর্ষ ব্যাংকের টেন্ডার পোর্টাল স্ক্র্যাপ করা শুরু হচ্ছে...\n")

    for bank in BANK_PORTALS:
        print(f"📡 Scraping: {bank['name']}...")
        bank_tenders = []
        try:
            r = requests.get(bank['url'], headers=headers, verify=False, timeout=12)
            if r.status_code != 200:
                print(f"  -> HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, 'html.parser')

            # Special parser for Bangladesh Bank table with pdf-links
            if bank['type'] == 'bb':
                table = soup.find('table')
                if table:
                    for tr in table.find_all('tr')[1:]:
                        tds = [td.get_text(separator=' ', strip=True) for td in tr.find_all('td')]
                        if len(tds) >= 4:
                            a = tr.find('a', attrs={'pdf-link': True}) or tr.find('a', href=True)
                            pdf = a.get('pdf-link') or a.get('href') if a else bank['url']
                            bank_tenders.append({
                                'title': tds[3].replace('details...', '').strip(),
                                'link': pdf,
                                'date': f"Published: {tds[1]} | Closes: {tds[2]}"
                            })

            # General parser for other bank portals
            if not bank_tenders:
                seen_on_bank = set()
                # Check table rows first
                for tr in soup.find_all('tr'):
                    txt = tr.get_text(separator=' ', strip=True)
                    if len(txt) > 20 and not any(skip in txt.lower() for skip in ['login', 'register', 'home', 'privacy', 'copyright']):
                        a = tr.find('a', href=True)
                        if a:
                            href = a['href'].strip()
                            if href and not href.startswith('javascript') and not href.startswith('#'):
                                full = href if href.startswith('http') else bank['base_url'].rstrip('/') + '/' + href.lstrip('/')
                                if full not in seen_on_bank:
                                    seen_on_bank.add(full)
                                    bank_tenders.append({
                                        'title': txt[:140] + ('...' if len(txt) > 140 else ''),
                                        'link': full,
                                        'date': "Active Notice"
                                    })
                                    if len(bank_tenders) >= 15:
                                        break

                # If no table rows, scan relevant anchor tags
                if not bank_tenders:
                    for a in soup.find_all('a', href=True):
                        txt = a.get_text(separator=' ', strip=True)
                        href = a['href'].strip()
                        if len(txt) > 15 and href and not href.startswith('#') and not href.startswith('javascript'):
                            full = href if href.startswith('http') else bank['base_url'].rstrip('/') + '/' + href.lstrip('/')
                            if full not in seen_on_bank:
                                seen_on_bank.add(full)
                                bank_tenders.append({
                                    'title': txt[:140],
                                    'link': full,
                                    'date': "Active Notice"
                                })
                                if len(bank_tenders) >= 12:
                                    break

            print(f"  -> {len(bank_tenders)} টি টেন্ডার/নোটিশ সংগৃহীত হয়েছে।")
            bank_results.append({
                'bank_name': bank['name'],
                'portal_url': bank['url'],
                'tenders': bank_tenders
            })
            total_tenders_found += len(bank_tenders)

        except Exception as e:
            print(f"  -> Error: {e}")
            bank_results.append({
                'bank_name': bank['name'],
                'portal_url': bank['url'],
                'tenders': []
            })

    print(f"\n✅ সর্বমোট {total_tenders_found}টি টেন্ডার পাওয়া গেছে ১০টি ব্যাংক থেকে।")

    # Send Email
    send_summary_email(bank_results, total_tenders_found)

def send_summary_email(bank_results, total_count):
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("❌ Email credentials (.env) are missing.")
        return

    print(f"📧 Sending 10-Bank Tender Report to: {RECEIVER_EMAIL}...")

    msg = MIMEMultipart()
    msg['Subject'] = f"🏦 শীর্ষ ১০টি ব্যাংকের চলমান টেন্ডার ও প্রকিউরমেন্ট রিপোর্ট ({total_count} টি টেন্ডার সংগৃহীত)"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; background-color: #f4f6f9; margin: 0; padding: 20px;">
        <div style="max-width: 950px; margin: 0 auto; background: #ffffff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0d47a1, #1e88e5); color: #ffffff; padding: 25px;">
                <h2 style="margin: 0; font-size: 24px;">🏦 ১০টি শীর্ষ ব্যাংকের প্রকিউরমেন্ট ও টেন্ডার রিপোর্ট</h2>
                <p style="margin: 8px 0 0 0; font-size: 14px; opacity: 0.95;">
                    বাংলাদেশ ব্যাংক, সোনালী ব্যাংক, ইসলামী ব্যাংক, ডাচ-বাংলা, প্রাইম ব্যাংক, সিটি ব্যাংক, ব্র্যাক, জাতীয় ই-জিপি, আরআইবি ও এসবিআই পোর্টাল থেকে স্ক্র্যাপ করা টেন্ডার তালিকা।
                </p>
                <div style="margin-top: 15px; display: inline-block; background-color: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 13px;">
                    মোট সংগৃহীত টেন্ডার: {total_count} টি | ট্র্যাক করা ব্যাংক: ১০ টি
                </div>
            </div>

            <!-- Body -->
            <div style="padding: 25px;">
    """

    for b in bank_results:
        bank_name = b['bank_name']
        portal_url = b['portal_url']
        tenders = b['tenders']

        html_content += f"""
                <div style="margin-bottom: 30px; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden;">
                    <div style="background-color: #f8f9fa; padding: 12px 16px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="margin: 0; font-size: 16px; color: #0d47a1;">
                            🏛️ {bank_name} <span style="font-size: 12px; color: #666; font-weight: normal;">({len(tenders)} টি নোটিশ পাওয়া গেছে)</span>
                        </h3>
                        <a href="{portal_url}" target="_blank" style="font-size: 12px; color: #1976d2; text-decoration: none; font-weight: bold;">
                            অফিশিয়াল পোর্টাল ভিজিট করুন &rarr;
                        </a>
                    </div>
                    
                    <div style="padding: 12px 16px;">
        """

        if tenders:
            html_content += """
                        <table border="0" cellpadding="8" cellspacing="0" style="width: 100%; border-collapse: collapse; font-size: 13px;">
            """
            for idx, t in enumerate(tenders, 1):
                bg = "#fbfbfb" if idx % 2 == 0 else "#ffffff"
                html_content += f"""
                            <tr style="background-color: {bg}; border-bottom: 1px solid #f0f0f0;">
                                <td style="width: 4%; font-weight: bold; color: #555; vertical-align: top;">{idx}.</td>
                                <td style="width: 72%; vertical-align: top;">
                                    <b>{t['title']}</b><br>
                                    <small style="color: #777;">{t['date']}</small>
                                </td>
                                <td style="width: 24%; text-align: right; vertical-align: top;">
                                    <a href="{t['link']}" target="_blank" style="display: inline-block; background-color: #0d47a1; color: #ffffff; text-decoration: none; padding: 5px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                                        টেন্ডার দেখুন &rarr;
                                    </a>
                                </td>
                            </tr>
                """
            html_content += """
                        </table>
            """
        else:
            html_content += """
                        <p style="margin: 8px 0; color: #888; font-size: 13px; font-style: italic;">
                            এই মুহূর্তে সরাসরি এই পোর্টালে কোনো উন্মুক্ত পাবলিক টেন্ডার তালিকাভুক্ত নেই অথবা লগইন সুরক্ষিত।
                        </p>
            """

        html_content += """
                    </div>
                </div>
        """

    html_content += """
                <br>
                <div style="border-top: 1px solid #e0e0e0; padding-top: 15px; font-size: 12px; color: #777; text-align: center;">
                    এই সমন্বিত প্রতিবেদনটি SWIFT & Multi-Bank Tender Automation Engine থেকে স্বয়ংক্রিয়ভাবে প্রস্তুত ও প্রেরণ করা হয়েছে।
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
        print(f"🎉 SUCCESS: ১০টি ব্যাংকের সমন্বিত টেন্ডার রিপোর্ট সফলভাবে {RECEIVER_EMAIL} এ পাঠানো হয়েছে!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    scrape_all_10_banks()
