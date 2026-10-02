"""Streamlit UI for the Email Triage Assistant."""
import imaplib
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

import mail_client
import triage

load_dotenv()
st.set_page_config(page_title="Email Triage Assistant", page_icon="📧", layout="wide")

BADGE = {"urgent": "🔴 urgent", "high": "🟠 high", "normal": "🟡 normal", "low": "🟢 low"}
PRIORITIES = triage.PRIORITIES


def get_api_key() -> str:
    """Streamlit secrets (deployed) -> .env / environment (local) -> sidebar input."""
    try:
        key = st.secrets["GROQ_API_KEY"]
    except Exception:
        key = os.getenv("GROQ_API_KEY", "")
    return key or st.sidebar.text_input("Groq API key", type="password")


def show_result(res: dict, key: str) -> None:
    if "error" in res:
        st.error(res["error"])
        return
    left, right = st.columns(2)
    left.markdown(f"**Priority:** {BADGE[res['priority']]}  \n*{res['priority_reason']}*")
    right.markdown(f"**Intent:** `{res['intent']}`")
    st.markdown(f"**Summary:** {res['summary']}")
    if res["action_items"]:
        st.markdown("**Action items**")
        for item in res["action_items"]:
            st.markdown(f"- {item}")
    if res["needs_reply"]:
        # key includes the draft text so a new draft is never hidden behind a stale widget
        st.text_area("Draft reply (editable)", res["reply_draft"], height=200,
                     key=f"reply_{key}_{abs(hash(res['reply_draft']))}")
    else:
        st.caption("No reply needed.")

def with_sender(res: dict, sender: str) -> dict:
    """Fill the signature at display time, so changing the name needs no new API call."""
    if sender and res.get("reply_draft"):
        return {**res, "reply_draft": res["reply_draft"].replace("[Your name]", sender)}
    return res

def render_results(emails: list[dict], results: list[dict], prefix: str, show_eval: bool) -> None:
    """Counts, sorted table, CSV, optional accuracy, and one expander per email."""
    rows = [{
        "Priority": res.get("priority", "error"),
        "Intent": res.get("intent", "-"),
        "From": e["from"],
        "Subject": e["subject"],
        "Summary": res.get("summary", res.get("error", "")),
        "Needs reply": res.get("needs_reply", False),
        "Reply draft": res.get("reply_draft", ""),
    } for e, res in zip(emails, results)]
    df = pd.DataFrame(rows)
    order = {p: i for i, p in enumerate(PRIORITIES)}
    df["_rank"] = df["Priority"].map(order).fillna(len(PRIORITIES))
    df = df.sort_values("_rank", kind="stable")
    sorted_idx = list(df.index)

    counts = df["Priority"].value_counts()
    for col, p in zip(st.columns(len(PRIORITIES)), PRIORITIES):
        col.metric(BADGE[p], int(counts.get(p, 0)))

    st.dataframe(df.drop(columns=["_rank", "Reply draft"]), hide_index=True)
    st.download_button("Download results (CSV)", df.drop(columns=["_rank"]).to_csv(index=False),
                       "triage_results.csv", "text/csv", key=f"dl_{prefix}")

    ev = triage.evaluate(emails, results) if show_eval else {}
    if ev:
        st.subheader("Accuracy vs. hand-labelled expectations")
        a, b, c = st.columns(3)
        a.metric("Intent exact match", f"{ev['intent_acc']:.0%}")
        b.metric("Priority exact match", f"{ev['priority_acc']:.0%}")
        c.metric("Priority within 1 level", f"{ev['priority_within_one']:.0%}")
        misses = [
            f"**{emails[i]['subject']}** — expected `{emails[i]['expected_intent']}` / "
            f"`{emails[i]['expected_priority']}`, got `{results[i].get('intent')}` / `{results[i].get('priority')}`"
            for i in sorted_idx
            if "error" not in results[i] and emails[i].get("expected_intent")
            and (emails[i]["expected_intent"] != results[i]["intent"]
                 or emails[i]["expected_priority"] != results[i]["priority"])
        ]
        if misses:
            with st.expander(f"Mismatches ({len(misses)})"):
                for m in misses:
                    st.markdown(f"- {m}")

    st.subheader("Emails, most urgent first")
    for i in sorted_idx:
        res = results[i]
        with st.expander(f"{BADGE.get(res.get('priority'), '⚠️ error')} · {emails[i]['subject']}"):
            st.caption(f"From: {emails[i]['from']}")
            st.text(emails[i]["body"])
            st.divider()
            show_result(res, f"{prefix}{i}")


# ---------- sidebar ----------
live_ready = all(mail_client.credentials())
with st.sidebar:
    st.header("Settings")
    tones = triage.CONFIG["reply"]["tones"]
    tone = st.selectbox("Reply tone", tones, index=tones.index(triage.CONFIG["reply"]["default_tone"]))
    sender = st.text_input("Sign replies as", placeholder="Your name")
    st.caption(f"Model: `{triage.CONFIG['llm']['model']}`")
    if not live_ready:
        st.caption("Live Gmail tab: add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to your local `.env`.")
    api_key = get_api_key()

st.title("📧 Email Triage Assistant")
st.caption("Intent classification · priority detection · reply drafting, powered by Groq.")

if not api_key:
    st.info("Add your Groq API key in the sidebar (or in `.env` / Streamlit secrets) to start.")
    st.stop()

client = Groq(api_key=api_key)
tab_names = ["📥 Sample inbox", "✍️ Try your own email"] + (["📬 Live Gmail"] if live_ready else [])
tabs = st.tabs(tab_names)

# ---------- tab 1: sample inbox ----------
with tabs[0]:
    samples = triage.load_samples()
    if st.button(f"Triage all {len(samples)} emails", type="primary"):
        with st.spinner("Triaging..."):
            st.session_state["results"] = triage.triage_batch(client, samples, tone, sender)
    if st.session_state.get("results"):
        render_results(samples, st.session_state["results"], "s", show_eval=True)

# ---------- tab 2: single email ----------
with tabs[1]:
    from_addr = st.text_input("From", placeholder="name@example.com")
    subject = st.text_input("Subject")
    body = st.text_area("Body", height=200)
    if st.button("Triage this email"):
        if not body.strip():
            st.warning("Paste an email body first.")
        else:
            with st.spinner("Triaging..."):
                try:
                    st.session_state["single"] = triage.triage_email(
                        client, {"from": from_addr, "subject": subject, "body": body}, tone, sender
                    )
                except RuntimeError as err:
                    st.session_state["single"] = {"error": str(err)}
    if "single" in st.session_state:
        show_result(st.session_state["single"], "single")

# ---------- tab 3: live Gmail (local only) ----------
if live_ready:
    with tabs[2]:
        st.caption("Read-only: nothing is sent, deleted, or marked as read. "
                   "Email text is sent to Groq for analysis.")
        c1, c2, c3 = st.columns(3)
        limit = c1.slider("How many recent emails", 5, 20, 10)
        unread_only = c2.checkbox("Unread only")
        force_reply = c3.checkbox("Draft a reply for every email", value=True,
                                  help="Off = the AI skips replies for newsletters and automated mail.")
        go, clear = st.columns([1, 6])
        if go.button("Fetch & triage", type="primary"):
            try:
                with st.spinner("Reading your inbox..."):
                    fetched = mail_client.fetch_recent(limit, unread_only)
                if not fetched:
                    st.info("No emails found.")
                else:
                    st.session_state["live_emails"] = fetched
                    st.session_state["live_cache"] = {}
            except (imaplib.IMAP4.error, OSError) as err:
                st.error(f"Could not read Gmail: {err}. Check the address and 16-character app password in .env.")
        if clear.button("Clear from screen"):
            st.session_state.pop("live_emails", None)
            st.session_state.pop("live_cache", None)
            st.rerun()

        live = st.session_state.get("live_emails")
        if live:
            cache = st.session_state["live_cache"]
            cache_key = (tone, force_reply)  # new tone / checkbox -> regenerate once, then reuse
            if cache_key not in cache:
                with st.spinner(f"Writing {tone} replies for {len(live)} emails..."):
                    cache[cache_key] = triage.triage_batch(client, live, tone, "", force_reply)
            results = [with_sender(r, sender) for r in cache[cache_key]]  # name updates instantly
            render_results(live, results, "live", show_eval=False)