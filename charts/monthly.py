"""
Monatliche Analyse: Gestapeltes Balken-Chart mit Solar-Peak-Linie.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots


MONTH_NAMES = ['Jan', 'Feb', 'Mrz', 'Apr', 'Mai', 'Jun',
               'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']


def monthly_chart(monthly_breakdown: list) -> go.Figure:
    """
    monthly_breakdown: list[MonthStats]
    """
    months = [m.name for m in monthly_breakdown]
    night = [m.night_per_day for m in monthly_breakdown]
    day_imp = [m.day_per_day for m in monthly_breakdown]
    export = [m.export_per_day for m in monthly_breakdown]
    peak = [m.peak_kw for m in monthly_breakdown]

    fig = make_subplots(specs=[[{'secondary_y': True}]])

    fig.add_trace(go.Bar(
        name='Nacht-Bezug (kWh/Tag)',
        x=months, y=night,
        marker_color='#1a3a5c',
        hovertemplate='%{x}: %{y:.2f} kWh/Tag<extra>Nacht-Bezug</extra>',
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        name='Tag-Bezug trotz Solar (kWh/Tag)',
        x=months, y=day_imp,
        marker_color='#5b8fb9',
        hovertemplate='%{x}: %{y:.2f} kWh/Tag<extra>Tag-Bezug</extra>',
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        name='Einspeisung (kWh/Tag)',
        x=months, y=export,
        marker_color='#1a6b3c',
        hovertemplate='%{x}: %{y:.2f} kWh/Tag<extra>Einspeisung</extra>',
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        name='Peak-Einspeisung (kW)',
        x=months, y=peak,
        mode='lines+markers',
        line=dict(color='#e67e22', width=2),
        marker=dict(size=6),
        hovertemplate='%{x}: %{y:.1f} kW<extra>Peak</extra>',
    ), secondary_y=True)

    fig.update_layout(
        barmode='stack',
        title='Monatliche Energiebilanz',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        margin=dict(t=60, b=40, l=60, r=60),
        height=380,
    )
    fig.update_yaxes(title_text='kWh/Tag', secondary_y=False)
    fig.update_yaxes(title_text='Peak kW', secondary_y=True)
    return fig
