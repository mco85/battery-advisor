"""
Batterie-Vergleichs-Chart: CHF/Jahr (Balken) + Amortisation (Linie).
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def battery_comparison_chart(battery_results: list) -> go.Figure:
    """
    battery_results: list[BatteryResult]
    """
    caps = [f'{r.capacity:.0f} kWh' for r in battery_results]
    chf = [r.chf_per_year for r in battery_results]
    amort = [min(r.amort_years, 30) for r in battery_results]  # Cap bei 30J für Lesbarkeit

    # Farbe nach Amortisation
    colors = []
    for r in battery_results:
        if r.amort_years < 10:
            colors.append('#1a6b3c')   # grün
        elif r.amort_years < 15:
            colors.append('#e67e22')   # orange
        else:
            colors.append('#c0392b')   # rot

    fig = make_subplots(specs=[[{'secondary_y': True}]])

    fig.add_trace(go.Bar(
        name='Einsparung CHF/Jahr',
        x=caps, y=chf,
        marker_color=colors,
        hovertemplate='%{x}: %{y:.0f} CHF/Jahr<extra>Einsparung</extra>',
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        name='Amortisation (Jahre)',
        x=caps, y=amort,
        mode='lines+markers',
        line=dict(color='#555', width=2),
        marker=dict(size=8, color=colors, line=dict(color='white', width=1)),
        hovertemplate='%{x}: %{y:.1f} Jahre<extra>Amortisation</extra>',
    ), secondary_y=True)

    # 10-Jahres-Garantiegrenze
    fig.add_hline(
        y=10, line_dash='dash', line_color='#c0392b',
        annotation_text='10 J. Garantiegrenze',
        annotation_position='top right',
        secondary_y=True,
    )

    fig.update_layout(
        title='Batterie-Vergleich: Einsparung & Amortisation',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        margin=dict(t=60, b=40, l=60, r=60),
        height=350,
    )
    fig.update_yaxes(title_text='CHF/Jahr', secondary_y=False)
    fig.update_yaxes(title_text='Jahre', secondary_y=True, range=[0, 32])
    return fig
