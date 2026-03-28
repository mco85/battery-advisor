"""
Kern-Simulation: Battery-Modell, Tagesgang, Monatsprofil.

Physik-Modell:
- Split-Effizienz: Lade-Verlust (sqrt(eff)) + Entlade-Verlust (sqrt(eff))
- Standby-Verbrauch: Dauerlast Inverter/BMS, wird aus SOC oder Netz gedeckt
- Mindestleistung: Unter Threshold keine Aktivierung
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from .economics import (
    UserConfig, AnalysisResult, MonthStats,
    compute_economics, recommend_battery
)

SLOT_HOURS = 0.25  # 15-Min-Slot = 0.25 Stunden


def sim_battery(
    df: pd.DataFrame,
    cap_kwh: float,
    config: UserConfig,
) -> tuple[float, float]:
    """
    Stateful DC-Batterie-Simulation auf 15-Min-Daten.

    Modelliert:
    - Split-Effizienz (charge_eff * discharge_eff = round-trip)
    - Standby-Verbrauch (Dauerlast aus SOC oder Netz)
    - Mindest-Threshold (Laden/Entladen nur über min_power_watts)

    Returns: (saved_kwh, standby_loss_kwh)
    """
    charge_eff = config.charge_eff
    discharge_eff = config.discharge_eff
    standby_kwh_per_slot = config.standby_watts / 1000 * SLOT_HOURS
    min_kwh_per_slot = config.min_power_watts / 1000 * SLOT_HOURS

    soc = 0.0
    saved = 0.0
    standby_from_grid = 0.0

    import_arr = df['import_kwh'].to_numpy()
    export_arr = df['export_kwh'].to_numpy()

    for i in range(len(import_arr)):
        # 1. Standby-Verbrauch: aus SOC wenn möglich, sonst Netz
        if soc >= standby_kwh_per_slot:
            soc -= standby_kwh_per_slot
        else:
            standby_from_grid += standby_kwh_per_slot - soc
            soc = 0.0

        # 2. Laden: Solar-Überschuss → Batterie (nur über Threshold)
        avail_export = export_arr[i]
        if avail_export >= min_kwh_per_slot:
            headroom = (cap_kwh - soc) / charge_eff
            charge_energy = min(avail_export, headroom)
            soc = min(cap_kwh, soc + charge_energy * charge_eff)

        # 3. Entladen: Batterie → Haus (nur über Threshold)
        demand = import_arr[i]
        if demand >= min_kwh_per_slot and soc > 0:
            max_discharge = soc * discharge_eff
            discharge = min(max_discharge, demand)
            soc -= discharge / discharge_eff
            saved += discharge

    return saved, standby_from_grid


def compute_tagesgang(df: pd.DataFrame) -> tuple[dict, dict]:
    """Jahresdurchschnittlicher Tagesgang in Watt (je Stunde 0-23)."""
    hi = df.groupby(df.index.hour)['import_kwh'].mean() * 4000
    he = df.groupby(df.index.hour)['export_kwh'].mean() * 4000
    import_w = {h: float(hi.get(h, 0)) for h in range(24)}
    export_w = {h: float(he.get(h, 0)) for h in range(24)}
    return import_w, export_w


def compute_night_profile(df: pd.DataFrame) -> tuple[float, float, dict]:
    """Nacht vs. Tag Segmentierung + stündliches Nacht-Lastprofil."""
    night_mask = df['export_kwh'] == 0
    night_imp = float(df[night_mask]['import_kwh'].sum())
    day_imp = float(df[~night_mask]['import_kwh'].sum())
    night_h = (df[night_mask]
               .groupby(df[night_mask].index.hour)['import_kwh']
               .mean() * 4000)
    night_profile = {h: float(night_h.get(h, 0)) for h in range(24)}
    return night_imp, day_imp, night_profile


def compute_monthly(df: pd.DataFrame) -> list:
    """Monatliche Detailanalyse."""
    months = []
    for m in range(1, 13):
        mdf = df[df.index.month == m]
        if mdf.empty:
            months.append(MonthStats(
                month=m,
                import_per_day=0, export_per_day=0,
                night_per_day=0, day_per_day=0, peak_kw=0
            ))
            continue
        days = max(mdf.index.normalize().nunique(), 1)
        months.append(MonthStats(
            month=m,
            import_per_day=float(mdf['import_kwh'].sum() / days),
            export_per_day=float(mdf['export_kwh'].sum() / days),
            night_per_day=float(mdf[mdf['export_kwh'] == 0]['import_kwh'].sum() / days),
            day_per_day=float(mdf[mdf['export_kwh'] > 0]['import_kwh'].sum() / days),
            peak_kw=float(mdf['export_kwh'].max() * 4),
        ))
    return months


def run_full_simulation(df: pd.DataFrame, config: UserConfig) -> AnalysisResult:
    """Vollständige Simulation auf dem gemergten DataFrame."""
    total_import = float(df['import_kwh'].sum())
    total_export = float(df['export_kwh'].sum())

    if df.empty or total_import + total_export == 0:
        raise ValueError('Keine gueltigen Daten fuer die Simulation.')

    date_range = (df.index.min().date(), df.index.max().date())

    tagesgang_import, tagesgang_export = compute_tagesgang(df)
    night_kwh, day_kwh, night_profile = compute_night_profile(df)
    monthly = compute_monthly(df)

    battery_results = []
    for cap in config.active_sizes:
        saved, standby_loss = sim_battery(df, cap, config)
        result = compute_economics(saved, standby_loss, total_import, cap, config)
        battery_results.append(result)

    recommendation = recommend_battery(battery_results, config)

    return AnalysisResult(
        total_import_kwh=total_import,
        total_export_kwh=total_export,
        date_range=date_range,
        tagesgang_import=tagesgang_import,
        tagesgang_export=tagesgang_export,
        night_import_kwh=night_kwh,
        day_import_kwh=day_kwh,
        night_profile=night_profile,
        monthly_breakdown=monthly,
        battery_results=battery_results,
        recommendation=recommendation,
        config=config,
    )
