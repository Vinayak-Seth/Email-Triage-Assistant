# 📧 Email Triage Assistant

NLP project: classifies email **intent**, detects **priority**, summarises, extracts **action items**, and drafts a **reply** using an LLM (Groq API) with a Streamlit UI.

## How the LLM is used
One Groq chat-completion call per email in JSON mode. The prompt (`prompts.yaml`) defines the intent taxonomy, a priority rubric, a prompt-injection guard, and the output schema. `triage.py` validates every field so a malformed response can never crash the app.

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit UI (sample inbox + custom email) |
| `mail_client.py` | Read-only Gmail IMAP fetcher (optional live tab, local only) |
| `triage.py` | Prompt building, Groq call, retries, validation, evaluation |
| `prompts.yaml` | Prompt file |
| `config.yaml` | Model, intents, priorities, tones |
| `data/sample_emails.json` | 15 labelled sample emails |
| `requirements.txt` | Dependencies |

## Run locally (Windows PowerShell)
```powershell
# 1. Get the code
git clone https://github.com/Vinayak-Seth/email-triage-assistant.git
cd email-triage-assistant

# 2. Create and activate a virtual environment (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
#   macOS / Linux:  python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your key
copy .env.example .env        # macOS / Linux: cp .env.example .env
#   then open .env and set GROQ_API_KEY=your_key

# 5. Run
streamlit run app.py
```

## Deploy on Streamlit Cloud
Push to GitHub -> share.streamlit.io -> New app -> select repo, branch `main`, file `app.py` -> Advanced settings -> Secrets:
```
GROQ_API_KEY = "your_key"
```

## Limitations
Accuracy is measured on 15 hand-labelled emails, a sanity check and not a benchmark. Priority is subjective, so the app also reports "within one level" accuracy.

## Live Gmail (optional, local only)
Add `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (a Google app password, needs 2-Step Verification on a personal @gmail.com account) to `.env`. A "Live Gmail" tab appears. It is read-only. Do not add these to Streamlit Cloud secrets: anyone with the app link could then read your inbox.
