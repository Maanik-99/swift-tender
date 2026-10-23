# Free 24/7 Online Deployment Guide (Render.com)

This system is configured to run **both the 24/7 Swift Tender Scanner & the Interactive Mock Testing Portal** completely free on **Render.com**.

---

### Step 1: Push code to GitHub
If you haven't pushed your repo to GitHub yet:
1. Create a new repository on [GitHub](https://github.com/new) (Make it **Private** to protect your email info, though credentials should always go into environment variables).
2. Run these commands in your project terminal:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for 24/7 cloud deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

---

### Step 2: Deploy Free on Render.com
1. Go to [https://render.com](https://render.com) and Sign In (using your GitHub account).
2. Click **New +** &rarr; Select **Web Service**.
3. Choose **Build and deploy from a Git repository** &rarr; Select your tender repository.
4. Fill in the basic settings:
   - **Name:** `swift-tender-alert` (or any name you like)
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python start.py`
   - **Instance Type:** Select **Free** ($0/month)
5. Scroll down to **Environment Variables** and click **Add Environment Variable**:
   - `SENDER_EMAIL` = `your_gmail_address@gmail.com`
   - `SENDER_PASSWORD` = `your_16_character_app_password`
   - `RECEIVER_EMAIL` = `destination_alert_email@gmail.com`
   - `GEMINI_API_KEY` = `(Optional, if using Gemini AI)`
   - `PYTHONUNBUFFERED` = `1`
6. Click **Create Web Service**!

---

### How it Works Once Deployed:
1. **Public Web URL:** Render will give you a free live URL like `https://swift-tender-alert.onrender.com`.
   - Open that URL in any browser (laptop or phone) &rarr; You will see your **Mock Bank Portal UI**!
   - You can click **"Create & Publish Tender"** or insert a SWIFT audit tender from anywhere in the world.
2. **24/7 Background Scanner:**
   - In the same service, `always_on_scanner.py` runs non-stop every 30-60 seconds.
   - It scans both your live Mock Portal and all 65+ commercial bank portals.
   - Whenever you create a test tender or a real bank posts a new tender, an **instant English email alert** is fired directly to your inbox.
