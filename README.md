# African Democracy Visualization Project

This repository explores the state of democracy and its relationship with human development across the African continent during the period **2011–2025**. Using data-driven visualizations, it analyzes how democratic institutions correlate with inequality-adjusted development outcomes.

## 📊 Visualizations

### 1. Interactive Map of Electoral Democracy
**File:** [african_democracy_interative_map.py](african_democracy_interative_map.py)
*   **Description:** An interactive choropleth map that allows users to explore democracy index scores across Africa from 2011 to 2025. 
*   **Features:**
    *   Dynamic year slider to track changes over time.
    *   Specialized handling for sub-national regions (e.g., Zanzibar and Tanzania Mainland).
    *   Interactive hover and click features for detailed data exploration.

### 2. IHDI vs. Democracy Quality Scatterplot
**File:** [ihdi_democracy_interactive_scatterplot.py](ihdi_democracy_interactive_scatterplot.py)
*   **Description:** An interactive scatterplot that examines the correlation between the **Electoral Democracy Index** and the **Inequality-adjusted Human Development Index (IHDI)**.
*   **Insight:** Helps determine how much political freedom influences developmental equality during the examined period.

## 🗂️ Data Sources

*   **Democracy Data:** [Varieties of Democracy (V-Dem)](https://www.v-dem.net/), providing multidimensional data on the quality of democracy.
*   **IHDI Data:** [United Nations Development Programme (UNDP)](https://hdr.undp.org/data-center/inequality-adjusted-human-development-index), measuring national achievements while accounting for inequality.
*   **Geospatial Data:** [Natural Earth](https://www.naturalearthdata.com/) for country and province-level boundaries.

## 🛠️ Technical Stack

*   **Languages:** Python (Pandas, GeoPandas, NumPy).
*   **Visualizations:** Plotly (Interactive maps and charts), Matplotlib/Seaborn.
*   **Database:** MySQL (SQLAlchemy) for storing and querying historical datasets.
*   **Geometry:** Shapely for handling complex spatial merges.

## 🚀 How to Run

1.  **Configure Database:** Ensure your MySQL instance contains the `africa_dem` and `africa_ihdi_2023` tables.
2.  **Install Dependencies:**
    ```bash
    pip install pandas geopandas sqlalchemy pymysql plotly matplotlib adjustText
    ```
3.  **Run Scripts:** Execute either [african_democracy_interative_map.py](african_democracy_interative_map.py) or [ihdi_democracy_interactive_scatterplot.py](ihdi_democracy_interactive_scatterplot.py). An HTML file will be generated and opened in your browser.
