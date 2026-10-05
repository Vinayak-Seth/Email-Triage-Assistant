# Repository Structure and Working Guide

A map of this repository for new collaborators. Read it first, then follow the [Suggested reading order](#8-suggested-reading-order). Student details are in [README.md](README.md) and the full project write-up is in [Documentation.md](Documentation.md).

## 1. Folder structure

```
MUJ-DS-YOUR_REG_NO/
│
├── app.py                      # UI layer: Streamlit app (3 tabs, sidebar, results display, send controls)
├── triage.py                   # LLM layer: prompt building, Groq call, validation, batching, evaluation
├── mail_client.py              # Mail layer: read Gmail (IMAP) and send replies (SMTP). Optional, local only
│
├── prompts.yaml                # PROMPT FILE: system prompt, reply-override text, user template
├── config.yaml                 # CONFIG FILE: model settings, intent list, priorities, reply tones, data path
│
├── data/
│   └── sample_emails.json      # 15 hand-labelled sample emails (Sample inbox tab and evaluation)
│
├── .streamlit/
│   └── secrets.toml.example    # Template for Streamlit Cloud / local secrets (copy to secrets.toml)
│
├── .env.example                # Template for local environment variables (copy to .env)
├── .gitignore                  # Keeps .env, .venv, secrets.toml and caches out of Git
├── requirements.txt            # Python dependencies
├── README.md                   # Student details, overview, quick start
├── Documentation.md            # Full project documentation
└── Structure.md                # This file
```

Files you create locally and must **never commit**: `.env`, `.venv/`, `.streamlit/secrets.toml`.

| I want to know… | Open |
|---|---|
| Who made this, which batch, which program | `README.md` |
| What the project does, how to install and run it, how it was evaluated | `Documentation.md` |
| Where a file or function lives, how to change something | `Structure.md` (this file) |

## 2. Architecture in one picture

```
            ┌───────────────────────────── app.py (UI) ─────────────────────────────┐
            │  Sidebar: tone, signature name, API key                               │
            │  Tab 1 Sample inbox   Tab 2 Try your own email   Tab 3 Live Gmail*    │
            └───────┬──────────────────────────┬──────────────────────────┬─────────┘
                    │ emails                   │ emails                   │ fetch / send
                    ▼                          ▼                          ▼
        data/sample_emails.json         pasted text              mail_client.py (IMAP/SMTP)*
                    └──────────────┬───────────┘
                                   ▼
                      triage.py  (build prompt → Groq API → validate)
                           ▲                    │
         prompts.yaml + config.yaml             ▼
                                    dict per email: intent, priority, summary,
                                    action_items, needs_reply, reply_draft
                                                │
                                                ▼
                              app.py renders table, metrics, expanders, reply boxes

* Live Gmail tab and sending exist only when GMAIL_ADDRESS and GMAIL_APP_PASSWORD are set locally.
```

Dependency direction: `app.py` → `triage.py`, `mail_client.py`. `triage.py` and `mail_client.py` do not import each other, and neither imports Streamlit. This keeps the LLM logic testable without the UI.

## 3. What each file does

### `app.py` (UI)
| Name | Role |
|---|---|
| `get_api_key()` | Finds the Groq key: Streamlit secrets → `.env` / environment → sidebar input box |
| `show_result(res, key, email, allow_send)` | Draws one email's result: priority, intent, summary, action items, editable reply, optional send controls |
| `with_sender(res, sender)` | Replaces the `[Your name]` placeholder in a draft at display time (no API call) |
| `render_results(emails, results, prefix, show_eval, allow_send)` | Shared display for Sample and Live tabs: priority counts, sorted table, CSV download, accuracy, one expander per email |
| `send_controls(res, email, draft)` | Send button → confirmation → sends exactly the text in the draft box |
| `send_block_reason(res, to_addr, draft)` | Returns why sending is disabled (phishing, no-reply address, empty draft, unfilled name), or `""` |
| Tab blocks at the bottom | Tab 1 sample inbox, Tab 2 single email, Tab 3 Live Gmail (only if credentials exist) |

Session-state keys: `results` (sample inbox output), `single` (tab 2 output), `live_emails` and `live_cache` (tab 3; the cache is keyed by `(tone, force_reply)` so each tone is generated once), plus per-email `sent_*` and `confirm_*` flags for sending.

### `triage.py` (LLM logic)
| Name | Role |
|---|---|
| `CONFIG`, `PROMPTS`, `INTENTS`, `PRIORITIES` | Loaded once from `config.yaml` and `prompts.yaml` |
| `load_samples()` | Reads `data/sample_emails.json` |
| `build_messages(email, tone, sender, force_reply)` | Fills prompt templates and returns the chat messages sent to Groq |
| `triage_email(client, email, tone, sender, force_reply)` | One Groq call → validated dict. Retries on rate limits / bad JSON. Fails fast on 401/403/404 |
| `_validate(raw)` | Coerces every model field to a safe value (unknown intent → `other`, unknown priority → `normal`) |
| `triage_batch(...)` | Runs `triage_email` in parallel threads. A failed email returns `{"error": ...}` instead of crashing the batch |
| `evaluate(emails, results)` | Intent accuracy, priority accuracy, priority within one level, using `expected_*` labels |

### `mail_client.py` (Gmail, optional)
| Name | Role |
|---|---|
| `credentials()` | Reads `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` from the environment only |
| `fetch_recent(limit, unread_only)` | Read-only IMAP fetch, newest first. Returns `{reply_to, message_id, from, subject, body}` (body capped at 2,000 characters) |
| `send_reply(to_addr, subject, body, in_reply_to)` | Sends a plain-text reply over SMTP; keeps the Gmail thread via `In-Reply-To` |
| `_decode`, `_body`, `_clean` | Header decoding, text/HTML body extraction, whitespace cleanup |

## 4. Data contracts

**An email** (input, from JSON, pasted text or Gmail):
```json
{ "from": "Name <a@b.com>", "subject": "…", "body": "…",
  "expected_intent": "…", "expected_priority": "…",     // optional, sample data only
  "reply_to": "a@b.com", "message_id": "<…>" }          // Gmail only
```

**A triage result** (output of `triage_email`):
```json
{ "intent": "action_request", "priority": "urgent", "priority_reason": "…",
  "summary": "…", "action_items": ["…"], "needs_reply": true, "reply_draft": "…" }
```
On failure: `{"error": "message"}`. UI code must check for the `error` key first.

## 5. Configuration reference

| File | Key | Meaning |
|---|---|---|
| `config.yaml` | `llm.model` | Groq model ID |
| | `llm.reasoning_effort`, `temperature`, `max_tokens` | Model behaviour. Keep `max_tokens` generous: reasoning tokens count toward it |
| | `llm.max_retries`, `llm.workers` | Retry count and parallel requests |
| | `intents` | `name: definition` map. Injected into the prompt, so it is the single source of truth |
| | `priorities` | Ordered most → least urgent |
| | `reply.tones`, `reply.default_tone` | Sidebar choices |
| | `data.sample_emails` | Path to the sample JSON |
| `prompts.yaml` | `system` | Main prompt: intents, priority rubric, JSON schema, security rule, example |
| | `force_reply` | Appended when "Draft a reply for every email" is on |
| | `user` | Wraps the email in `<email>` tags |
| `.env` | `GROQ_API_KEY` | Local API key |
| | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | Enable the Live Gmail tab (local only) |

Prompt placeholders (`$intent_definitions`, `$tone`, `$sender`, `$from_addr`, `$subject`, `$body`) use Python's `string.Template`. Avoid a literal `$` in the prompt text; write `$$` if you need one.

## 6. Common changes

| I want to… | Change |
|---|---|
| Add or rename an intent | Edit `intents` in `config.yaml`. The prompt updates automatically. Update `expected_intent` labels in the sample data if needed |
| Change priority rules | Edit the rubric in `prompts.yaml` → `system` |
| Add a reply tone | Add it to `reply.tones` in `config.yaml` |
| Switch model | Change `llm.model` in `config.yaml` (check <https://console.groq.com/docs/models>) |
| Add sample emails | Append to `data/sample_emails.json` (`expected_*` fields optional, but needed for accuracy scoring) |
| Support another mail provider | Add a new fetch/send module with the same function shapes as `mail_client.py` and wire it in `app.py` |
| Add a field to the LLM output | Update the schema in `prompts.yaml`, `_validate()` in `triage.py`, and `show_result()` in `app.py` |

## 7. Design rules to keep

1. **Never trust model output.** Everything goes through `_validate()` before the UI sees it.
2. **Treat email text as untrusted data.** The prompt tells the model to ignore instructions inside emails. Do not weaken this.
3. **Keep the UI and logic separate.** No Streamlit imports in `triage.py` or `mail_client.py`.
4. **Prompts and settings live in YAML,** not in Python strings.
5. **Gmail features are local-only.** Never put Gmail credentials in Streamlit Cloud secrets: anyone with the app link could read the inbox.
6. **Sending needs human confirmation.** Keep the enable checkbox, the confirm step and `send_block_reason()` in place.
7. **Secrets never go in Git.** Check `git status` for `.env` before every commit.

## 8. Suggested reading order

1. `README.md`: who made this and what the project is.
2. `Documentation.md`: what the project does and how to run it.
3. `prompts.yaml` and `config.yaml`: what the model is asked to do.
4. `triage.py`: how a prompt becomes a validated result.
5. `data/sample_emails.json`: what the inputs and expected labels look like.
6. `app.py`: how results are shown. Start at the tab blocks at the bottom.
7. `mail_client.py`: only if you work on Gmail features.

## 9. Git workflow

1. **Plan in Issues.** Each task is a GitHub issue (for example Dataset Collection, Model Development, Testing, Documentation, Deployment) assigned to its owner.
2. **Branch per task.** Use names like `feature/unit-tests`, `fix/reply-signature` or `docs/screenshots`. Do not commit directly to `main` after setup.
3. **Small commits** with clear messages: `git commit -m "Add tests for _validate"`.
4. **Pull request.** Push the branch, open a PR, and write `Closes #<issue number>` in the description so the issue closes on merge.
5. **Review, then merge.** A reviewer reads the diff and approves; then merge and delete the branch.
6. **Sync:** `git checkout main` then `git pull` before starting the next task.
7. **Before every commit:** run `git status` and confirm `.env` is not listed.

## 10. Known limitations

- Accuracy is measured on 15 hand-written emails, which is a sanity check, not a benchmark.
- There are no automated tests yet. Adding unit tests for `_validate()`, `build_messages()` and `evaluate()` (all pure functions) is the easiest place to start.
- Live Gmail needs a personal `@gmail.com` account with an app password; Google Workspace accounts cannot create one.
- Groq model names change over time. A `model_not_found` (404) error means `llm.model` needs updating.