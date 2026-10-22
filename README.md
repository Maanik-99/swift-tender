# SWIFT Security Assessment Tender Tracker

SWIFT Customer Security Programme (CSP) / CSCF Mandatory Security Assessment সংক্রান্ত RFP ও টেন্ডার স্বয়ংক্রিয়ভাবে ট্র্যাক এবং ইমেইলে অ্যালার্ট পাঠানোর সম্পূর্ণ অটোমেশন সিস্টেম।

## 📁 ফাইল স্ট্রাকচার

- [swift_tender_alert.py](file:///c:/Users/_/Desktop/swift%20tender/swift_tender_alert.py): মূল পাইথন স্ক্রিপ্ট (Google Custom Search, টার্গেটেড ব্যাংক ক্রলার, SQLite ডি-ডুপ্লিকেশন এবং SMTP ইমেইল সেন্ডার)।
- [.env.example](file:///c:/Users/_/Desktop/swift%20tender/.env.example): কনফিগারেশন ও ক্রেডেনশিয়াল টেমপ্লেট।
- [requirements.txt](file:///c:/Users/_/Desktop/swift%20tender/requirements.txt): ডিপেন্ডেন্সি তালিকা।
- [.github/workflows/checker.yml](file:///c:/Users/_/Desktop/swift%20tender/.github/workflows/checker.yml): প্রতি ৬ ঘণ্টা পর পর স্বয়ংক্রিয়ভাবে স্ক্রিপ্ট চালানোর GitHub Actions ক্রন ওয়ার্কফ্লো।

---

## 🛠️ সেটআপ নির্দেশিকা

### ১. ডিপেন্ডেন্সি ইনস্টল
```bash
pip install -r requirements.txt
```

### ২. কনফিগারেশন সেটআপ (.env তৈরি)
`.env.example` ফাইলটি কপি করে `.env` নামে সেভ করুন এবং আপনার তথ্যগুলো দিন:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_gmail_app_password
RECEIVER_EMAIL=your_receiving_email@company.com

# ঐচ্ছিক (Google Search API চালু করতে চাইলে)
GOOGLE_API_KEY=YOUR_API_KEY
GOOGLE_CSE_ID=YOUR_CSE_ID
```

> **টিপ (Gmail App Password):** Gmail-এ 2-Step Verification অন করে Google Account Settings > Security > App Passwords থেকে একটি ১৬ অক্ষরের পাসওয়ার্ড তৈরি করে `SENDER_PASSWORD`-এ বসান।

### ৩. স্ক্রিপ্টটি টেস্ট রান করুন
```bash
python swift_tender_alert.py
```

---

## 🏦 যুক্ত টার্গেট ব্যাংক ও পোর্টাল

বর্তমানে স্ক্রিপ্টটিতে বাংলাদেশ ও ভারতের প্রধান প্রধান কেন্দ্রীয় ও বাণিজ্যিক ব্যাংকগুলোর টেন্ডার পোর্টাল যুক্ত রয়েছে:
1. **Bangladesh Bank** (Procurement Notice / Tenders)
2. **Sonali Bank PLC**
3. **Janata Bank PLC**
4. **Agrani Bank PLC**
5. **Rupali Bank PLC**
6. **Reserve Bank of India (RBI)**
7. **State Bank of India (SBI)**

> আপনার প্রয়োজন অনুযায়ী [swift_tender_alert.py](file:///c:/Users/_/Desktop/swift%20tender/swift_tender_alert.py)-এর `TARGET_SITES` লিস্টে আরও প্রাইভেট ব্যাংক (যেমন: BRAC Bank, City Bank, Islami Bank, HDFC ইত্যাদি) যুক্ত করতে পারেন।
