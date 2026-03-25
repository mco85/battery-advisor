"""
Tagesgang-Chart: stündlicher Bezug vs. Einspeisung (Area-Chart).
"""
import plotly.graph_objects as go


BLUE = '#1a3a5c'
GREEN = '#1a6b3c'
BLUE_FILL = 'rgba(26,58,92,0.25)'
GREEN_FILL = 'rgba(26,107,60,0.25)'


def tagesgang_chart(
    import_w: dict,
    export_w: dict,
    title: str = 'Tagesgang — Jahresdurchschnitt',
) -> go.Figure:
    """
    import_w, export_w: dict {Stunde (int) → Watt (float)}
    """
    hours = list(range(24))
    imp = [import_w.get(h, 0) for h in hours]
    exp = [export_w.get(h, 0) for h in hours]
    saldo = [e - i for e, i in zip(exp, imp)]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=hours, y=exp,
        name='Einspeisung (Solar)',
        fill='tozeroy',
        fillcolor=GREEN_FILL,
        line=dict(color=GREEN, width=2),
        hovertemplate='%{x}h: %{y:.0f} W<extra>Einspeisung</extra>',
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=imp,
        name='Netzbezug',
        fill='tozeroy',
        fillcolor=BLUE_FILL,
        line=dict(color=BLUE, width=2),
        hovertemplate='%{x}h: %{y:.0f} W<extra>Netzbezug</extra>',
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=saldo,
        name='Saldo (+ = Überschuss)',
        line=dict(color='#888', width=1, dash='dot'),
        hovertemplate='%{x}h: %{y:+.0f} W<extra>Saldo</extra>',
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(
            title='Stunde',
            tickmode='linear', dtick=2,
            tickvals=list(range(0, 24, 2)),
            ticktext=[f'{h}h' for h in range(0, 24, 2)],
        ),
        yaxis=dict(title='Leistung (W)'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        margin=dict(t=60, b=40, l=60, r=20),
        height=350,
    )
    return fig


def night_profile_chart(night_profile: dict) -> go.Figure:
    """Horizontales Balken-Chart: Nachtlast-Profil je Stunde."""
    hours = [h for h in range(24) if night_profile.get(h, 0) > 1]
    values = [night_profile.get(h, 0) for h in hours]
    labels = [f'{h:02d}h' for h in hours]

    fig = go.Figure(go.Bar(
        x=values, y=labels,
        orientation='h',
        marker_color=BLUE,
        hovertemplate='%{y}: %{x:.0f} W<extra></extra>',
    ))
    fig.update_layout(
        title='Nachtlast-Profil (Stunden ohne Solar)',
        xaxis=dict(title='Leistung (W)'),
        yaxis=dict(autorange='reversed'),
        margin=dict(t=50, b=40, l=50, r=20),
        height=350,
    )
    return fig
