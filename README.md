# 📧 Email Triage Assistant

Capstone project · Batch F · Repository `MUJ-DS-YOUR_REG_NO`

## 👤 Student details

| | |
|---|---|
| **Name** | Vinayak Seth |
| **Registration Number** | YOUR_REG_NO |
| **Branch** | Computer Science (Data Science) |
| **Batch** | F |
| **GitHub Username** | [@Vinayak-Seth](https://github.com/Vinayak-Seth) |
| **Training Program** | YOUR_PROGRAM_NAME |
| **Program Duration** | START_DATE – END_DATE |
| **Instructor** | INSTRUCTOR_NAME ([@INSTRUCTOR_GITHUB_USERNAME](https://github.com/INSTRUCTOR_GITHUB_USERNAME)) |
| **Project Title** | Email Triage Assistant: LLM-based intent classification, priority detection and reply drafting |

## 🚀 What it does

Reads an email and returns its **intent**, **priority**, a **summary**, **action items** and a **draft reply**, using an LLM through the Groq API. Built with Python and Streamlit, with a built-in accuracy check against hand-labelled emails.

| | |
|---|---|
| 🌐 Live demo | `https://YOUR-APP-NAME.streamlit.app` |
| 📄 Full documentation | [Documentation.md](Documentation.md) |
| 🗺️ File and code map | [Structure.md](Structure.md) |

## ⚡ Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then put your Groq key in .env
streamlit run app.py
```

Get a free key at <https://console.groq.com>. Never commit `.env`. Details, Live Gmail setup and deployment are in [Documentation.md](Documentation.md).

## 📁 Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI |
| `triage.py` | Prompt building, Groq call, validation, evaluation |
| `mail_client.py` | Optional Gmail read / send (local only) |
| `prompts.yaml` | Prompt file |
| `config.yaml` | Configuration file |
| `data/sample_emails.json` | 15 hand-labelled sample emails |
| `requirements.txt` | Dependencies |

## 🛠️ Workflow

Work is planned in GitHub **Issues** and merged into `main` through **pull requests** (branch → pull request → review → merge).

## 🤝 Contributions

Solo project. All work is mine: prompt design, LLM integration, Streamlit UI, testing, documentation and deployment.

## 📅 Weekly progress

| Week | Update | Link |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |