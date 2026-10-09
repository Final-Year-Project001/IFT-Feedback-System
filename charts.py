"""
charts.py
---------
All Plotly figure builders. Each function returns a `go.Figure` or `None`
(when there isn't enough data yet) so callers can just do:
    fig = make_rating_bar(df)
    if fig: st.plotly_chart(fig, use_container_width=True)
"""

import plotly.graph_objects as go

from config import CATEGORIES, PLOTLY_LAYOUT

# Plotly draws donut labels in the slice, and this app's slices are saturated
# mid-tone colours (#3b82f6, #f59e0b, …). The old `color="#f0f4ff"` gave a
# 1.4:1 contrast ratio on the blue slice — effectively invisible. The readable
# choice on saturated fills is near-black; the percent label is also bolded and
# given a light halo so it survives every palette colour in this module.
_SLICE_LABEL_FONT = dict(size=12, color="#0f172a", family="Sora, sans-serif")


def make_rating_bar(df, title="Ratings"):
    if df.empty:
        return None
    counts = df["rating"].value_counts().sort_index().reindex([1, 2, 3, 4, 5], fill_value=0)
    colors = ["#ef4444", "#f97316", "#f59e0b", "#22c55e", "#10b981"]
    try:
        # `cornerradius` on Bar traces needs plotly >= 5.19. On older installs
        # Plotly raises rather than ignoring it, so fall back to square bars
        # instead of losing the whole chart.
        bar = go.Bar(
            x=counts.index, y=counts.values,
            marker=dict(color=colors, line_width=0, cornerradius=6),
            hovertemplate="Rating %{x}: <b>%{y}</b><extra></extra>",
        )
    except (TypeError, ValueError):
        bar = go.Bar(
            x=counts.index, y=counts.values,
            marker=dict(color=colors, line_width=0),
            hovertemplate="Rating %{x}: <b>%{y}</b><extra></extra>",
        )
    fig = go.Figure(bar)
    fig.update_layout(title=title, xaxis_title="Rating", yaxis_title="Count", **PLOTLY_LAYOUT)
    return fig


def make_level_pie(df):
    if df.empty:
        return None
    counts = df["student_level"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.6,
        marker_colors=["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#64748b"][:len(counts)],
        textinfo="percent", textfont=_SLICE_LABEL_FONT, insidetextorientation="horizontal",
        hovertemplate="%{label}: <b>%{value}</b><extra></extra>",
    ))
    fig.update_layout(title="By Student Level", **PLOTLY_LAYOUT)
    return fig


def make_sentiment_pie(df):
    if df.empty:
        return None
    col = "effective_sentiment" if "effective_sentiment" in df.columns else "sentiment"
    counts = df[col].fillna("Neutral").value_counts()
    clr = {"Positive": "#10b981", "Neutral": "#f59e0b", "Negative": "#ef4444"}
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.6,
        marker_colors=[clr.get(label, "#64748b") for label in counts.index],
        textinfo="percent", textfont=_SLICE_LABEL_FONT, insidetextorientation="horizontal",
        hovertemplate="%{label}: <b>%{value}</b><extra></extra>",
    ))
    fig.update_layout(title="Sentiment Analysis", **PLOTLY_LAYOUT)
    return fig


def make_trend_bar(df, title="Rating Trend Over Time"):
    """Daily average rating, as bars.

    Was a smoothed line. A continuous spline implies a reading between every
    submission that nobody took — and on a few days with a single submission it
    drew a confident curve through one data point, which is the kind of chart
    that makes a dip look like a trend when it is one person's rating. Bars say
    only what was actually recorded, and a gap in the bars is visibly a gap.

    Days with no submissions are omitted rather than zero-filled: a zero bar
    would read as "every student rated this 0", which is a different claim from
    "nobody answered".
    """
    if df.empty or "timestamp" not in df.columns:
        return None
    try:
        df2 = df.copy()
        df2["date"] = df2["timestamp"].dt.date
        daily = df2.groupby("date").agg(
            avg=("rating", "mean"), n=("rating", "size")
        ).reset_index()
        daily = daily[daily["n"] > 0].sort_values("date")

        # Colour each bar by the band its average falls in, so the trend and the
        # verdict are read in one glance and cannot be read two different ways.
        #
        # The bounds are the engine's own constants, read rather than repeated.
        # Written out as literals they would look identical to a copy and stay
        # that way until somebody moves a band in `sentiment.py` and this chart
        # quietly colours the old bands forever.
        from sentiment import NEGATIVE_MAX, NEUTRAL, POSITIVE_MIN

        def band(value):
            if value <= NEGATIVE_MAX:
                return "#ef4444"
            if value < POSITIVE_MIN:
                return "#f59e0b"
            return "#10b981"

        colors = [band(v) for v in daily["avg"].round(2)]
        try:
            bar = go.Bar(
                x=daily["date"], y=daily["avg"].round(2),
                marker=dict(color=colors, line_width=0, cornerradius=6),
                customdata=daily["n"],
                hovertemplate="%{x}<br>Average <b>%{y:.2f}</b>/5"
                              "<br>%{customdata} submission(s)<extra></extra>",
            )
        except (TypeError, ValueError):
            # `cornerradius` needs plotly >= 5.19; on older builds Plotly raises
            # rather than ignoring it, so fall back to square bars.
            bar = go.Bar(
                x=daily["date"], y=daily["avg"].round(2),
                marker=dict(color=colors, line_width=0),
                customdata=daily["n"],
                hovertemplate="%{x}<br>Average <b>%{y:.2f}</b>/5"
                              "<br>%{customdata} submission(s)<extra></extra>",
            )
        fig = go.Figure(bar)
        fig.update_layout(
            title=title, yaxis_range=[0, 5.5],
            bargap=0.25,
            **PLOTLY_LAYOUT,
        )
        return fig
    except Exception:
        return None


def make_trend_line(df):
    """Retained name for the old chart. Now draws the same bars.

    Kept so any caller still importing this name keeps working; it is an alias
    rather than a second implementation, because two charts that were meant to
    show the same thing is how the line and bar versions would drift.
    """
    return make_trend_bar(df)


def make_category_radar(df):
    if df.empty:
        return None
    avgs = df.groupby("category")["rating"].mean().reindex(CATEGORIES).fillna(0)
    fig = go.Figure(go.Scatterpolar(
        r=avgs.values.tolist() + [avgs.values[0]],
        theta=avgs.index.tolist() + [avgs.index[0]],
        fill="toself", fillcolor="rgba(59,130,246,0.1)",
        line=dict(color="#3b82f6", width=2.5),
        marker=dict(size=7, color="#8b5cf6"),
        hovertemplate="%{theta}: <b>%{r:.2f}</b><extra></extra>",
    ))
    fig.update_layout(
        title="Category Overview",
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 5], gridcolor="#e2e8f0", color="#64748b"),
            angularaxis=dict(gridcolor="#e2e8f0", linecolor="#e2e8f0", color="#334155"),
        ),
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("xaxis", "yaxis")},
    )
    return fig
