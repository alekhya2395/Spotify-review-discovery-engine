"""Phase 3 synthesis orchestrator."""

from __future__ import annotations

from loguru import logger

from .config import settings
from .loader import load_insights
from .themes import build_theme_report, build_discovery_deep_dive
from .segments import build_segment_report
from .stats import compute_summary_stats
from .report import generate_report


def run_synthesis() -> None:
    """Execute the full synthesis pipeline."""
    settings.ensure_directories()
    logger.info("=== Phase 3: Synthesis ===")

    df = load_insights(settings.insights_csv_path)

    logger.info("Step 1/4: Computing summary statistics...")
    stats = compute_summary_stats(df)

    logger.info("Step 2/4: Building pain themes...")
    themes = build_theme_report(
        df,
        top_n=settings.top_n_themes,
        quotes_per_theme=settings.top_n_quotes,
    )

    logger.info("Step 3/4: Analyzing segments...")
    segments = build_segment_report(df)

    logger.info("Step 4/4: Discovery deep dive...")
    discovery = build_discovery_deep_dive(df)

    logger.info("Generating reports...")
    json_path, md_path = generate_report(
        stats=stats,
        themes=themes,
        segments=segments,
        discovery=discovery,
        output_dir=settings.synthesis_output_dir,
    )

    logger.info("=== Phase 3 Complete ===")
    logger.info("JSON report: {}", json_path)
    logger.info("Markdown report: {}", md_path)
    logger.info("")
    logger.info("Key findings:")
    logger.info("  Total insights: {:,}", stats["total_reviews_analyzed"])
    logger.info("  Discovery-related: {:,} ({}%)", stats["discovery_related_count"], stats["discovery_related_pct"])
    logger.info("  Top pain: {}", stats["top_pain_category"])
    logger.info("  Pain themes found: {}", len(themes))
    logger.info("  User segments analyzed: {}", len(segments))
