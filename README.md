<<<<<<< HEAD
# 📧 Email Intelligence Dashboard

Automated Gmail → Gemini AI processing pipeline with a Streamlit dashboard.

## Features
- Polls Gmail every 60 seconds for new emails
- Processes emails from allowed senders only
- Extracts and explains technical terms using Gemini 2.5 Flash
- Dashboard to manage senders and view results

## Local Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your credentials
Place these files in the project folder:
- `credentials.json` (from Google Cloud Console)
- `token.json` (auto-generated on first run)
- `.env` file with:
```
GEMINI_API_KEY=AIzaSy...your-key-here
```

### 3. Run the dashboard
```bash
streamlit run app.py
```

### 4. Use the dashboard
- Click **▶ Start Pipeline** in the sidebar to begin polling Gmail
- Go to **Manage Senders** tab to add allowed email addresses
- Go to **Results** tab to view processed emails and Gemini analysis

## Deployment on Streamlit Cloud

1. Push this project to a GitHub repository (exclude `.env`, `token.json`, `credentials.json`)
2. Go to https://streamlit.io/cloud and connect your GitHub repo
3. Add secrets in Streamlit Cloud dashboard under **Settings → Secrets**:
```toml
GEMINI_API_KEY = "AIzaSy..."
```
4. Note: Gmail OAuth requires token.json which needs browser login — for cloud deployment, generate token.json locally first and add it as a secret.
=======
# email-intelligence-dashboard
Add the email addresses you want to monitor — suppliers, vendors, or clients. Whenever a new email arrives from those addresses, the dashboard automatically picks it up and displays it. If the email contains technical terms like equipment names, specifications, or industry standards, the system explains each one in simple language.
>>>>>>> 834231757fb6e8a708818303dd8da1278d1cf3f5
