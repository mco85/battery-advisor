"""
Schritt 2: Preise & Batteriekonfiguration.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.economics import UserConfig


def render_config_page():
    st.header('Schritt 2: Strompreise & Batteriegrössen')

    col_left, col_right = st.columns([3, 2])

    # ── Strompreise ─────────────────────────────────────────────────────────
    with col_left:
        st.subheader('Strompreise')
        grid_price = st.number_input(
            'Bezugspreis (Rp./kWh, inkl. MwSt.)',
            value=27.2, min_value=5.0, max_value=80.0, step=0.5,
            format='%.1f',
            help='Gesamtpreis für Strom aus dem Netz: Energie + Netznutzung + Abgaben + MwSt.',
        )
        feedin_price = st.number_input(
            'Einspeisevergütung (Rp./kWh)',
            value=8.0, min_value=0.0, max_value=30.0, step=0.5,
            format='%.1f',
            help='Vergütung für ins Netz eingespeisten Solar-Strom (Mindestansatz + ggf. HKN-Bonus).',
        )

    with col_right:
        st.subheader('Nettovorteil')
        net = (grid_price - feedin_price)
        color = '#1a6b3c' if net > 15 else '#e67e22' if net > 10 else '#c0392b'
        st.markdown(
            f'<div style="background:#f0f4f8;padding:12px;border-radius:8px;text-align:center">'
            f'<div style="font-size:0.85em;color:#555">pro gespartem kWh</div>'
            f'<div style="font-size:2em;font-weight:bold;color:{color}">{net:.1f} Rp.</div>'
            f'<div style="font-size:0.8em;color:#888">{grid_price:.1f} − {feedin_price:.1f} Rp.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Tipp: Preis-Quellen ─────────────────────────────────────────────────
    with st.expander('Wo finde ich meinen Strompreis?'):
        st.markdown(
            '- **CKW (Pfaffnau LU):** 27,2 Rp./kWh (2026)\n'
            '- **EKZ (Zürich):** ca. 24–28 Rp./kWh\n'
            '- **BKW (Bern):** ca. 25–30 Rp./kWh\n'
            '- **Axpo/Aargau:** ca. 23–28 Rp./kWh\n'
            '- **Einspeisevergütung:** 6–10 Rp./kWh (Mindestansatz 6 Rp. + ggf. HKN-Bonus)\n\n'
            'Genauer Preis: Stromrechnung oder [elcom.admin.ch](https://www.elcom.admin.ch)'
        )

    st.divider()

    # ── Batteriegrössen ─────────────────────────────────────────────────────
    st.subheader('Batteriegrössen & Investitionskosten')
    st.caption(
        'Investitionskosten inkl. Hybrid-Wechselrichter und Installation, '
        'netto nach Steuerabzug (~30% Grenzsteuersatz in CH).'
    )

    default_batteries = pd.DataFrame({
        'Aktiv': [True, True, True, True],
        'Kapazität (kWh)': [5.0, 7.5, 10.0, 15.0],
        'Invest netto (CHF)': [4550, 5600, 6650, 9100],
    })

    battery_df = st.data_editor(
        default_batteries,
        use_container_width=True,
        hide_index=True,
        num_rows='dynamic',
        column_config={
            'Aktiv': st.column_config.CheckboxColumn(),
            'Kapazität (kWh)': st.column_config.NumberColumn(min_value=1.0, max_value=50.0, step=0.5, format='%.1f'),
            'Invest netto (CHF)': st.column_config.NumberColumn(min_value=500, max_value=50000, step=100),
        },
        key='battery_table',
    )

    # ── Erweitert ───────────────────────────────────────────────────────────
    with st.expander('Erweiterte Einstellungen'):
        efficiency = st.slider(
            'Batterie-Wirkungsgrad (Round-Trip %)',
            min_value=80, max_value=98, value=90, step=1,
            help='Typisch: DC-Batterie 88–95%, AC-Batterie 80–90%.',
        )

    # ── Config zusammenstellen ──────────────────────────────────────────────
    active_rows = battery_df[battery_df['Aktiv'] == True]
    sizes = active_rows['Kapazität (kWh)'].tolist()
    costs = dict(zip(active_rows['Kapazität (kWh)'].tolist(),
                     active_rows['Invest netto (CHF)'].tolist()))

    config = UserConfig(
        grid_price=grid_price / 100,
        feedin_price=feedin_price / 100,
        battery_sizes=sizes,
        invest_costs=costs,
        efficiency=efficiency / 100,
    )

    # ── Navigation ──────────────────────────────────────────────────────────
    st.divider()
    col_back, col_fwd = st.columns([1, 1])
    with col_back:
        if st.button('← Zurück', use_container_width=True):
            st.session_state['step'] = 1
            st.rerun()
    with col_fwd:
        if st.button('Analysieren →', type='primary', use_container_width=True):
            if not sizes:
                st.error('Bitte mindestens eine Batteriegrösse aktivieren.')
            else:
                st.session_state['config'] = config
                st.session_state['step'] = 3
                st.rerun()
