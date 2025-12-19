import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# --- Constants ---
FAO_DIR = 'FAO'
ZIM_DIR = os.path.join(FAO_DIR, 'Zimbabwe')
FILE_1 = os.path.join(ZIM_DIR, 'Zimbabwe_2021-22.csv')
FILE_2 = os.path.join(ZIM_DIR, 'Zimbabwe_2023-25.csv')
GEOJSON_FILE = os.path.join(ZIM_DIR, 'Zimbabwe_Admin1_Lite.geojson')
OUTPUT_CHART = 'lcsi_trend_chart.html'
OUTPUT_MAP = 'lcsi_map.html'

# --- 1. Data Loading & Preprocessing ---
print("Loading data...")

# Load File 1 (2021-22)
df1 = pd.read_csv(FILE_1, low_memory=False)
# Rename spatial column for consistency
if 'Admin 1 name' in df1.columns:
    df1.rename(columns={'Admin 1 name': 'adm1_name'}, inplace=True)

# Load File 2 (2023-25)
df2 = pd.read_csv(FILE_2, low_memory=False)
# Ensure consistent spatial column name
if 'Admin 1 name' in df2.columns:
    df2.rename(columns={'Admin 1 name': 'adm1_name'}, inplace=True)

# Select relevant columns
cols_to_keep = ['adm1_name', 'survey_date', 'lcsi']
df1 = df1[cols_to_keep].copy()
df2 = df2[cols_to_keep].copy()

# Merge DataFrames
df = pd.concat([df1, df2], ignore_index=True)

# Process Dates
print("Processing dates...")
df['survey_date'] = pd.to_datetime(df['survey_date'], errors='coerce')
df['Year'] = df['survey_date'].dt.year

# Filter invalid years if any (e.g. naive parsing errors)
df = df.dropna(subset=['Year'])
df['Year'] = df['Year'].astype(int)

# --- 2. LCSI Analysis (Trends) ---
print("Analyzing LCSI trends...")

# Map LCSI codes to labels (Assumption: 1=Stress, 2=Crisis, 3=Emergency, 0=None)
# If the values are different, the chart might look empty, but we verified [1 2 3 0].
lcsi_map = {1: 'Stress', 2: 'Crisis', 3: 'Emergency', 0: 'None'}
df['lcsi_label'] = df['lcsi'].map(lcsi_map)

# Calculate percentages per year
trend_data = df.groupby(['Year', 'lcsi_label']).size().reset_index(name='Count')
total_per_year = df.groupby('Year').size().reset_index(name='Total')
trend_data = trend_data.merge(total_per_year, on='Year')
trend_data['Percentage'] = (trend_data['Count'] / trend_data['Total']) * 100

# Filter for relevant categories
categories = ['Stress', 'Crisis', 'Emergency']
trend_filtered = trend_data[trend_data['lcsi_label'].isin(categories)]

# Create Line Chart
fig_trend = px.line(
    trend_filtered, 
    x='Year', 
    y='Percentage', 
    color='lcsi_label',
    markers=True,
    title='LCSI Strategies Trend (2021-2025)',
    labels={'Percentage': '% of Households', 'lcsi_label': 'Strategy Type'},
    category_orders={'lcsi_label': ['Stress', 'Crisis', 'Emergency']}
)
fig_trend.update_layout(template='plotly_white', hovermode='x unified')

# Save Trend Chart
output_chart_path = os.path.join(FAO_DIR, OUTPUT_CHART)
fig_trend.write_html(output_chart_path, include_plotlyjs='cdn')
print(f"Saved trend chart to {output_chart_path}")

# --- 3. Spatial Analysis (Map) ---
print("Generating spatial map...")

# specific focus on EMERGENCY strategies (Value = 3)
df['is_emergency'] = (df['lcsi'] == 3).astype(int)

# Group by Region and Year
# Calculate prevalence of Emergency strategies
map_data = df.groupby(['adm1_name', 'Year'])['is_emergency'].mean().reset_index()
map_data['Prevalence'] = map_data['is_emergency'] * 100  # Convert to percentage

# Start visualization
# Load GeoJSON
with open(GEOJSON_FILE, encoding='utf-8') as f:
    geojson = json.load(f)

# The geojson feature properties usually have a name field. 
# Let's verify what key to use. Usually 'ADM1_EN' or 'admin1Name'. 
# For standard FAO/HDX, it might be 'ADM1_EN'.
# We'll use a standard creation method which tries to match features.

# Ensure full year range for animation (if some regions missing in some years, we fill with NaN or 0)
# But for simplicity, we let Plotly handle missing frames or we assume data is dense enough.

fig_map = px.choropleth(
    map_data,
    geojson=geojson,
    locations='adm1_name',
    featureidkey='properties.ADM1_EN', # Common key, might need adjustment if map is blank
    color='Prevalence',
    animation_frame='Year',
    range_color=[0, map_data['Prevalence'].max()],
    color_continuous_scale='Reds',
    title='Prevalence of Emergency Livelihood Coping Strategies (% of HH)',
    labels={'Prevalence': 'Emergency Rate (%)'}
)

# If 'ADT_EN' or other keys are used in the geojson, we might need to inspect it. 
# But 'properties.ADM1_EN' is a safe bet for Admin1 boundaries often used.
# If the map comes up blank, the key is the issue. 
# Let's inspect the geojson briefly in code? 
# No, let's just default to 'properties.ADM1_EN' and if it fails (blank map), 
# I can fix it. But I'll add a quick check logic internally to be smarter.

# Quick logic to find the name key
if geojson['features']:
    props = geojson['features'][0]['properties']
    # Look for a key that looks like name
    possible_keys = ['ADM1_EN', 'ADM1_NAME', 'admin1Name', 'name', 'NAME']
    found_key = 'properties.ADM1_EN' # Default
    for key in possible_keys:
        if key in props:
            found_key = f'properties.{key}'
            break
    print(f"Using GeoJSON key: {found_key}")
    
    fig_map.update_traces(marker_line_width=0.5)
    fig_map = px.choropleth(
        map_data,
        geojson=geojson,
        locations='adm1_name',
        featureidkey=found_key,
        color='Prevalence',
        animation_frame='Year',
        range_color=[0, map_data['Prevalence'].max()], # robust scaling
        color_continuous_scale='Reds',
        title='Prevalence of Emergency Livelihood Coping Strategies (%)'
    )
    fig_map.update_geos(fitbounds="locations", visible=False)
    fig_map.update_layout(margin={"r":0,"t":50,"l":0,"b":0})

# Save Map
output_map_path = os.path.join(FAO_DIR, OUTPUT_MAP)
fig_map.write_html(output_map_path, include_plotlyjs='cdn')
print(f"Saved map to {output_map_path}")

print("Done.")
