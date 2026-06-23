"""Streamlit PM dashboard — Phase 6 delivery layer."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.phase5_storage.config import settings as index_settings
from src.phase6_dashboard.charts import (
    priority_bar,
    segment_pain_heatmap,
    segment_stacked,
    severity_pie,
    source_sunburst,
    theme_bar,
    topic_size_bar,
    topic_trend_lines,
)
from src.phase6_dashboard.chat import ReviewChatbot
from src.phase6_dashboard.config import settings
from src.phase6_dashboard.data import DashboardData
from src.phase6_dashboard.export import build_markdown_digest, export_digest


st.set_page_config(
    page_title=settings.app_title,
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #121212; }
    [data-testid="stSidebar"] { background-color: #000000; }
    div[data-testid="metric-container"] {
        background-color: #181818;
        border: 1px solid #282828;
        padding: 12px 16px;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Connecting to index…")
def _load_data() -> DashboardData:
    if not index_settings.warehouse_path.exists():
        raise FileNotFoundError(
            f"Index not found at {index_settings.warehouse_path}. Run `python run_phase5.py` first."
        )
    return DashboardData()


def _render_card_detail(card: dict) -> None:
    st.subheader(card["title"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Priority", f"{card['priority_score']:.1f}")
    c2.metric("Severity", str(card["severity"]).upper())
    c3.metric("Reviews", int(card["supporting_review_count"]))
    c4.metric("Trend", str(card["trend"]))

    st.markdown(f"**Theme:** {card['theme']}  ·  **Topic ID:** {card['topic_id']}")
    st.markdown(card["narrative"])
    st.info(f"**Opportunity:** {card['suggested_opportunity']}")

    if card.get("segment_notes") and str(card["segment_notes"]).strip() not in ("", "nan"):
        st.markdown(f"**Segment notes:** {card['segment_notes']}")

    if card.get("top_unmet_needs"):
        st.markdown("**Unmet needs**")
        for need in card["top_unmet_needs"]:
            st.markdown(f"- {need}")

    if card.get("evidence_quotes"):
        st.markdown("**Evidence quotes**")
        for q in card["evidence_quotes"]:
            st.markdown(f"> {q}")


def page_overview(data: DashboardData) -> None:
    st.title("Overview")
    st.caption("Top pain points, themes, and corpus health at a glance.")

    stats = data.stats()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Raw reviews", f"{stats.get('raw_reviews', 0):,}")
    m2.metric("Enriched", f"{stats.get('reviews_enriched', 0):,}")
    m3.metric("Topics", stats.get("topics", 0))
    m4.metric("Insight cards", stats.get("insight_cards", 0))
    m5.metric("Vectors", f"{stats.get('vectors', 0):,}")

    cards = data.all_cards()
    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(priority_bar(cards, top_n=12), use_container_width=True)
    with right:
        st.plotly_chart(severity_pie(data.severity_distribution()), use_container_width=True)

    st.plotly_chart(theme_bar(data.theme_counts()), use_container_width=True)

    trending = data.top_trending_topics()
    if not trending.empty:
        st.subheader("Increasing trends")
        st.dataframe(trending, use_container_width=True, hide_index=True)


def page_insight_cards(data: DashboardData) -> None:
    st.title("Insight Cards")
    st.caption("PM-ready cards ranked by priority score.")

    f1, f2, f3 = st.columns(3)
    severity = f1.selectbox("Severity", ["All", "high", "medium", "low"])
    theme_q = f2.text_input("Theme contains")
    min_pri = f3.number_input("Min priority", min_value=0.0, max_value=100.0, value=0.0, step=1.0)

    cards = data.all_cards(limit=200)
    if severity != "All":
        cards = cards[cards["severity"].str.lower() == severity]
    if theme_q.strip():
        cards = cards[cards["theme"].str.contains(theme_q.strip(), case=False, na=False)]
    if min_pri > 0:
        cards = cards[cards["priority_score"] >= min_pri]

    st.dataframe(
        cards[
            [
                "insight_id",
                "priority_score",
                "severity",
                "trend",
                "supporting_review_count",
                "discovery_share_pct",
                "title",
                "theme",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    ids = cards["insight_id"].tolist()
    if ids:
        selected = st.selectbox("Inspect card", ids)
        card = data.card(selected)
        if card:
            st.divider()
            _render_card_detail(card)


def page_topics(data: DashboardData) -> None:
    st.title("Topic Explorer")
    st.caption("BERTopic clusters from Phase 3.")

    topics = data.topics()
    st.plotly_chart(topic_size_bar(topics, top_n=20), use_container_width=True)

    topic_labels = topics["label"].head(15).tolist()
    pick = st.selectbox("Cluster detail", topic_labels)
    row = topics[topics["label"] == pick].iloc[0]
    st.markdown(
        f"**Size:** {int(row['size'])} reviews  ·  "
        f"**Discovery share:** {row['discovery_share_pct']:.0f}%  ·  "
        f"**Top pain:** {row['top_pain_category']}"
    )

    reviews = data.filter_reviews(topic_id=int(row["topic_id"]), limit=25)
    if not reviews.empty:
        st.dataframe(
            reviews[["review_id", "source", "sentiment", "segment", "verbatim_quote"]],
            use_container_width=True,
            hide_index=True,
        )


def page_segments(data: DashboardData) -> None:
    st.title("Segment Explorer")
    st.caption("Compare pain and sentiment across user segments.")

    seg = data.segment_breakdown()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(segment_stacked(seg), use_container_width=True)
    with c2:
        st.plotly_chart(source_sunburst(data.source_breakdown()), use_container_width=True)

    pain = data.segment_by_pain()
    if not pain.empty:
        st.plotly_chart(segment_pain_heatmap(pain), use_container_width=True)

    st.dataframe(seg, use_container_width=True, hide_index=True)


def page_trends(data: DashboardData) -> None:
    st.title("Topic Trends")
    st.caption("Monthly review volume per cluster (where timestamps exist).")

    trends = data.topic_trends()
    if trends.empty:
        st.warning("No timestamp data available for trend charts.")
        return

    top_topics = (
        trends.groupby("topic_label")["reviews"]
        .sum()
        .sort_values(ascending=False)
        .head(12)
        .index.tolist()
    )
    selected = st.multiselect("Topics to plot", top_topics, default=top_topics[:5])
    st.plotly_chart(topic_trend_lines(trends, selected), use_container_width=True)


def page_search(data: DashboardData) -> None:
    st.title("Review Search")
    st.caption("Semantic search over indexed reviews with optional filters.")

    opts = data.filter_options()
    q = st.text_input("Search query", placeholder="e.g. discover weekly genre filter")
    c1, c2, c3, c4 = st.columns(4)
    k = c1.slider("Results", 5, 30, settings.default_search_k)
    source = c2.selectbox("Source", ["All"] + opts["sources"])
    sentiment = c3.selectbox("Sentiment", ["All"] + opts["sentiments"])
    discovery_only = c4.checkbox("Discovery-related only")

    mode = st.radio("Mode", ["Semantic search", "Structured filter"], horizontal=True)

    if mode == "Structured filter":
        seg = st.selectbox("Segment", ["All"] + opts["segments"])
        df = data.filter_reviews(
            source=None if source == "All" else source,
            sentiment=None if sentiment == "All" else sentiment,
            segment=None if seg == "All" else seg,
            discovery_only=discovery_only,
            limit=k,
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    if not q.strip():
        st.info("Enter a query to search.")
        return

    with st.spinner("Searching (first query loads the embedder ~60–90s)…"):
        hits = data.search(
            q.strip(),
            k=k,
            source=None if source == "All" else source,
            sentiment=None if sentiment == "All" else sentiment,
            discovery_only=discovery_only,
        )

    rows = []
    for i, hit in enumerate(hits, start=1):
        detail = hit.get("detail") or {}
        rows.append(
            {
                "#": i,
                "similarity": round(hit.get("similarity") or 0, 3),
                "source": detail.get("source", ""),
                "sentiment": detail.get("sentiment", ""),
                "topic": detail.get("topic_label", ""),
                "quote": (detail.get("verbatim_quote") or hit.get("document", ""))[:200],
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_chat(data: DashboardData) -> None:
    st.title("Ask the Reviews")
    st.caption("RAG chatbot — semantic retrieval + Groq synthesis.")

    if not settings.enable_chat:
        st.warning("Chat is disabled (PHASE6_ENABLE_CHAT=false).")
        return

    if not settings.groq_api_key:
        st.warning("Set GROQ_API_KEY in `.env` for LLM answers. Retrieval still works.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    bot = ReviewChatbot(data)
    question = st.chat_input("Ask about user pain, discovery, ads, pricing…")

    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            st.markdown(turn["question"])
        with st.chat_message("assistant"):
            st.markdown(turn["answer"])
            if turn.get("model_used"):
                st.caption(f"Model: {turn['model_used']} · {len(turn.get('hits', []))} reviews retrieved")

    if question:
        with st.spinner("Retrieving reviews and synthesizing…"):
            result = bot.ask(question)
        st.session_state.chat_history.append({"question": question, **result})
        st.rerun()


def page_export(data: DashboardData) -> None:
    st.title("Export Report")
    st.caption("One-click PM digest for Notion, Confluence, or email.")

    top_n = st.slider("Cards to include", 5, 53, 15)
    preview = build_markdown_digest(data, top_n=top_n)
    st.download_button(
        "Download Markdown",
        preview,
        file_name="spotify_insight_digest.md",
        mime="text/markdown",
    )

    if st.button("Save to data/exports/"):
        paths = export_digest(data, top_n=top_n)
        st.success(f"Saved {paths['markdown'].name} and {paths['json'].name}")


PAGES = {
    "Overview": page_overview,
    "Insight Cards": page_insight_cards,
    "Topics": page_topics,
    "Segments": page_segments,
    "Trends": page_trends,
    "Search": page_search,
    "Ask the Reviews": page_chat,
    "Export": page_export,
}


def main() -> None:
    st.sidebar.title("🎧 Review Discovery")
    st.sidebar.caption("Phase 6 · PM Dashboard")

    try:
        data = _load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.code("python run_phase5.py", language="bash")
        return

    page = st.sidebar.radio("Navigate", list(PAGES.keys()))
    st.sidebar.divider()
    st.sidebar.markdown(
        f"Index: `{index_settings.warehouse_path}`  \n"
        f"Cards: {data.stats().get('insight_cards', 0)}"
    )

    PAGES[page](data)


if __name__ == "__main__":
    main()
