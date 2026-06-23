"""Plotly chart builders for the Phase 6 dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = {
    "spotify_green": "#1DB954",
    "dark": "#121212",
    "card": "#181818",
    "text": "#FFFFFF",
    "muted": "#B3B3B3",
    "negative": "#E91429",
    "positive": "#1DB954",
    "neutral": "#535353",
    "high": "#E91429",
    "medium": "#F59B23",
    "low": "#1DB954",
}

PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor=COLORS["dark"],
        plot_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text"]),
        colorway=[COLORS["spotify_green"], "#509BF5", "#F59B23", "#E91429", "#B49BC8"],
    )
)


def _apply_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    fig.update_xaxes(gridcolor="#282828", zerolinecolor="#282828")
    fig.update_yaxes(gridcolor="#282828", zerolinecolor="#282828")
    return fig


def priority_bar(cards: pd.DataFrame, top_n: int = 15) -> go.Figure:
    df = cards.head(top_n).copy()
    df = df.sort_values("priority_score", ascending=True)
    colors = df["severity"].map(
        {"high": COLORS["high"], "medium": COLORS["medium"], "low": COLORS["low"]}
    ).fillna(COLORS["muted"])
    fig = go.Figure(
        go.Bar(
            x=df["priority_score"],
            y=df["title"].str.slice(0, 55),
            orientation="h",
            marker_color=colors,
            hovertext=df["insight_id"],
        )
    )
    fig.update_layout(
        title="Top insight cards by priority",
        xaxis_title="Priority score",
        height=max(400, top_n * 28),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return _apply_theme(fig)


def severity_pie(df: pd.DataFrame) -> go.Figure:
    color_map = {"high": COLORS["high"], "medium": COLORS["medium"], "low": COLORS["low"]}
    fig = px.pie(
        df,
        names="severity",
        values="count",
        color="severity",
        color_discrete_map=color_map,
        title="Cards by severity",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _apply_theme(fig)


def theme_bar(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        df,
        x="count",
        y="theme",
        orientation="h",
        title="Insight themes",
        labels={"count": "Cards", "theme": "Theme"},
    )
    fig.update_layout(height=max(350, len(df) * 24))
    return _apply_theme(fig)


def segment_stacked(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        df,
        x="segment",
        y=["negative", "positive"],
        title="Sentiment by user segment",
        labels={"value": "Reviews", "segment": "Segment", "variable": "Sentiment"},
        color_discrete_map={"negative": COLORS["negative"], "positive": COLORS["positive"]},
    )
    fig.update_layout(barmode="stack")
    return _apply_theme(fig)


def segment_pain_heatmap(df: pd.DataFrame) -> go.Figure:
    pivot = df.pivot_table(index="segment", columns="pain_category", values="reviews", fill_value=0)
    fig = px.imshow(
        pivot,
        labels=dict(x="Pain category", y="Segment", color="Reviews"),
        title="Pain categories by segment",
        aspect="auto",
        color_continuous_scale=[[0, COLORS["card"]], [0.5, "#509BF5"], [1, COLORS["spotify_green"]]],
    )
    return _apply_theme(fig)


def source_sunburst(df: pd.DataFrame) -> go.Figure:
    fig = px.sunburst(
        df,
        path=["source", "sentiment"],
        values="reviews",
        title="Reviews by source and sentiment",
    )
    return _apply_theme(fig)


def topic_size_bar(topics: pd.DataFrame, top_n: int = 20) -> go.Figure:
    df = topics.head(top_n).sort_values("size", ascending=True)
    fig = px.bar(
        df,
        x="size",
        y=df["label"].str.slice(0, 50),
        orientation="h",
        title=f"Top {top_n} topic clusters by size",
        labels={"size": "Reviews", "label": "Topic"},
        color="discovery_share_pct",
        color_continuous_scale=[[0, "#282828"], [1, COLORS["spotify_green"]]],
    )
    fig.update_layout(height=max(450, top_n * 26))
    return _apply_theme(fig)


def topic_trend_lines(df: pd.DataFrame, topic_labels: list[str]) -> go.Figure:
    subset = df[df["topic_label"].isin(topic_labels)].copy()
    if subset.empty:
        fig = go.Figure()
        fig.update_layout(title="No timestamp data for selected topics")
        return _apply_theme(fig)

    subset["month"] = pd.to_datetime(subset["month"])
    fig = px.line(
        subset,
        x="month",
        y="reviews",
        color="topic_label",
        markers=True,
        title="Topic volume over time",
        labels={"reviews": "Reviews", "month": "Month", "topic_label": "Topic"},
    )
    return _apply_theme(fig)
