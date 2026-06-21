# ResumeIQ — AI Resume Analyzer

AI-powered resume analysis using Flask + Groq (LLaMA 3.3 70B). Upload your resume (PDF/DOCX/TXT), optionally paste a job description, and get instant ATS scoring, keyword gap analysis, bullet rewrites, and interview prep.

## Features

- ATS Score & Overall Score (0-100), computed via a deterministic weighted formula (keyword match + section completeness + formatting) with a small, bounded AI adjustment
- Job Description matching with % score
- Section detection & per-section scoring
- Missing keyword analysis
- Bullet point rewrite suggestions
- Grammar & language feedback
- Interview question generation (10 questions)
- Follow-up chat about your report (rewrite sections, ask for more questions, tailor for a role)
- PDF report export
- Analysis history saved to SQLite

## Tech Stack

- **Backend:** Python, Flask
- **AI:** Groq API (LLaMA 3.3 70B)
- **PDF Parsing:** pdfplumber
- **DOCX Parsing:** python-docx
- **PDF Export:** ReportLab
- **Storage:** SQLite
- **Deployment:** Render.com

## Local Setup

### 1. Open the folder in VS Code

### 2. Create virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set your Groq API key
Create a `.env` file in the project root:
```
GROQ_API_KEY=your_actual_key_here
```
Get a free key at https://console.groq.com

### 5. Run
```bash
python app.py
```

Visit: http://127.0.0.1:5000

## Deploy to Render (Free)

1. Push this repo to GitHub
2. Go to https://render.com -> New -> Web Service
3. Connect your GitHub repo (Render will auto-detect render.yaml)
4. Add environment variable: GROQ_API_KEY = your key
5. Deploy - you get a live public URL

## Project Structure

```
resumeiq/
├── app.py                  # Flask routes
├── utils/
│   ├── parser.py           # PDF/DOCX/TXT text extraction
│   ├── analyzer.py         # Groq AI analysis + scoring integration
│   ├── scoring.py          # Deterministic weighted ATS scoring formula
│   ├── chatbot.py          # Follow-up chat logic
│   ├── database.py         # SQLite persistence layer
│   └── pdf_export.py       # PDF report generation
├── templates/
│   ├── index.html          # Main analyzer UI
│   ├── chat.html           # Follow-up chat UI
│   └── landing.html        # Marketing landing page
├── static/
│   ├── css/style.css
│   └── js/main.js
├── requirements.txt
├── Procfile                 # For Render deployment
├── render.yaml               # Render blueprint config
└── .gitignore
```
