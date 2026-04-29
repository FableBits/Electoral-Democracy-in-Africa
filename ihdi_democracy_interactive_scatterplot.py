
"""
Interactive Scatterplot: Democracy Quality vs. Inequality-Adjusted HDI in Africa

This script creates an interactive scatterplot to examine the relationship between
the quality of democracy (using V-Dem data) and the Inequality-adjusted Human 
Development Index (Using United Nations Development Programme data) for African countries. 
The visualization helps explore how democratic institutions correlate with human 
development outcomes across the continent.
"""

# %%
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import plotly.express as px
import webbrowser
from sqlalchemy import create_engine, text
from getpass import getpass


# %%
# --- Database settings ---
user = "*********" 
password = getpass("MySQL password: ") 
database = "********" 

# Create SQLAlchemy engine for MySQL connection
engine = create_engine(f"mysql+pymysql://{user}:{password}@localhost/{database}")

# Test the database connection
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT '✅ Connection successful' AS status"))
        print(result.scalar())
except Exception as e:
    print(f"❌ Connection failed: {e}")


# --- Load data from database ---
query_hdi = "SELECT * FROM africa_ihdi_2023"  # Table with IHDI data

# %%

df_hdi = pd.read_sql(query_hdi, engine)

# %%

query_dem = "SELECT * FROM africa_dem_2023"  # Table with democracy data

# %%

df_dem = pd.read_sql(query_dem, engine)

# %%

# --- Country name harmonization for joining datasets ---
name_mapping = {
    "Democratic Republic of the Congo": "Democratic Republic of Congo",
    "Ivory Coast": "Côte d'Ivoire",
    "Republic of the Congo": "Congo",
    "The Gambia": "Gambia",
    "Cote d'Ivoire": "Côte d'Ivoire"
}

# %%

# Step 1: Normalize country names in both tables for reliable joining

import re
import unicodedata


def normalize_country_name(s: str) -> str:
    """Convert country names to a normalized form for joining."""
    if pd.isna(s):
        return s
    # Remove accents and convert to lowercase
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.strip().lower()
    # Clean up punctuation and whitespace
    s = s.replace("&", "and")
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[^a-z0-9\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Copy and harmonize country names
df_dem2 = df_dem.copy()
df_hdi2 = df_hdi.copy()
df_dem2["country_mapped"] = df_dem2["country_name"].replace(name_mapping)
df_hdi2["entity_mapped"]  = df_hdi2["Entity"].replace(name_mapping)
df_dem2["join_key"] = df_dem2["country_mapped"].map(normalize_country_name)
df_hdi2["join_key"] = df_hdi2["entity_mapped"].map(normalize_country_name)

# %%

# Step 2: Check for any country names that still don't match after normalization

dem_keys = set(df_dem2["join_key"].dropna().unique())
hdi_keys = set(df_hdi2["join_key"].dropna().unique())

dem_only = sorted(dem_keys - hdi_keys)
hdi_only = sorted(hdi_keys - dem_keys)

print("Count dem join_keys:", len(dem_keys))
print("Count hdi join_keys:", len(hdi_keys))
print("\nStill only in df_dem (after normalization):")
print(dem_only)

print("\nStill only in df_hdi (after normalization):")
print(hdi_only)

# %%

# Step: Create aligned name columns for both tables (for further checks)

# 1) Make copies so you don't overwrite your original tables
df_dem_aligned = df_dem.copy()
df_hdi_aligned = df_hdi.copy()

# 2) Apply the mapping to both sides
df_dem_aligned["country_aligned"] = df_dem_aligned["country_name"].replace(name_mapping)
df_hdi_aligned["entity_aligned"]  = df_hdi_aligned["Entity"].replace(name_mapping)

# 3) Check for any remaining mismatches
dem_only = sorted(set(df_dem_aligned["country_aligned"]) - set(df_hdi_aligned["entity_aligned"]))
hdi_only = sorted(set(df_hdi_aligned["entity_aligned"]) - set(df_dem_aligned["country_aligned"]))

print("Still only in df_dem (after mapping):", dem_only)
print("Still only in df_hdi (after mapping):", hdi_only)

# %%

# Step: Keep only countries that exist in both datasets (intersection)

# 1) Find common country names
common_countries = sorted(
    set(df_dem_aligned["country_aligned"]) & set(df_hdi_aligned["entity_aligned"])
)

print("Common countries count:", len(common_countries))

# 2) Filter both tables to only common countries
df_dem_common = df_dem_aligned[df_dem_aligned["country_aligned"].isin(common_countries)].copy()
df_hdi_common = df_hdi_aligned[df_hdi_aligned["entity_aligned"].isin(common_countries)].copy()

print("df_dem_common rows:", df_dem_common.shape)
print("df_hdi_common rows:", df_hdi_common.shape)

# 3) Sanity check: the set differences should now be empty
print("dem-only (should be empty):",
      sorted(set(df_dem_common["country_aligned"]) - set(df_hdi_common["entity_aligned"])))
print("hdi-only (should be empty):",
      sorted(set(df_hdi_common["entity_aligned"]) - set(df_dem_common["country_aligned"])))

# %%
dem_2023 = df_dem2[["join_key", "country_mapped", "elect_dem_ind"]].copy()
hdi_2023 = df_hdi2[["join_key", "entity_mapped", "Inequality-adjusted Human Development Index"]].copy()

# Rename IHDI column for easier handling
hdi_2023 = hdi_2023.rename(columns={
    "Inequality-adjusted Human Development Index": "ihdi"
})

# Convert democracy index to numeric (ensures correct type)
dem_2023["elect_dem_ind"] = pd.to_numeric(dem_2023["elect_dem_ind"], errors="coerce")

# (ihdi is already float64, but this is harmless / consistent)
hdi_2023["ihdi"] = pd.to_numeric(hdi_2023["ihdi"], errors="coerce")

# If there are accidental duplicates, keep the first
dem_2023 = dem_2023.drop_duplicates(subset=["join_key"])
hdi_2023 = hdi_2023.drop_duplicates(subset=["join_key"])

# Inner join: keep only countries present in both datasets
merged = dem_2023.merge(hdi_2023[["join_key", "ihdi"]], on="join_key", how="inner")

# Add country label for hover info
merged["country"] = merged["country_mapped"]

# Drop rows with missing values
merged = merged.dropna(subset=["elect_dem_ind", "ihdi", "country"])

# %%
# --- Add regime labels to merged data ---
regime_labels = {
    0: "Closed autocracy",
    1: "Electoral autocracy",
    2: "Electoral democracy",
    3: "Liberal democracy",
}

# Merge regime column from democracy data
regime_col = df_dem2[["join_key", "regime"]].drop_duplicates(subset=["join_key"])
merged = merged.merge(regime_col, on="join_key", how="left")

# Map numeric regime codes to readable labels
merged["regime_label"] = merged["regime"].map(regime_labels).fillna("Unknown")

# Print shape and regime distribution for verification
print("Merged dataframe shape:", merged.shape)
print("\nRegime distribution:")
print(merged["regime_label"].value_counts())

# %%
# --- Create interactive scatterplot with regime labels ---

# Color palette for regime types
palette = {
    "Closed autocracy": "#8A1E1C",
    "Electoral autocracy": "#FA8072",
    "Electoral democracy": "#8BC3C9",
    "Liberal democracy": "#2027A1",
}

# Create the scatter plot
fig = px.scatter(
    merged,
    x="elect_dem_ind",
    y="ihdi",
    custom_data=["country"],
    color="regime_label",
    color_discrete_map=palette,
    category_orders={"regime_label": list(palette.keys())},
    labels={
        "elect_dem_ind": "Electoral Democracy Index",
        "ihdi": "Inequality-adjusted HDI",
        "regime_label": "Regime Type",
    },
    title="<span style='font-size:18px;'>Electoral Democracy vs Inequality-adjusted HDI in Africa (2023)</span><br><span style='font-size:14px;'>Hover over dots to view country and scores</span>",
    height=750,
)

# Update marker appearance and hover info
fig.update_traces(
    marker=dict(size=12, opacity=0.85),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Electoral Democracy Index: %{x:.3f}<br>"
        "Inequality-adjusted HDI: %{y:.3f}"
        "<extra></extra>"
    ),
)

# Calculate and add linear trendline
fit_df = merged.dropna(subset=["elect_dem_ind", "ihdi"]).copy()
x = fit_df["elect_dem_ind"].astype(float).to_numpy()
y = fit_df["ihdi"].astype(float).to_numpy()

# Linear regression: y = m*x + b
m, b = np.polyfit(x, y, 1)
x_line = np.linspace(x.min(), x.max(), 100)
y_line = m * x_line + b

fig.add_scatter(
    x=x_line,
    y=y_line,
    mode="lines",
    name="Trend",
    line=dict(color="black", width=2, dash="dash"),
    hoverinfo="skip",
)

# Update plot layout and style
fig.update_layout(
    template="plotly_white",
    title_x=0.5,
    title_y=0.92,
    plot_bgcolor = "#FCFCFC",
    paper_bgcolor = "#FFEBDE",
    hovermode="closest",
    dragmode=False,
    hoverlabel=dict(
        bgcolor="#F0F0F0",
        bordercolor="black",
    ),
    legend=dict(
        x=0.03,
        y=0.98,
        xanchor="left",
        yanchor="top",
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    ),
)

# --- Save plot to HTML with enhancements ---
output_file = "africa_democracy_ihdi_2023.html"

html_string = fig.to_html(
    include_plotlyjs="cdn",
    full_html=True,
    config={"displayModeBar": False, "scrollZoom": True},
)

html_enhancements = """
<style>
  #open-fullpage-btn {
    position: fixed;
    top: 12px;
    right: 12px;
    z-index: 9999;
    padding: 8px 10px;
    font: 14px/1.2 Arial, sans-serif;
    background: rgba(255,255,255,0.85);
    border: 1px solid rgba(0,0,0,0.25);
    border-radius: 6px;
    cursor: pointer;
  }

  #open-fullpage-btn:hover {
    background: rgba(255,255,255,0.98);
  }
</style>

<button id="open-fullpage-btn" type="button" title="Open in a new tab">
  Open full page ↗
</button>

<script>
window.addEventListener('load', function () {
    const plotDiv = document.querySelector('.plotly-graph-div');
    const btn = document.getElementById('open-fullpage-btn');
    
    if (!plotDiv) return;

    function setOverlayCursor(value) {
        plotDiv.querySelectorAll('.draglayer rect, .draglayer path').forEach(function (el) {
            el.style.cursor = value;
        });
    }

    setOverlayCursor('default');

    plotDiv.on('plotly_hover', function () {
        setOverlayCursor('pointer');
    });

    plotDiv.on('plotly_unhover', function () {
        setOverlayCursor('default');
    });

    plotDiv.on('plotly_afterplot', function () {
        setOverlayCursor('default');
    });

    if (btn) {
        const embedded = (window.self !== window.top);

        if (!embedded) {
            btn.style.display = 'none';
        } else {
            btn.addEventListener('click', function () {
                window.open(window.location.href, '_blank', 'noopener');
            });
        }
    }
});
</script>
"""

html_string = html_string.replace('</body>', html_enhancements + '</body>')

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_string)

webbrowser.open(output_file)

print(f"Saved to: {output_file}")

# Show plot in notebook (if running interactively)
fig.show()