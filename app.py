"""
Batteriespeicher-Berater — Streamlit Web-App
Hauptdatei: Session-State, Routing, Layout.
"""
import streamlit as st
from pathlib import Path
import sys

# Projekt-Root zum Suchpfad hinzufügen
sys.path.insert(0, str(Path(__file__).parent))

# ── Seiten-Konfiguration ────────────────────────────────────────────────────
st.set_page_config(
    page_title='Batteriespeicher-Berater',
    page_icon='🔋',
    layout='wide',
    initial_sidebar_state='collapsed',
)

# ── Session-State initialisieren ─────────────────────────────────────────────
if 'step' not in st.session_state:
    st.session_state['step'] = 1
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'config' not in st.session_state:
    st.session_state['config'] = None
if 'data_source' not in st.session_state:
    st.session_state['data_source'] = None
if 'is_estimated' not in st.session_state:
    st.session_state['is_estimated'] = False

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="color:#1a3a5c;margin-bottom:0">🔋 Batteriespeicher-Berater</h1>'
    '<p style="color:#555;margin-top:4px">Lohnt sich ein Heimspeicher für Ihre Solaranlage? '
    'Laden Sie Ihre Zählerdaten hoch und erhalten Sie eine datenbasierte Analyse.</p>',
    unsafe_allow_html=True,
)

# ── Fortschrittsbalken ───────────────────────────────────────────────────────
step = st.session_state['step']
STEPS = ['Daten eingeben', 'Konfigurieren', 'Ergebnisse']

cols = st.columns(len(STEPS))
for i, (col, label) in enumerate(zip(cols, STEPS), start=1):
    with col:
        active = i == step
        done = i < step
        color = '#1a6b3c' if done else '#1a3a5c' if active else '#ccc'
        icon = '✓' if done else str(i)
        st.markdown(
            f'<div style="text-align:center;padding:6px 0">'
            f'<span style="background:{color};color:white;border-radius:50%;'
            f'padding:2px 9px;font-weight:bold;font-size:0.85em">{icon}</span> '
            f'<span style="color:{color};font-weight:{"bold" if active else "normal"}'
            f';font-size:0.9em">{label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown('<hr style="margin:8px 0 20px 0">', unsafe_allow_html=True)

# ── Routing ───────────────────────────────────────────────────────────────────
if step == 1:
    from ui.page_upload import render_upload_page
    render_upload_page()
elif step == 2:
    from ui.page_config import render_config_page
    render_config_page()
elif step == 3:
    from ui.page_results import render_results_page
    render_results_page()

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    '<hr style="margin-top:40px"><p style="text-align:center;color:#aaa;font-size:0.8em">'
    'Simulation: stateful DC-Batterie · 15-Min-Auflösung · Schweizer Markt · '
    'Alle Angaben ohne Gewähr</p>',
    unsafe_allow_html=True,
)
