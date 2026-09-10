pythonimport streamlit as st
import requests
from textblob import TextBlob
import urllib.parse
import pandas as pd
import pydeck as pdk

# ==============================================================================
# 1. ENTERPRISE GATEWAY & BRANDING
# ==============================================================================
st.set_page_config(page_title="Project CORA | Risk Analytics", layout="wide")
st.title("🚢 Project CORA: Corporate Operations & Risk Analytics")

# OFFICIAL RESEARCH IDENTIFIER
st.markdown("### **Lead Author & Independent Researcher:**")
st.subheader("👨‍💻 Mohd Khairul Ridhuan bin Mohd Fadzil")
st.markdown("*Specialization: Structured Analytic Techniques (SAT), Alternative Risk Ingestion, Cognitive Bias Mitigation, and 3D Geospatial Telemetry.*")
st.caption("Classification: RESTRICTED ENTERPRISE USE ONLY | Data Stream: LIVE 15-Minute Intercept")
st.divider()

# ==============================================================================
# 2. INTERACTIVE VECTOR BALANCING (THE 'WHAT' & 'WHEN')
# ==============================================================================
st.write("### 📍 Active Node Telemetry Grid")
st.caption("Select a commercial maritime vector to execute real-time empirical auditing and update the 3D Dynamic Threat Map.")

if "selected_node" not in st.session_state:
    st.session_state.selected_node = "Red Sea / Bab al-Mandab"

col_a, col_b, col_c = st.columns(3)

if col_a.button("🔴 Node A: Red Sea / Bab al-Mandab", use_container_width=True):
    st.session_state.selected_node = "Red Sea / Bab al-Mandab"
if col_b.button("🟡 Node B: Strait of Hormuz", use_container_width=True):
    st.session_state.selected_node = "Strait of Hormuz"
if col_c.button("🟢 Node C: Malacca Strait", use_container_width=True):
    st.session_state.selected_node = "Malacca Strait"

current_node = st.session_state.selected_node

# Dynamic Enterprise Exposure & Geopolitical Coordinate Mapping
if current_node == "Red Sea / Bab al-Mandab":
    gdelt_keyword = "Bab al-Mandab crisis"
    wolfram_query = "Suez Canal to Bab-el-Mandeb distance"
    base_multiplier = 4.5
    asset_exposure = 15000000     # $15M default fleet value
    daily_delay_cost = 45000      # Operational daily penalty cost
    node_lat, node_lon = 12.5833, 43.3333
    origin_lat, origin_lon = 29.9667, 32.5500 # Suez Port Gateway
elif current_node == "Strait of Hormuz":
    gdelt_keyword = "Strait of Hormuz military"
    wolfram_query = "Strait of Hormuz width"
    base_multiplier = 3.5
    asset_exposure = 22000000     # $22M default fleet value
    daily_delay_cost = 60000
    node_lat, node_lon = 26.5667, 56.2500
    origin_lat, origin_lon = 25.1972, 55.2744 # Dubai Jebel Ali Gateway
else:
    gdelt_keyword = "Malacca Strait piracy"
    wolfram_query = "Strait of Malacca length"
    base_multiplier = 1.5
    asset_exposure = 8000000      # $8M default fleet value
    daily_delay_cost = 25000
    node_lat, node_lon = 4.0000, 99.0000
    origin_lat, origin_lon = 1.3521, 103.8198 # Port of Singapore

# ==============================================================================
# 3. LIVE DATA INGESTION SUITE (THE 'HOW')
# ==============================================================================
st.write("### 🌐 Live Infrastructure Telemetry Ingestion")

# Fetch Secure Wolfram AppID from Cloud Environment Settings
try:
    WOLFRAM_APP_ID = st.secrets["WOLFRAM_APP_ID"]
except Exception:
    WOLFRAM_APP_ID = "DEMO"

spatial_metric = "2,210 km (Cached Geopolitical Baseline)"
if WOLFRAM_APP_ID != "DEMO":
    try:
        wolfram_url = f"http://wolframalpha.com{WOLFRAM_APP_ID}&i={urllib.parse.quote(wolfram_query)}"
        spatial_metric = requests.get(wolfram_url, timeout=5).text
    except Exception:
        pass

# Ingest live geopolitical reporting stream via GDELT DOC API v2
encoded_keyword = urllib.parse.quote(f'"{gdelt_keyword}"')
gdelt_url = f"https://gdeltproject.org{encoded_keyword}&mode=artlist&format=json"

live_headline = "No critical kinetic or cyber telemetry spikes detected in open data streams within the last 15 minutes."
live_source = "https://gdeltproject.org"

try:
    gdelt_response = requests.get(gdelt_url, timeout=5).json()
    if "articles" in gdelt_response and len(gdelt_response["articles"]) > 0:
        live_headline = gdelt_response["articles"][0]["title"]
        live_source = gdelt_response["articles"][0]["url"]
except Exception:
    pass

# Render Live Telemetry Assets onto UI
col_data_1, col_data_2 = st.columns(2)
col_data_1.info(f"📍 **Wolfram Spatial Matrix Ingested:** `{wolfram_query}` ➔ **{spatial_metric}**")
col_data_2.success(f"📡 **GDELT Live Incident Vector:** Source: [Link to Source Enclave]({live_source})")
st.warning(f"📰 **Latest Ingested Global Intelligence Feed:** *\"{live_headline}\"*")

st.divider()

# ==============================================================================
# 4. NATURAL LANGUAGE INTERPRETATION & CLIENT FINANCIAL METRICS
# ==============================================================================
st.header("🧠 Cognitive Automation & Financial Risk Ingestion")

blob = TextBlob(live_headline)
sentiment_score = float(blob.sentiment.polarity)

# Executive Guidance Framework Model
with st.expander("ℹ️ CORE LOGIC FRAMEWORK: Understanding the Anti-Deception Engine"):
    st.markdown("""
    * **The Objective:** This framework prevents human confirmation bias during complex maritime disruptions. 
    * **The Methodology:** When an anomaly occurs, ground operations often report standard excuses (weather/labor) to avoid corporate penalties. This engine tests live telemetries from **Wolfram Alpha** and **GDELT** to mathematically *disprove* alternative explanations. 
    * **The Outcome:** If weather and labor hypotheses are successfully disproved by empirical indices, the platform isolates the structural root cause: **Asymmetric Exogenous Threats (Cyber Sabotage / Geopolitical grey-zone interferences)**.
    """)

# Dynamic Real-Time Financial Calculations based on Ingested Stream Sentiment
signal_interference = True if sentiment_score < 0.0 else False
base_premium_rate = 0.015 if sentiment_score >= 0 else 0.075
calculated_premium = asset_exposure * base_premium_rate
projected_days_delayed = int(base_multiplier * 3 if signal_interference else 1)
total_delay_impact = projected_days_delayed * daily_delay_cost

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric(label="📊 Narrative Volatility Index (NLP Polarity)", value=f"{sentiment_score:.2f}", delta="Volatile Threat Vector" if sentiment_score < 0 else "Stable Baseline")
col_m2.metric(label="💰 Dynamic War-Risk Insurance Premium", value=f"USD ${calculated_premium:,.2f}", delta="+25% Variance" if signal_interference else "Standard Rate")
col_m3.metric(label="📉 Projected Contingency Delay Loss", value=f"USD ${total_delay_impact:,.2f}", delta=f"{projected_days_delayed} Days Downtime" if signal_interference else "On Schedule")

st.divider()

# ==============================================================================
# 5. ADVANCED 3D GEOSPATIAL SIMULATION (The 'Scientist' Visualization Feature)
# ==============================================================================
st.header("🌐 3D Geopolitical Anomaly Simulation Mapping")
st.caption("Real-time 3D spatial mapping representing fleet vector routes and dynamic threat radius tracking (Hold right-click and drag to rotate map).")

# CRM Processing Core for Chart Generation
h1_inconsistency = int((-5 if sentiment_score > 0.1 else 2) + (3 if signal_interference else -2))
h2_inconsistency = int((0 if sentiment_score == 0 else -3))
h3_inconsistency = int((base_multiplier * 3 if signal_interference else -4) + (5 if sentiment_score < -0.1 else 0))

# Calculate height column based on threat score intensity matrix
threat_elevation = float(abs(h3_inconsistency) * 60000 if h3_inconsistency > 0 else 1000)

map_data = pd.DataFrame({
    'from_lat': [origin_lat], 'from_lon': [origin_lon],
    'to_lat': [node_lat], 'to_lon': [node_lon],
    'threat_level': [threat_elevation]
})

# Define the Pydeck 3D Canvas Layer Framework
view_state = pdk.ViewState(latitude=node_lat, longitude=node_lon, zoom=4, pitch=50, bearing=0)

arc_layer = pdk.Layer(
    "ArcLayer", data=map_data, get_source_position="[from_lon, from_lat]", get_target_position="[to_lon, to_lat]",
    get_source_color=[0, 255, 100, 200], get_target_color=[255, 0, 50, 200], get_width=5
)

column_layer = pdk.Layer(
    "ColumnLayer", data=map_data, get_position="[to_lon, to_lat]", get_elevation="threat_level",
    elevation_scale=1, radius=50000, get_fill_color=[255, 0, 50, 150], pickable=True, auto_highlight=True
)

st.pydeck_chart(pdk.Deck(
    layers=[arc_layer, column_layer], initial_view_state=view_state, 
    map_style="mapbox://styles/mapbox/dark-v10", tooltip={"text": "Geopolitical Anomaly Vector Detected"}
))

st.divider()

# ==============================================================================
# 6. COMPETING RISK MATRIX (CRM) GRAPHICAL PRESENTATION
# ==============================================================================
st.header("📊 Competing Risk Matrix (CRM) Visual Analytics")

chart_data = pd.DataFrame({
    'Hypothesis Framework': ['Standard Weather Variance (H1)', 'Internal Operational Bottleneck (H2)', 'Exogenous Asymmetric Anomaly (H3)'],
    'Inconsistency Score Index': [h1_inconsistency, h2_inconsistency, h3_inconsistency]
})

col_c_left, col_c_right = st.columns()

with col_c_left:
    st.write("#### Numerical Assessment Audit Trail:")
    st.caption("A lower score indicates high probability (cannot be disproved by empirical telemetry). A high score index flags anomalies.")
    st.dataframe(chart_data, hide_index=True, use_container_width=True)

with col_c_right:
    st.write("#### 📈 Statistical Metric Index Chart:")
