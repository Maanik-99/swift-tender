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

def scrape_and_email_bb_tenders():
    print(f"📡 Scraping all ongoing tenders from Bangladesh Bank portal...")
    url = "https://www.bb.org.bd/en/index.php/about/tenders"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        r = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')[1:] if table else []

        tenders = []
        for row in rows:
            cols = [c.get_text(separator=' ', strip=True) for c in row.find_all('td')]
            if len(cols) >= 4:
                a_elem = row.find('a', attrs={'pdf-link': True}) or row.find('a', href=True)
                pdf = a_elem.get('pdf-link') or a_elem.get('href') if a_elem else ''
                clean_title = cols[3].replace('details...', '').strip()
                tenders.append({
                    'sl': cols[0],
                    'publish_date': cols[1],
                    'closing_date': cols[2],
                    'title': clean_title,
                    'link': pdf
                })

        print(f"✅ Found {len(tenders)} active tenders on Bangladesh Bank portal.")

        if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
            print("❌ Email credentials missing in .env file.")
            return

        print(f"📧 Sending email from {SENDER_EMAIL} to {RECEIVER_EMAIL}...")

        msg = MIMEMultipart()
        msg['Subject'] = f"🏛️ বাংলাদেশ ব্যাংক (Bangladesh Bank) সকল চলমান টেন্ডার তালিকা ({len(tenders)} টি)"
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; margin: 0; padding: 20px; background-color: #f9f9f9;">
            <div style="max-width: 900px; margin: 0 auto; background: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;">
                <div style="background: linear-gradient(135deg, #0d47a1, #1976d2); color: white; padding: 24px; text-align: left;">
                    <h2 style="margin: 0; font-size: 22px;">🏛️ বাংলাদেশ ব্যাংক (Bangladesh Bank)</h2>
                    <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">সকল চলমান টেন্ডার ও প্রকিউরমেন্ট নোটিশের পূর্ণাঙ্গ তালিকা ({len(tenders)} টি সক্রিয় টেন্ডার)</p>
                </div>

                <div style="padding: 24px;">
                    <p style="font-size: 14px; color: #444;">
                        সরাসরি বাংলাদেশ ব্যাংকের অফিশিয়াল পোর্টাল (<a href="https://www.bb.org.bd/en/index.php/about/tenders" target="_blank" style="color: #1976d2; font-weight: bold;">bb.org.bd/about/tenders</a>) থেকে সংগৃহীত সমস্ত চলমান টেন্ডার নিচে উপস্থাপন করা হলো:
                    </p>

                    <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%; border-color: #e0e0e0; font-size: 13px;">
                        <thead>
                            <tr style="background-color: #0d47a1; color: #ffffff;">
                                <th style="width: 6%; text-align: center;">SL</th>
                                <th style="width: 14%; text-align: center;">প্রকাশের তারিখ</th>
                                <th style="width: 14%; text-align: center;">জমার শেষ তারিখ</th>
                                <th style="width: 50%;">টেন্ডার শিরোনাম</th>
                                <th style="width: 16%; text-align: center;">ডকুমেন্ট</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        for item in tenders:
            html_content += f"""
                            <tr>
                                <td style="text-align: center; font-weight: bold; background-color: #fafafa;">{item['sl']}</td>
                                <td style="text-align: center;">{item['publish_date']}</td>
                                <td style="text-align: center; color: #d32f2f; font-weight: bold;">{item['closing_date']}</td>
                                <td><b>{item['title']}</b></td>
                                <td style="text-align: center;">
                                    <a href="{item['link']}" target="_blank" style="background-color: #0d47a1; color: #ffffff; text-decoration: none; padding: 6px 10px; border-radius: 4px; display: inline-block; font-size: 12px; font-weight: bold;">
                                        PDF ডাউনলোড
                                    </a>
                                </td>
                            </tr>
            """

        html_content += """
                        </tbody>
                    </table>

                    <br>
                    <p style="font-size: 12px; color: #777; margin-top: 20px; border-top: 1px solid #eee; padding-top: 12px;">
                        এই ইমেইলটি SWIFT & Bank Tender Automation Engine থেকে বাংলাদেশ ব্যাংকের পোর্টাল স্ক্র্যাপ করে স্বয়ংক্রিয়ভাবে পাঠানো হয়েছে।
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [email.strip() for email in RECEIVER_EMAIL.split(',')], msg.as_string())
        server.quit()
        print(f"🎉 SUCCESS: বাংলাদেশ ব্যাংকের সকল {len(tenders)}টি টেন্ডারের তালিকা সফলভাবে {RECEIVER_EMAIL} এ পাঠানো হয়েছে!")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    scrape_and_email_bb_tenders()
