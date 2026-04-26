import mysql.connector
import sqlalchemy
from sqlalchemy import create_engine, text
from mysql.connector import Error
from getpass import getpass
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from matplotlib.patches import Patch

# Database Setup
user = "********"
password = getpass("MySQL password: ")
database = "my_database_2"

engine = create_engine(f"mysql+pymysql://{user}:{password}@localhost/{database}")

# Load Data
query = "SELECT * FROM africa_dem"
df = pd.read_sql(query, engine)

# Geography Setup
world = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip"
)
Africa = world[(world['CONTINENT'] == 'Africa')]

admin1 = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip"
)

# Zanzibar Setup
z_codes = ["TZ-07", "TZ-11", "TZ-15", "TZ-10", "TZ-06"]
z_parts = admin1[admin1["iso_3166_2"].isin(z_codes)].copy()
zanzibar_geom = unary_union(z_parts.geometry)

tanzania_geom = Africa.loc[Africa["NAME"].eq("Tanzania"), "geometry"].iloc[0]
tanzania_mainland_geom = tanzania_geom.difference(zanzibar_geom)

Africa_split = Africa[Africa["NAME"] != "Tanzania"].copy()
Africa_split = pd.concat(
    [
        Africa_split,
        gpd.GeoDataFrame({"NAME": ["Tanzania (Mainland)"]}, geometry=[tanzania_mainland_geom], crs=Africa.crs),
        gpd.GeoDataFrame({"NAME": ["Zanzibar"]}, geometry=[zanzibar_geom], crs=Africa.crs),
    ],
    ignore_index=True
)

# Add Islands
islands = world[world["NAME"].isin(["Mauritius", "Seychelles"])][["NAME", "geometry"]].copy()
Africa_split = pd.concat([Africa_split, islands], ignore_index=True)

# Map Country Names
name_mapping = {
    # V-Dem -> Natural Earth (admin-0)
    "Cape Verde": "Cabo Verde",
    "Central African Republic": "Central African Rep.",
    "Democratic Republic of the Congo": "Dem. Rep. Congo",
    "Equatorial Guinea": "Eq. Guinea",
    "Eswatini": "eSwatini",
    "Ivory Coast": "Côte d'Ivoire",
    "Republic of the Congo": "Congo",
    "Sao Tome and Principe": "São Tomé and Principe",
    "South Sudan": "S. Sudan",
    "The Gambia": "Gambia",
    "Tanzania": "Tanzania (Mainland)",
    "Zanzibar": "Zanzibar",
}

df["country_name_vdem"] = df["country_name"]
df["country_name_ne"] = df["country_name_vdem"].replace(name_mapping)

# Fix Western Sahara
Africa_split = Africa_split[~Africa_split["NAME"].isin(["W. Sahara"])].copy()

disputed = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_disputed_areas.zip"
)

ws_disputed = disputed[
    disputed['NAME'].str.contains('Sahara', case=False, na=False) 
    | disputed['ADMIN'].str.contains('Sahara', case=False, na=False)
]
Africa_split = pd.concat([Africa_split, ws_disputed[['NAME', 'geometry']]], ignore_index=True)

# Plotting settings
year = 2011
side_countries = ["Gambia", "Guinea-Bissau", "Sierra Leone", "Liberia", "Togo", "Benin", "Rwanda", "Burundi", "Zanzibar", "Seychelles"]

df_year = df.copy()
df_year["year"] = pd.to_numeric(df_year["year"], errors="coerce").astype("Int64")
df_year["elect_dem_ind"] = pd.to_numeric(df_year["elect_dem_ind"], errors="coerce")
df_year = df_year[df_year["year"] == year][["country_name_ne", "elect_dem_ind"]].drop_duplicates()

africa_map = Africa_split.merge(
    df_year,
    left_on="NAME",
    right_on="country_name_ne",
    how="left",
)
africa_map["plot_val"] = pd.to_numeric(africa_map["elect_dem_ind"], errors="coerce")

africa_map = africa_map.to_crs("EPSG:8857")

africa_map["label_pt"] = africa_map.geometry.representative_point()
africa_map["label_x"] = africa_map["label_pt"].x
africa_map["label_y"] = africa_map["label_pt"].y
africa_map["label_txt"] = africa_map["plot_val"].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")

fig, ax = plt.subplots(figsize=(12, 12))

ax.set_facecolor("#7f7f7f")

africa_map.plot(ax=ax, color="#7f7f7f", edgecolor="black", linewidth=0.3)

ws_row = africa_map[africa_map['NAME'].str.contains('Sahara', case=False, na=False)]
if len(ws_row) > 0:
    ws_row.plot(ax=ax, color='#E4E4E7', edgecolor='black', linewidth=0.3, hatch='///', zorder=1)

africa_map[africa_map["plot_val"].notna()].plot(
    ax=ax,
    column="plot_val",
    cmap="viridis",
    legend=False,
    edgecolor="black",
    linewidth=0.3,
)

for _, r in africa_map.dropna(subset=["plot_val"]).iterrows():
    if r["NAME"] in side_countries:
        continue
    ax.text(
        r["label_x"], r["label_y"],
        r["label_txt"],
        ha="center", va="center",
        fontsize=16,
        color="black",
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.6),
        zorder=10,
    )

side_rows = africa_map[africa_map["NAME"].isin(side_countries)].set_index("NAME")
side_lines = "\n".join(
    f"{name}: {side_rows.loc[name, 'label_txt']}"
    for name in side_countries
    if name in side_rows.index
)
        
ax.text(
    0.11, 0.22,
    side_lines,
    transform=ax.transAxes,
    ha="left", va="bottom",
    fontsize=16,
    bbox=dict(boxstyle="round,pad=0.4", fc="#EDE2AF", ec="black", alpha=0.3),
    zorder=20,
)

ax.set_aspect("equal")
ax.set_title(f"Electoral Democracy Index (V-Dem) — Africa, {year}", fontsize=20)
ax.set_axis_off()
plt.tight_layout()

ax.set_xlim(-2500000, 6000000)
ax.set_ylim(-4500000, 5000000)

plt.savefig(
    f'africa_dem_{year}_equal_earth.png',
    dpi=300,
    bbox_inches='tight',
    pad_inches=0.1,
    facecolor='#E8DFDF'
)

plt.show()