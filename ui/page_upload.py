"""
Schritt 1: Dateneingabe — CSV-Upload, Monatswerte, Demo.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ingestion import load_meter_csv, validate_and_merge
from core.manual_estimate import monthly_totals_to_15min

DEMO_IMPORT = Path(__file__).parent.parent / 'data' / 'sample' / 'demo_import.csv'
DEMO_EXPORT = Path(__file__).parent.parent / 'data' / 'sample' / 'demo_export.csv'

MONTH_NAMES = ['Jan', 'Feb', 'Mrz', 'Apr', 'Mai', 'Jun',
               'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']

# Muster-Monatswerte für leere Eingabe (10 kWp Anlage, Mittelschweiz)
DEFAULT_MONTHLY_IMPORT = [420, 380, 310, 250, 190, 160, 150, 165, 210, 290, 370, 420]
DEFAULT_MONTHLY_EXPORT = [250, 380, 700, 950, 1200, 1350, 1400, 1280, 950, 620, 280, 200]


def _show_validation(report):
    """Zeigt Validierungsergebnisse an."""
    if report.errors:
        for e in report.errors:
            st.error(f'Fehler: {e}')
    if report.warnings:
        for w in report.warnings:
            st.warning(w)
    if report.is_valid:
        st.success(
            f'✓ {report.row_count:,} Zeilen erkannt  |  '
            f'{report.date_start} bis {report.date_end}  |  '
            f'Vollständigkeit: {report.coverage_pct:.1f}%'
        )


def render_upload_page():
    st.header('Schritt 1: Zählerdaten eingeben')
    st.markdown(
        'Exportieren Sie die **15-Minuten-Messwerte** aus dem Kundenportal Ihres Netzbetreibers '
        '(CKW, EKZ, BKW, Axpo o.ä.) und laden Sie zwei CSV-Dateien hoch: eine für den '
        '**Netzbezug** und eine für die **Einspeisung** (Rücklieferung).'
    )

    tab_csv, tab_manual, tab_demo = st.tabs([
        '📁 Zählerdaten hochladen', '📋 Monatswerte eingeben', '▶️ Demo-Daten'
    ])

    # ── Tab: CSV-Upload ────────────────────────────────────────────────────
    with tab_csv:
        st.markdown('#### CSV-Dateien hochladen')
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('**Netzbezug** (Energieverbrauch / Bezug vom Netz)')
            f_import = st.file_uploader(
                'Netzbezug CSV', type=['csv', 'txt'],
                key='upload_import', label_visibility='collapsed'
            )
        with col2:
            st.markdown('**Einspeisung** (Rücklieferung / Solar-Überschuss)')
            f_export = st.file_uploader(
                'Einspeisung CSV', type=['csv', 'txt'],
                key='upload_export', label_visibility='collapsed'
            )

        if f_import and f_export:
            with st.spinner('Daten werden geladen und validiert...'):
                try:
                    df_imp = load_meter_csv(f_import, 'import_kwh')
                    df_exp = load_meter_csv(f_export, 'export_kwh')
                    df, report = validate_and_merge(df_imp, df_exp)
                    _show_validation(report)
                    if report.is_valid:
                        st.session_state['df'] = df
                        st.session_state['data_source'] = 'csv'
                        st.session_state['is_estimated'] = False
                        st.session_state['validation_report'] = report
                except ValueError as e:
                    st.error(str(e))
        elif f_import or f_export:
            st.info('Bitte beide Dateien hochladen (Netzbezug + Einspeisung).')

        with st.expander('Welches Format wird erwartet?'):
            st.markdown(
                '**CKW, EKZ, BKW, Axpo:** Export als CSV über das Kundenportal → '
                '"Meine Verbrauchsdaten" → "15-Minuten-Werte" → Zeitraum wählen → Download.\n\n'
                '**Generisch:** CSV mit zwei Spalten: Zeitstempel (`TT.MM.JJJJ HH:MM`) '
                'und Wert in kWh, Semikolon-getrennt. Auch stündliche Daten werden akzeptiert.'
            )

    # ── Tab: Monatswerte ───────────────────────────────────────────────────
    with tab_manual:
        st.markdown('#### Monatswerte aus der Jahresabrechnung')
        st.info(
            'Ohne Smart-Meter-Daten können Sie Monatswerte aus der Jahresabrechnung eingeben. '
            'Die App generiert daraus eine synthetische 15-Min-Kurve. '
            '**Die Ergebnisse sind Schätzungen (±20%).**'
        )

        default_df = pd.DataFrame({
            'Monat': MONTH_NAMES,
            'Netzbezug (kWh)': DEFAULT_MONTHLY_IMPORT,
            'Einspeisung (kWh)': DEFAULT_MONTHLY_EXPORT,
        })

        edited = st.data_editor(
            default_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Monat': st.column_config.TextColumn(disabled=True),
                'Netzbezug (kWh)': st.column_config.NumberColumn(min_value=0, step=10),
                'Einspeisung (kWh)': st.column_config.NumberColumn(min_value=0, step=10),
            },
            key='manual_table',
        )

        year = st.number_input('Analysejahr', value=2025, min_value=2020, max_value=2030, step=1)

        if st.button('Synthetische Daten generieren', key='btn_manual'):
            with st.spinner('Generiere 15-Min-Kurve...'):
                monthly_imp = edited['Netzbezug (kWh)'].tolist()
                monthly_exp = edited['Einspeisung (kWh)'].tolist()
                df = monthly_totals_to_15min(monthly_imp, monthly_exp, year=int(year))
                _, report = validate_and_merge(
                    df[['import_kwh']], df[['export_kwh']]
                )
                st.session_state['df'] = df
                st.session_state['data_source'] = 'manual'
                st.session_state['is_estimated'] = True
                st.session_state['validation_report'] = report
                st.success(
                    f'✓ Synthetische Kurve generiert: {len(df):,} Datenpunkte, '
                    f'Netzbezug {sum(monthly_imp):.0f} kWh, '
                    f'Einspeisung {sum(monthly_exp):.0f} kWh'
                )

    # ── Tab: Demo ─────────────────────────────────────────────────────────
    with tab_demo:
        st.markdown('#### Demo-Daten: Musteranlage 10 kWp, Mittelschweiz')
        st.info(
            'Laden Sie anonymisierte Beispieldaten einer realen Solaranlage (10 kWp, 22.5 MWh/Jahr). '
            'Ideal um die App kennenzulernen.'
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(
                '| Kennzahl | Wert |\n|---|---|\n'
                '| Solarproduktion | ~22.500 kWh/Jahr |\n'
                '| Netzbezug | ~4.000 kWh/Jahr |\n'
                '| Einspeisung | ~12.500 kWh/Jahr |\n'
                '| Messpunkte | 35.040 (15-Min, 2025) |'
            )
        with col2:
            if st.button('Demo starten', type='primary', key='btn_demo'):
                if DEMO_IMPORT.exists() and DEMO_EXPORT.exists():
                    with st.spinner('Lade Demo-Daten...'):
                        df_imp = load_meter_csv(str(DEMO_IMPORT), 'import_kwh')
                        df_exp = load_meter_csv(str(DEMO_EXPORT), 'export_kwh')
                        df, report = validate_and_merge(df_imp, df_exp)
                        st.session_state['df'] = df
                        st.session_state['data_source'] = 'demo'
                        st.session_state['is_estimated'] = False
                        st.session_state['validation_report'] = report
                        st.success('✓ Demo-Daten geladen')
                else:
                    st.error('Demo-Daten nicht gefunden. Bitte CSV-Dateien hochladen.')

    # ── Weiter-Button ──────────────────────────────────────────────────────
    st.divider()
    col_back, col_fwd = st.columns([1, 1])
    with col_fwd:
        has_data = st.session_state.get('df') is not None
        if st.button(
            'Weiter: Preise konfigurieren →',
            disabled=not has_data,
            type='primary' if has_data else 'secondary',
            use_container_width=True,
        ):
            st.session_state['step'] = 2
            st.rerun()
        if not has_data:
            st.caption('Bitte zuerst Daten laden.')
