"""Quick inspection: distributions + sample rows from insights.csv."""
import pandas as pd

df = pd.read_csv("data/processed/insights.csv")

print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}\n")

print("=== Sentiment ===")
print(df["sentiment"].value_counts().to_string())
print("\n=== Pain category ===")
print(df["pain_category"].value_counts().to_string())
print("\n=== Segment ===")
print(df["segment"].value_counts().to_string())
print("\n=== Discovery-related ===")
print(df["discovery_related"].value_counts().to_string())

print("\n=== 5 sample insights ===")
for _, r in df.head(5).iterrows():
    print(
        f"\nreview_id={r.review_id}  source={r.source}\n"
        f"  discovery_related={r.discovery_related}  pain={r.pain_category}  "
        f"sentiment={r.sentiment}  segment={r.segment}  conf={r.confidence}"
    )
    print(f"  unmet_need: {r.unmet_need}")
    quote = str(r.verbatim_quote)
    if len(quote) > 220:
        quote = quote[:220] + "..."
    print(f'  quote: "{quote}"')

print(f"\n=== Discovery-related rows only ===")
disc = df[df["discovery_related"] == True]
print(f"{len(disc)} of {len(df)} ({100*len(disc)/len(df):.0f}%) are discovery-related")
if len(disc) > 0:
    print("\nPain categories for discovery-related reviews:")
    print(disc["pain_category"].value_counts().to_string())
