"""
Interactive Map of Electoral Democracy in Africa
------------------------------------------------
This script loads democracy index data for African countries from a MySQL database, 
processes and harmonizes country geometries, and generates an interactive Plotly 
choropleth map with a year slider and custom hover/click features. 
The output is an HTML file with a dynamic map for data exploration.
"""
# --- Imports ---
from sqlalchemy import create_engine, text
from getpass import getpass
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from shapely.geometry import mapping
import plotly.graph_objects as go
from pathlib import Path
import webbrowser
import plotly.express as px

# --- Database connection ---
user = "********"
password = getpass("MySQL password: ")
database = "********"
engine = create_engine(f"mysql+pymysql://{user}:{password}@localhost/{database}")

# Test connection (prints status)
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT '✅ Connection successful' AS status"))
        print(result.scalar())
except Exception as e:
    print(f"❌ Connection failed: {e}")

# --- Load democracy data ---
query = "SELECT * FROM africa_dem"
df = pd.read_sql(query, engine)
# Ensure year is integer type
df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

# --- Load world country geometries ---
world = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip"
)
# Filter for African countries
africa = world[world['CONTINENT'] == 'Africa']

# --- Load admin-1 (province) geometries for special cases ---
admin1 = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip"
)

# --- Special handling for Tanzania and Zanzibar ---
# Extract Zanzibar provinces and merge into single geometry
z_codes = ["TZ-07", "TZ-11", "TZ-15", "TZ-10", "TZ-06"]
z_parts = admin1[admin1["iso_3166_2"].isin(z_codes)].copy()
zanzibar_geom = unary_union(z_parts.geometry)
tanzania_geom = africa.loc[africa["NAME"] == "Tanzania", "geometry"].iloc[0]
tanzania_mainland_geom = tanzania_geom.difference(zanzibar_geom)
# Build Africa split with Tanzania (Mainland) and Zanzibar as separate features
africa_split = africa[africa["NAME"] != "Tanzania"].copy()
africa_split = pd.concat(
    [
        africa_split,
        gpd.GeoDataFrame({"NAME": ["Tanzania (Mainland)"]}, geometry=[tanzania_mainland_geom], crs=africa.crs),
        gpd.GeoDataFrame({"NAME": ["Zanzibar"]}, geometry=[zanzibar_geom], crs=africa.crs),
    ],
    ignore_index=True
)
# Clean Zanzibar geometry (remove internal boundaries)
zanzibar = gpd.GeoDataFrame({"NAME": ["Zanzibar"]}, geometry=[zanzibar_geom], crs=africa.crs)
zanzibar["geometry"] = zanzibar["geometry"].buffer(0)

# --- Add Mauritius and Seychelles if missing from Africa_split ---
islands = world[world["NAME"].isin(["Mauritius", "Seychelles"])][["NAME", "geometry"]].copy()
africa_split = pd.concat([africa_split, islands], ignore_index=True)

# --- Harmonize country names between data and geometries ---
name_mapping = {
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
# Optionally drop countries with no data (e.g., Bir Tawil, W. Sahara)
africa_split = africa_split[~africa_split["NAME"].isin(["Bir Tawil", "W. Sahara"])].copy()
df_only = sorted(set(df["country_name_ne"]) - set(africa_split["NAME"]))
africa_only = sorted(set(africa_split["NAME"]) - set(df["country_name_ne"]))

# --- Prepare data for selected year ---
year = 2025  # Change this to select a different year
df_merge = df.copy()
df_merge["year"] = pd.to_numeric(df_merge["year"], errors="coerce").astype("Int64")
df_merge["elect_dem_ind"] = pd.to_numeric(df_merge["elect_dem_ind"], errors="coerce")
df_merge["corrupt_ind"] = pd.to_numeric(df_merge["corrupt_ind"], errors="coerce")
df_merge["lawrule_ind"] = pd.to_numeric(df_merge["lawrule_ind"], errors="coerce")
df_year = df_merge[df_merge["year"] == year].copy()
# Merge geometry and data for the selected year
africa_map = africa_split.merge(
    df_year,
    left_on="NAME",
    right_on="country_name_ne",
    how="left",
)
africa_map["plot_val"] = pd.to_numeric(africa_map["elect_dem_ind"], errors="coerce")
# Compute representative points for labels (if needed)
africa_map["label_pt"] = africa_map.geometry.representative_point()
africa_map["label_x"] = africa_map["label_pt"].x
africa_map["label_y"] = africa_map["label_pt"].y
africa_map["label_txt"] = africa_map["plot_val"].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")

# --- Add Western Sahara as a disputed area (if present) ---
disputed = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_disputed_areas.zip"
)
ws_disputed = disputed[
    disputed['NAME'].str.contains('Sahara', case=False, na=False) 
    | disputed['ADMIN'].str.contains('Sahara', case=False, na=False)
]
africa_split = pd.concat([africa_split, ws_disputed[['NAME', 'geometry']]], ignore_index=True)

############################################################
# CREATE INTERACTIVE PLOTLY MAP
############################################################
SIMPLIFY_TOLERANCE = 0.02   # try 0.01–0.05 if needed
N_BINS = 9                 # discrete color steps
out_html = "africa_democracy_slider_hover_click.html"
regime_names = {
    0: "Closed Autocracy",
    1: "Electoral Autocracy",
    2: "Electoral Democracy",
    3: "Liberal Democracy",
}
# 1) Build a "base" GeoDataFrame for geometry only (stable across years)
base_geo = africa_split[["NAME", "geometry"]].copy()
base_geo = base_geo.to_crs(epsg=4326)
base_geo["geometry"] = base_geo["geometry"].simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
base_geo = base_geo.reset_index(drop=True)
base_geo["plot_id"] = base_geo.index.astype(str)
# Convert base geometry to GeoJSON for Plotly
geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": {"plot_id": row.plot_id},
        }
        for _, row in base_geo.iterrows()
    ],
}
# 2) Prepare democracy data for all years (for animation)
df_all = df.copy()
df_all["year"] = pd.to_numeric(df_all["year"], errors="coerce").astype("Int64")
df_all["elect_dem_ind"] = pd.to_numeric(df_all["elect_dem_ind"], errors="coerce")
df_all["regime"] = pd.to_numeric(df_all["regime"], errors="coerce")
# Ensure mapped name exists
if "country_name_ne" not in df_all.columns:
    raise RuntimeError("df_all must have country_name_ne (apply name_mapping step first).")
years = sorted([int(y) for y in df_all["year"].dropna().unique().tolist()])
if not years:
    raise RuntimeError("No valid years found in df_all['year'].")
# Helper: Format index for hover text
def fmt_index(v):
    if pd.isna(v):
        return "No data"
    return f"{v:.3f}"
# Helper: Build hover text for each country
def build_hover(country, elect, regime, year):
    reg_name = regime_names.get(int(regime), "No data") if pd.notna(regime) else "No data"
    return (
        f"<b>{country}</b><br>"
        f"Electoral Democracy Index: {fmt_index(elect)}<br>"
        f"Regime Type: {reg_name}<br>"
        f"Year: {year}"
    )
# Helper: Discretize values into bins for color mapping
def discretize(values, edges):
    b = np.digitize(values, edges, right=True) - 1
    b = np.clip(b, 0, len(edges) - 2)
    return b
# 4) Build animation frames (one per year)
#    Each frame has its own color bins for better contrast
frames = []
first_year = years[-1]  # Start at most recent year by default
for y in years:
    df_y = df_all[df_all["year"] == y][["country_name_ne", "elect_dem_ind", "regime"]].copy()
    m = base_geo.merge(df_y, left_on="NAME", right_on="country_name_ne", how="left")
    NO_DATA_BIN = N_BINS  # Extra bin for missing data (grey)
    m["is_no_data"] = m["elect_dem_ind"].isna() | m["NAME"].str.contains("W\\. Sahara|Western Sahara", case=False, na=False)
    obs_min = float(m["elect_dem_ind"].min())
    obs_max = float(m["elect_dem_ind"].max())
    if not np.isfinite(obs_min) or not np.isfinite(obs_max) or obs_min == obs_max:
        obs_min, obs_max = 0.0, 1.0
    bin_edges = np.linspace(obs_min, obs_max, N_BINS + 1)
    z_for_color = discretize(m["elect_dem_ind"].to_numpy(), bin_edges)
    z_for_color = np.where(m["is_no_data"].to_numpy(), NO_DATA_BIN, z_for_color)
    hover = [
        build_hover(row["NAME"], row["elect_dem_ind"], row["regime"], y)
        for _, row in m.iterrows()
    ]
    frames.append(
        go.Frame(
            name=str(y),
            data=[
                go.Choropleth(
                    z=z_for_color,
                    customdata=np.array(hover).reshape(-1, 1),
                )
            ],
            layout=go.Layout(
                title=dict(text=f"Electoral Democracy in Africa ({y})")
            ),
        )
    )
# 5) Create the initial Plotly figure (use first_year frame's data)
init_frame = next(f for f in frames if f.name == str(first_year))
init_z = init_frame.data[0]["z"]
init_customdata = init_frame.data[0]["customdata"]
# Build color scale: Viridis for bins, grey for missing data
colorscale_grey = [
    [i/(N_BINS), c]
    for i, c in enumerate(
        px.colors.sample_colorscale(
            "Viridis",
            [i/(N_BINS-1) for i in range(N_BINS)]
        )
    )
]
colorscale_grey += [[1.0, "#9F9FA9"]]
fig = go.Figure(
    data=[
        go.Choropleth(
            geojson=geojson,
            locations=base_geo["plot_id"],
            featureidkey="properties.plot_id",
            z=init_z,
            zmin=0,
            zmax=N_BINS,
            colorscale=colorscale_grey,
            marker_line_color="black",
            marker_line_width=0.3,
            customdata=init_customdata,
            hovertemplate="%{customdata[0]}<extra></extra>",
            showscale=True,
            colorbar=dict(
                title="Electoral<br>Democracy<br>Index",
                x=0.88,
                xanchor="left",
                y=0.45,
                yanchor="middle",
                len=0.75,
                thickness=35,
                tickmode="array",
                tickvals=[1, 2, 3, 4, 5, 6, 7, 8],
                ticktext=["0.1","0.2","0.3","0.4","0.5","0.6","0.7","0.8"],
            ),
        )
    ],
    frames=frames
)
# Set map projection and appearance
fig.update_geos(
    projection_type="equal earth",
    visible=False,
    showcountries=False,
    showcoastlines=False,
    bgcolor="#F5F5F5",
    lonaxis=dict(range=[-25, 60]),
    lataxis=dict(range=[-40, 40]),
)
# Add play/pause buttons and slider for animation
fig.update_layout(
    updatemenus=[
        dict(
            type="buttons",
            direction="right",
            x=0.05,
            y=1.05,
            showactive=False,
            pad={"r": 10, "t": 10},
            buttons=[
                dict(
                    label="Play",
                    method="animate",
                    args=[None, {"frame": {"duration": 600, "redraw": True}, "fromcurrent": True}],
                ),
                dict(
                    label="Pause",
                    method="animate",
                    args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                ),
            ],
        )
    ],
    sliders=[
        dict(
            active=len(years) - 1,
            x=0.11,
            y=1.15,
            len=0.85,
            pad={"t": 10, "b": 10},
            currentvalue={"visible": False},
            steps=[
                dict(
                    method="animate",
                    label=str(y),
                    args=[[str(y)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                )
                for y in years
            ],
        )
    ],
    title=dict(
        text=f"Electoral Democracy in Africa ({first_year})",
        x=0.51,
        y=0.98,
        xanchor="center",
        yanchor="top",
        font=dict(size=18),
    ),
    annotations=[
        dict(
            text="Hover to preview • Click to pin label • Use slider to change year",
            xref="paper",
            yref="paper",
            x=0.5,
            y=1.18,
            showarrow=False,
            font=dict(size=14),
            xanchor="center",
        )
    ],
    margin=dict(l=15, r=15, t=145, b=15),
    paper_bgcolor="#FFEBDE",
    hoverlabel=dict(
        bgcolor="#F0F0F0",
        font=dict(
            size=14,
            family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
            color="black",
        ),
        bordercolor="#333",
        align="left",
    ),
)
# Save the interactive map to HTML and inject custom JS for click-to-pin labels
fig.write_html(
    out_html,
    include_plotlyjs="cdn",
    config={"scrollZoom": True, "displayModeBar": False, "responsive": True},
    auto_play=False
)

# --- Click-to-pin script injection (minimal + robust) ---
click_pin_script = r"""
<!-- Click-to-pin labels enabled -->
<style>
  .pin-label {
    position: absolute;
    background: rgba(240,240,240,0.55);
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px 10px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
    color: #000;
    pointer-events: auto;
    max-width: 280px;
    z-index: 9999;
    box-shadow: 0 2px 10px rgba(0,0,0,0.35);
    cursor: move; 
  }
  .pin-close {
    float: right;
    cursor: pointer;
    font-weight: 700;
    margin-left: 8px;
  }
</style>

<script>
(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    const gd = document.querySelector('.plotly-graph-div');
    if (!gd) return;

    // ensure container is position:relative so absolute labels anchor correctly
    const container = gd.parentElement;
    if (container && getComputedStyle(container).position === 'static') {
      container.style.position = 'relative';
    }

    // store pinned labels by a stable key
    const pinned = new Map();

    // -- Drag and drop variables and listeners --
    let dragEl = null;
    let dragStartX = 0;
    let dragStartY = 0;
    let initialLeft = 0;
    let initialTop = 0;

    document.addEventListener('mousedown', function(e) {
      const pin = e.target.closest('.pin-label');
      if (!pin || e.target.className === 'pin-close') return;
      dragEl = pin;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      initialLeft = parseInt(dragEl.style.left || 0, 10);
      initialTop = parseInt(dragEl.style.top || 0, 10);
      dragEl.style.cursor = 'grabbing';
      e.preventDefault(); // prevent accidental text highlighting
    });

    document.addEventListener('mousemove', function(e) {
      if (!dragEl) return;
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      dragEl.style.left = (initialLeft + dx) + 'px';
      dragEl.style.top = (initialTop + dy) + 'px';
    });

    document.addEventListener('mouseup', function() {
      if (dragEl) {
        dragEl.style.cursor = 'move';
        dragEl = null;
      }
    });

    function makeKey(pt) {
      // curveNumber + pointNumber is stable for a single rendered choropleth trace
      return `${pt.curveNumber}:${pt.pointNumber}`;
    }

    function makeKey(pt) {
      // Create a unique key using the point ID *and* the label's HTML text (which includes the year)
      const content = (pt.customdata && pt.customdata[0]) ? pt.customdata[0] : (pt.text || '');
      return `${pt.curveNumber}:${pt.pointNumber}:${content}`;
    }

    function addPin(pt) {
      const key = makeKey(pt);
      if (pinned.has(key)) {
        removePin(key);
        return;
      }

      // Prefer the customdata hover HTML string
      const html = (pt.customdata && pt.customdata[0]) ? pt.customdata[0] : (pt.text || 'No data');

      // Create label element
      const div = document.createElement('div');
      div.className = 'pin-label';

      const close = document.createElement('span');
      close.className = 'pin-close';
      close.innerHTML = '×';
      
      // Stop drag events from swallowing the click, and delete from screen immediately
      close.onpointerdown = function(e) {
        e.stopPropagation();
        e.preventDefault();
        div.remove();
        pinned.delete(key);
      };
      // Fallback
      close.onclick = function(e) {
        e.stopPropagation();
        div.remove();
        pinned.delete(key);
      };

      div.appendChild(close);

      const body = document.createElement('div');
      body.innerHTML = html;
      div.appendChild(body);

      // Position near the click event (fallback: center)
      const x = (pt.event && pt.event.clientX) ? pt.event.clientX : (window.innerWidth / 2);
      const y = (pt.event && pt.event.clientY) ? pt.event.clientY : (window.innerHeight / 2);

      // Convert viewport coords to container coords
      const rect = container.getBoundingClientRect();
      div.style.left = (x - rect.left + 10) + 'px';
      div.style.top  = (y - rect.top + 10) + 'px';

      container.appendChild(div);
      pinned.set(key, div);
    }

    gd.on('plotly_click', function (data) {
      // Disable click-to-pin on touch devices to prevent double labels
      if ('ontouchstart' in window || navigator.maxTouchPoints > 0) return;
      
      if (!data || !data.points || !data.points.length) return;
      const pt = data.points[0];
      addPin(pt);
    });

    // --- Refresh hover label dynamically during animation playback ---
    let lastX = 0;
    let lastY = 0;
    let isMouseOver = false;

    // 1. Track the exact mouse pixel coordinates
    gd.addEventListener('mousemove', function(e) {
      lastX = e.clientX;
      lastY = e.clientY;
      isMouseOver = true;
    });

    // 2. Stop tracking if the mouse leaves the graph area
    gd.addEventListener('mouseleave', function() {
      isMouseOver = false;
    });

    // 3. When a new animation frame plays, simulate a real mouse movement
    gd.on('plotly_animatingframe', function() {
      if (isMouseOver) {
        // Wait 100ms for the new frame's data to finish drawing on the screen
        setTimeout(function() {
          // Find whatever parts of the map are directly under the mouse right now
          const el = document.elementFromPoint(lastX, lastY);
          if (el) {
            // Fake a mouse movement event on that exact spot
            el.dispatchEvent(new MouseEvent('mousemove', {
              clientX: lastX,
              clientY: lastY,
              bubbles: true
            }));
          }
        }, 100); 
      }
    });

    console.log("✅ Click-to-pin enabled: click country to pin/unpin label.");
  });
})();
</script>
"""

open_full_page_button_script = """
<style>
  #open-fullpage-btn{
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
  #open-fullpage-btn:hover{
    background: rgba(255,255,255,0.98);
  }
</style>

<button id="open-fullpage-btn" type="button" title="Open in a new tab">
  Open full page ↗
</button>

<script>
  (function () {
    var btn = document.getElementById('open-fullpage-btn');
    if (!btn) return;

    // Only show the button when embedded (inside an iframe).
    // If opened directly (top-level window), hide it.
    var embedded = (window.self !== window.top);
    if (!embedded) {
      btn.style.display = 'none';
      return;
    }

    btn.addEventListener('click', function () {
      window.open('https://fablebits.github.io/Electoral-Democracy-in-Africa/', '_blank', 'noopener');
    });
  })();
</script>
"""

if "click_pin_script" not in globals():
    raise RuntimeError("click_pin_script not found. Reuse the exact click-to-pin JS from your working version.")

p = Path(out_html)
html = p.read_text(encoding="utf-8")

if "Click-to-pin labels enabled" not in html:
    html = html.replace(
        "</body>",
        click_pin_script + "\n" + open_full_page_button_script + "\n</body>"
    )
    p.write_text(html, encoding="utf-8")

webbrowser.open(p.resolve().as_uri())