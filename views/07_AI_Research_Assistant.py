import streamlit as st

from ai.assistant import SUPPORTED, answer
from components.context import sidebar
from components import theme

ctx = sidebar("assistant")
t, rows, obj = ctx["target"], ctx["rows"], ctx["objective"]

theme.header("Research Assistant", "Ask about the results. Answers come from the catalogue and computed scores, cite their datasets and say when data is missing.", "Workspace 07", "assistant")
theme.note("Retrieval-based fallback: no language model is configured, so answers are assembled from records and scores and cannot invent science. Set OPENAI_API_KEY and LLM_MODEL in .env to enable a model later.")

if "chat" not in st.session_state:
    st.session_state.chat = []

top = rows[0]["name"].split(" (")[0]
suggestions = [f"Why was {top} selected?", "Which sites suit rover testing?", "Which sites resemble the target terrain?",
               "What are the limitations of this analogue?", "Which sites have water or ice indicators?", "Which sites have lava tubes or caves?",
               "What data is missing?"]
cols = st.columns(4)
clicked = None
for i, s in enumerate(suggestions):
    if cols[i % 4].button(s, key=f"sug_{i}"):
        clicked = s

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["text"])
        if m.get("evidence"):
            with st.expander("Evidence (datasets recorded for the sites mentioned)"):
                for e in m["evidence"]:
                    st.markdown(f"- {e}")

q = st.chat_input("Ask about the ranked sites") or clicked
if q:
    st.session_state.chat.append({"role": "user", "text": q})
    res = answer(q, t, ctx["cand_list"], rows, obj)
    st.session_state.chat.append({"role": "assistant", "text": res["text"], "evidence": res["evidence"]})
    st.rerun()

st.caption("Supported topics: " + "; ".join(SUPPORTED) + f". Context: {obj} vs {t['name']}.")
