"""Core triage logic: prompt building, Groq API call, output validation, batching, evaluation."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from string import Template

import yaml
from groq import APIError, RateLimitError

ROOT = Path(__file__).parent


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


CONFIG = _load_yaml("config.yaml")
PROMPTS = _load_yaml("prompts.yaml")
INTENTS: dict[str, str] = CONFIG["intents"]
PRIORITIES: list[str] = CONFIG["priorities"]


def load_samples() -> list[dict]:
    path = ROOT / CONFIG["data"]["sample_emails"]
    return json.loads(path.read_text(encoding="utf-8"))


def build_messages(email: dict, tone: str, sender: str, force_reply: bool = False) -> list[dict]:
    """Fill the prompt templates from prompts.yaml / config.yaml."""
    definitions = "\n".join(f"      * {name}: {desc}" for name, desc in INTENTS.items())
    system = Template(PROMPTS["system"]).safe_substitute(
        intent_definitions=definitions, tone=tone, sender=sender or "[Your name]"
    )
    if force_reply:
        system += "\n" + Template(PROMPTS["force_reply"]).safe_substitute(
            tone=tone, sender=sender or "[Your name]"
        )
    user = Template(PROMPTS["user"]).safe_substitute(
        from_addr=email.get("from", ""),
        subject=email.get("subject", ""),
        body=email.get("body", ""),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

def _validate(raw: dict) -> dict:
    """Never trust model output: coerce every field to a safe, known value."""
    intent = str(raw.get("intent", "")).strip().lower()
    priority = str(raw.get("priority", "")).strip().lower()
    items = raw.get("action_items")
    needs_reply = bool(raw.get("needs_reply"))
    return {
        "intent": intent if intent in INTENTS else "other",
        "priority": priority if priority in PRIORITIES else "normal",
        "priority_reason": str(raw.get("priority_reason", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
        "action_items": [str(i) for i in items] if isinstance(items, list) else [],
        "needs_reply": needs_reply,
        "reply_draft": str(raw.get("reply_draft", "")).strip() if needs_reply else "",
    }


def triage_email(client, email: dict, tone: str | None = None, sender: str = "", force_reply: bool = False) -> dict:
    """One Groq call per email -> validated dict. Retries on rate limits / bad JSON."""
    llm = CONFIG["llm"]
    tone = tone or CONFIG["reply"]["default_tone"]
    messages = build_messages(email, tone, sender, force_reply)
    last_err: Exception | None = None

    for attempt in range(llm["max_retries"]):
        try:
            resp = client.chat.completions.create(
                model=llm["model"],
                messages=messages,
                temperature=llm["temperature"],
                max_tokens=llm["max_tokens"],
                response_format={"type": "json_object"},
                extra_body={"reasoning_effort": llm["reasoning_effort"]},
            )
            result = _validate(json.loads(resp.choices[0].message.content))
            if sender:  # guarantee the signature even if the model leaves a placeholder
                result["reply_draft"] = result["reply_draft"].replace("[Your name]", sender)
            return result
        except RateLimitError as err:
            last_err = err
            time.sleep(2 * 2**attempt)  # 2s, 4s, 8s
        except (APIError, ValueError) as err:  # ValueError covers JSONDecodeError
            last_err = err
            if getattr(err, "status_code", None) in (401, 403, 404):
                break  # bad key / unknown model: retrying cannot help
            time.sleep(1)
    raise RuntimeError(f"Triage failed: {last_err}")


def triage_batch(client, emails: list[dict], tone: str | None = None, sender: str = "", force_reply: bool = False) -> list[dict]:
    """Triage many emails in parallel. A failed email returns {'error': ...} instead of crashing the batch."""

    def run(email: dict) -> dict:
        try:
            return triage_email(client, email, tone, sender, force_reply)
        except RuntimeError as err:
            return {"error": str(err)}

    with ThreadPoolExecutor(max_workers=CONFIG["llm"]["workers"]) as pool:
        return list(pool.map(run, emails))


def evaluate(emails: list[dict], results: list[dict]) -> dict:
    """Compare predictions with the expected_* labels in the sample data."""
    pairs = [
        (e, r) for e, r in zip(emails, results)
        if "error" not in r and e.get("expected_intent") and e.get("expected_priority")
    ]
    if not pairs:
        return {}
    n = len(pairs)
    rank = PRIORITIES.index
    return {
        "n": n,
        "intent_acc": sum(e["expected_intent"] == r["intent"] for e, r in pairs) / n,
        "priority_acc": sum(e["expected_priority"] == r["priority"] for e, r in pairs) / n,
        "priority_within_one": sum(
            abs(rank(e["expected_priority"]) - rank(r["priority"])) <= 1 for e, r in pairs
        ) / n,
    }
