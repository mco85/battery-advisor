"""
Kern-Simulation: Battery-Modell, Tagesgang, Monatsprofil.
Direkt portiert aus analyse_15min.py.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from .economics import (
    UserConfig, AnalysisResult, MonthStats, BatteryResult,
    compute_economics, recommend_battery
)


def sim_battery(df: pd.DataFrame, cap_kwh: float, eff: float = 0.90) -> float:
    """
    Stateful DC-Batterie-Simulation auf 15-Min-Daten.
    df muss Spalten 'import_kwh' und 'export_kwh' haben.
    Gibt gespeicherte kWh zurück (= Ersparnis vs. Netzbezug).
    """
    soc = 0.0
    saved = 0.0
    import_arr = df['import_kwh'].to_numpy()
    export_arr = df['export_kwh'].to_numpy()
    for i in range(len(import_arr)):
        # Laden: Solar-Überschuss in Batterie
        charge_possible = min(export_arr[i], (cap_kwh - soc) / eff)
        soc = min(cap_kwh, soc + charge_possible * eff)
        # Entladen: Batterie deckt Netzbezug
        discharge = min(soc, import_arr[i])
        soc -= discharge
        saved += discharge
    return saved


def compute_tagesgang(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    Jahresdurchschnittlicher Tagesgang in Watt (je Stunde 0–23).
    Gibt (import_w, export_w) zurück als dict {hour: watts}.
    """
    hi = df.groupby(df.index.hour)['import_kwh'].mean() * 4000
    he = df.groupby(df.index.hour)['export_kwh'].mean() * 4000
    import_w = {h: float(hi.get(h, 0)) for h in range(24)}
    export_w = {h: float(he.get(h, 0)) for h in range(24)}
    return import_w, export_w


def compute_night_profile(df: pd.DataFrame) -> tuple[float, float, dict]:
    """
    Nacht vs. Tag Segmentierung + stündliches Nacht-Lastprofil.
    Nacht = alle Slots ohne Solareinspeisung (export_kwh == 0).
    Gibt (night_kwh_total, day_kwh_total, night_profile_dict) zurück.
    """
    night_mask = df['export_kwh'] == 0
    night_imp = float(df[night_mask]['import_kwh'].sum())
    day_imp = float(df[~night_mask]['import_kwh'].sum())
    night_h = (df[night_mask]
               .groupby(df[night_mask].index.hour)['import_kwh']
               .mean() * 4000)
    night_profile = {h: float(night_h.get(h, 0)) for h in range(24)}
    return night_imp, day_imp, night_profile


def compute_monthly(df: pd.DataFrame) -> list:
    """Monatliche Detailanalyse. Gibt list[MonthStats] zurück."""
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
        days = mdf.index.normalize().nunique()
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
    """
    Vollständige Simulation auf dem gemergten DataFrame.
    df: DatetimeIndex, Spalten 'import_kwh' + 'export_kwh'.
    """
    total_import = float(df['import_kwh'].sum())
    total_export = float(df['export_kwh'].sum())

    if df.empty or total_import + total_export == 0:
        raise ValueError('Keine gültigen Daten für die Simulation.')

    date_range = (df.index.min().date(), df.index.max().date())

    tagesgang_import, tagesgang_export = compute_tagesgang(df)
    night_kwh, day_kwh, night_profile = compute_night_profile(df)
    monthly = compute_monthly(df)

    battery_results = []
    for cap in config.active_sizes:
        saved = sim_battery(df, cap, config.efficiency)
        result = compute_economics(saved, total_import, cap, config)
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
