import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

DARK_LAYOUT = dict(
    paper_bgcolor='rgba(11, 14, 20, 0.8)',
    plot_bgcolor='rgba(11, 14, 20, 0.8)',
    font=dict(color='#E2E8F0', family='Titillium Web, sans-serif'),
    xaxis=dict(gridcolor='rgba(255, 255, 255, 0.08)'),
    yaxis=dict(gridcolor='rgba(255, 255, 255, 0.08)')
)

def build_position_chart(facts_data: Dict[str, Any]) -> go.Figure:
    """
    Generates interactive lap-by-lap position chart.
    """
    laps_df = pd.DataFrame(facts_data.get("lap_positions", []))
    if laps_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No Lap Data Available", showarrow=False, font=dict(size=18, color="#FFFFFF"))
        fig.update_layout(**DARK_LAYOUT)
        return fig

    fig = px.line(
        laps_df,
        x="lap",
        y="position",
        color="driver",
        title="<b>Position Progression by Lap</b>",
        labels={"lap": "Lap Number", "position": "Position", "driver": "Driver"}
    )
    fig.update_yaxes(autorange="reversed", dtick=1)
    fig.update_layout(**DARK_LAYOUT)
    return fig

def build_grid_vs_finish_chart(facts_data: Dict[str, Any]) -> go.Figure:
    """
    Generates Grid Position vs. Finishing Position scatter delta chart.
    """
    results_df = pd.DataFrame(facts_data.get("results", []))
    if results_df.empty:
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT)
        return fig

    fig = px.scatter(
        results_df,
        x="grid",
        y="position",
        text="code",
        color="team",
        title="<b>Starting Grid vs. Finishing Position</b>",
        labels={"grid": "Starting Grid", "position": "Finish Position"}
    )
    fig.add_shape(type="line", x0=1, y0=1, x1=20, y1=20, line=dict(color="rgba(255,255,255,0.3)", dash="dash"))
    fig.update_traces(marker=dict(size=12), textposition='top center')
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(**DARK_LAYOUT)
    return fig

def build_telemetry_comparison_chart(telemetry_data: Dict[str, Any]) -> go.Figure:
    """
    Generates speed comparison trace overlay across lap distance.
    """
    d1 = telemetry_data["driver1"]
    d2 = telemetry_data["driver2"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d1["distance"], y=d1["speed"], mode='lines', name=d1["code"], line=dict(color='#E6002B', width=2)))
    fig.add_trace(go.Scatter(x=d2["distance"], y=d2["speed"], mode='lines', name=d2["code"], line=dict(color='#27F4D2', width=2)))

    fig.update_layout(
        title=f"<b>Speed Trace Telemetry: {d1['code']} vs {d2['code']}</b>",
        xaxis_title="Distance (m)",
        yaxis_title="Speed (km/h)",
        **DARK_LAYOUT
    )
    return fig
