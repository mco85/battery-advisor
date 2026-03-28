"""
Schritt 3: Ergebnisse — Charts, Tabellen, PDF-Download.
"""
import streamlit as st
import pandas as pd

from core.simulation import run_full_simulation
from charts.tagesgang import tagesgang_chart
from charts.monthly import monthly_chart
from charts.battery_comparison import battery_comparison_chart


def _amort_badge(years: float) -> str:
    if years < 10:
        return f'🟢 {years:.1f} J'
    elif years < 15:
        return f'🟡 {years:.1f} J'
    else:
        return f'🔴 {years:.1f} J'


@st.cache_data(show_spinner=False)
def _cached_simulation(_df_csv: str, config_dict: dict):
    """Cached simulation. _df_csv prefix underscore = unhashable-safe for st.cache_data."""
    import io
    df = pd.read_csv(io.StringIO(_df_csv), index_col=0, parse_dates=True)
    from core.economics import UserConfig
    config = UserConfig(**config_dict)
    return run_full_simulation(df, config)


def render_results_page():
    df = st.session_state.get('df')
    config = st.session_state.get('config')

    if df is None or config is None:
        st.error('Keine Daten vorhanden. Bitte von vorne starten.')
        if st.button('← Zurück zu Schritt 1'):
            st.session_state['step'] = 1
            st.rerun()
        return

    # Simulation mit Cache (serialisiert df + config für stabilen Cache-Key)
    with st.spinner('Simulation läuft...'):
        try:
            config_dict = {
                'grid_price': config.grid_price,
                'feedin_price': config.feedin_price,
                'battery_sizes': config.battery_sizes,
                'invest_costs': config.invest_costs,
                'efficiency': config.efficiency,
            }
            result = _cached_simulation(df.to_csv(), config_dict)
            if st.session_state.get('is_estimated'):
                result.is_estimated = True
        except ValueError as e:
            st.error(f'Fehler bei der Simulation: {e}')
            return

    st.header('Schritt 3: Ihre Analyse')

    if result.is_estimated:
        st.warning(
            'Diese Analyse basiert auf **synthetisch generierten Daten** (Monatswerte). '
            'Für präzise Ergebnisse empfehlen wir den Upload der 15-Min-Zählerdaten.'
        )

    if st.session_state.get('data_source') == 'demo':
        st.info('Sie verwenden **Demo-Daten** (Musteranlage 10 kWp, Mittelschweiz).')

    # ── Empfehlungs-Callout ─────────────────────────────────────────────────
    rec = result.recommendation
    if rec.verdict == 'buy':
        st.success(f'**Kaufempfehlung:** {rec.reason}')
    elif rec.verdict == 'wait':
        st.warning(f'**Abwarten empfohlen:** {rec.reason}')
    else:
        st.error(f'**Aktuell nicht rentabel:** {rec.reason}')

    st.divider()

    # ── Metrikkarten ─────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric('Jahres-Netzbezug', f'{result.total_import_kwh:.0f} kWh')
    with m2:
        st.metric('Jahres-Einspeisung', f'{result.total_export_kwh:.0f} kWh')
    with m3:
        net = result.net_cost_chf
        st.metric('Netto-Stromkosten', f'CHF {net:.0f}/Jahr')
    with m4:
        net_benefit = config.net_benefit * 100
        st.metric('Nettovorteil', f'{net_benefit:.1f} Rp./kWh')

    st.divider()

    # ── Batterie-Simulation ───────────────────────────────────────────────────
    st.subheader('Batterie-Simulation')

    sim_data = []
    for br in result.battery_results:
        sim_data.append({
            'Kapazität': f'{br.capacity:.0f} kWh',
            'Gespart/Jahr': f'{br.saved_kwh:.0f} kWh',
            'Reduktion': f'{br.reduction_pct:.1f}%',
            'Einsparung': f'CHF {br.chf_per_year:.0f}',
            'Invest netto': f'CHF {br.invest_chf:.0f}',
            'Amortisation': _amort_badge(br.amort_years),
        })

    fig_bat = None  # Init before conditional block to avoid NameError
    if sim_data:
        sim_df = pd.DataFrame(sim_data)
        best_idx = next(
            (i for i, r in enumerate(result.battery_results)
             if r.capacity == rec.best_size), None
        )
        st.dataframe(
            sim_df,
            use_container_width=True,
            hide_index=True,
        )
        if best_idx is not None:
            best = result.battery_results[best_idx]
            st.caption(
                f'Empfohlen: **{best.capacity:.0f} kWh** — '
                f'beste Amortisation bei {best.amort_years:.1f} Jahren'
            )

    # Batterie-Vergleichs-Chart
    if result.battery_results:
        fig_bat = battery_comparison_chart(result.battery_results)
        st.plotly_chart(fig_bat, use_container_width=True)

    st.divider()

    # ── Tagesgang ─────────────────────────────────────────────────────────────
    st.subheader('Tagesgang — Jahresdurchschnitt')
    fig_tg = tagesgang_chart(result.tagesgang_import, result.tagesgang_export)
    st.plotly_chart(fig_tg, use_container_width=True)

    # ── Monatliche Analyse ─────────────────────────────────────────────────────
    st.subheader('Monatliche Energiebilanz')
    fig_mon = monthly_chart(result.monthly_breakdown)
    st.plotly_chart(fig_mon, use_container_width=True)

    # Monatstabelle
    with st.expander('Monatstabelle anzeigen'):
        month_data = [{
            'Monat': m.name,
            'Bezug/Tag': f'{m.import_per_day:.2f} kWh',
            'Einsp./Tag': f'{m.export_per_day:.2f} kWh',
            'Nacht kWh': f'{m.night_per_day:.2f}',
            'Tag kWh': f'{m.day_per_day:.2f}',
            'Peak kW': f'{m.peak_kw:.1f}',
        } for m in result.monthly_breakdown]
        st.dataframe(pd.DataFrame(month_data), use_container_width=True, hide_index=True)

    st.divider()

    # ── PDF-Download ───────────────────────────────────────────────────────────
    st.subheader('Bericht herunterladen')
    col_pdf, col_new = st.columns([2, 1])
    with col_pdf:
        if st.button('PDF-Bericht generieren', type='primary'):
            with st.spinner('Bericht wird erstellt...'):
                try:
                    from pdf.report import generate_report
                    chart_figs = {
                        'tagesgang': fig_tg,
                        'monthly': fig_mon,
                        'battery': fig_bat,
                    }
                    pdf_bytes = generate_report(result, chart_figs)
                    st.download_button(
                        label='📄 PDF herunterladen',
                        data=pdf_bytes,
                        file_name='batteriespeicher-analyse.pdf',
                        mime='application/pdf',
                    )
                except Exception as e:
                    st.error(f'PDF-Generierung fehlgeschlagen: {e}')

    with col_new:
        if st.button('Neue Analyse starten', use_container_width=True):
            for key in ['df', 'config', 'data_source', 'is_estimated']:
                st.session_state.pop(key, None)
            st.session_state['step'] = 1
            st.rerun()
