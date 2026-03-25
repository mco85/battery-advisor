"""
Synthethische 15-Min-Kurve aus 12 Monatswerten.
Für Nutzer ohne Smart-Meter-Daten.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

# Typisches Tages-Lastprofil (normalisiert, Summe = 1.0)
# Index = Stunde 0–23, Werte = relativer Anteil des Tagesverbrauchs
_LOAD_PROFILE_HOURLY = np.array([
    0.030, 0.025, 0.022, 0.020, 0.020, 0.025,  # 00–05h Grundlast Nacht
    0.035, 0.050, 0.060, 0.055, 0.050, 0.050,  # 06–11h Morgen/Mittag
    0.052, 0.050, 0.048, 0.048, 0.050, 0.058,  # 12–17h Nachmittag
    0.070, 0.075, 0.070, 0.060, 0.050, 0.040,  # 18–23h Abend
])
_LOAD_PROFILE_HOURLY /= _LOAD_PROFILE_HOURLY.sum()

# Saisonales Solar-Tagesprofil (Glockenkurve, Peak = Sonnenhöchststand)
# Parameter: (peak_hour, width_hours) je Monat
_SOLAR_PARAMS = [
    (12.0, 3.0),   # Jan
    (12.0, 3.5),   # Feb
    (12.0, 4.5),   # Mrz
    (12.5, 5.5),   # Apr
    (13.0, 6.5),   # Mai
    (13.0, 7.0),   # Jun
    (13.0, 7.0),   # Jul
    (13.0, 6.5),   # Aug
    (12.5, 5.5),   # Sep
    (12.0, 4.5),   # Okt
    (12.0, 3.5),   # Nov
    (12.0, 3.0),   # Dez
]


def _solar_day_profile(month: int, steps_per_hour: int = 4) -> np.ndarray:
    """Normalisiertes 15-Min-Solar-Tagesprofil für einen Monat."""
    peak_h, width_h = _SOLAR_PARAMS[month - 1]
    n = 24 * steps_per_hour
    t = np.linspace(0, 24, n, endpoint=False)
    sigma = width_h / 2.35  # FWHM → sigma
    profile = np.exp(-0.5 * ((t - peak_h) / sigma) ** 2)
    profile[profile < 0.01] = 0  # Nacht = 0
    total = profile.sum()
    if total > 0:
        profile /= total
    return profile


def monthly_totals_to_15min(
    monthly_import: list[float],
    monthly_export: list[float],
    year: int = 2025,
    noise_level: float = 0.15,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Erzeugt synthetischen 15-Min-DataFrame aus 12 Monatswerten.

    monthly_import: Liste von 12 Werten (kWh/Monat Netzbezug)
    monthly_export: Liste von 12 Werten (kWh/Monat Einspeisung)
    noise_level: Tag-zu-Tag Zufallsvariation (0.15 = ±15%)

    Gibt DataFrame mit DatetimeIndex (15-Min-Auflösung, volles Jahr) zurück,
    Spalten 'import_kwh' und 'export_kwh'.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range(f'{year}-01-01', f'{year}-12-31 23:45', freq='15min')
    df = pd.DataFrame(0.0, index=index, columns=['import_kwh', 'export_kwh'])

    for m in range(1, 13):
        mask = df.index.month == m
        month_idx = df.index[mask]
        days = sorted(set(month_idx.date))
        n_days = len(days)

        imp_total = monthly_import[m - 1]
        exp_total = monthly_export[m - 1]
        imp_per_day = imp_total / n_days if n_days > 0 else 0
        exp_per_day = exp_total / n_days if n_days > 0 else 0

        solar_profile = _solar_day_profile(m)  # 96 Werte

        for d, day in enumerate(days):
            day_mask = df.index.date == day
            day_slots = df.index[day_mask]
            n_slots = len(day_slots)
            if n_slots == 0:
                continue

            # Tages-Variation
            imp_noise = rng.uniform(1 - noise_level, 1 + noise_level)
            exp_noise = rng.uniform(1 - noise_level, 1 + noise_level)

            # Import-Profil (Lastprofil, auf 96 Slots interpoliert)
            load_96 = np.repeat(_LOAD_PROFILE_HOURLY, 4)  # 24h × 4 = 96 Slots
            imp_day = imp_per_day * imp_noise * load_96[:n_slots]
            imp_day = imp_day / imp_day.sum() * imp_per_day * imp_noise if imp_day.sum() > 0 else imp_day

            # Export-Profil (Solar-Glockenkurve)
            exp_day = exp_per_day * exp_noise * solar_profile[:n_slots]
            if exp_day.sum() > 0:
                exp_day = exp_day / exp_day.sum() * exp_per_day * exp_noise

            df.loc[day_mask, 'import_kwh'] = np.maximum(0, imp_day)
            df.loc[day_mask, 'export_kwh'] = np.maximum(0, exp_day)

    return df
