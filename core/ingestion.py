"""
CSV-Ingestion: Format-Detection, Parsing, Validierung.
Unterstützt CKW-Format (skiprows=10) und generisches 2-Spalten-Format.
"""
from __future__ import annotations
import io
from dataclasses import dataclass
import pandas as pd


@dataclass
class FormatSpec:
    skiprows: int
    sep: str
    datetime_fmt: str
    encoding: str = 'utf-8-sig'


@dataclass
class ValidationReport:
    row_count: int
    date_start: str
    date_end: str
    resolution_min: int      # erkannte Auflösung in Minuten
    gap_count: int           # fehlende Zeitslots
    coverage_pct: float      # Datenvollständigkeit in %
    warnings: list           # list[str]
    errors: list             # list[str]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


# Bekannte Formate
_FORMATS = [
    # CKW / Schweizer Utilities: 10-Zeilen-Header
    FormatSpec(skiprows=10, sep=';', datetime_fmt='%d.%m.%Y %H:%M', encoding='utf-8-sig'),
    # Generisch: 1-Zeilen-Header
    FormatSpec(skiprows=1, sep=';', datetime_fmt='%d.%m.%Y %H:%M', encoding='utf-8-sig'),
    FormatSpec(skiprows=1, sep=';', datetime_fmt='%Y-%m-%d %H:%M', encoding='utf-8-sig'),
    FormatSpec(skiprows=1, sep=',', datetime_fmt='%Y-%m-%d %H:%M', encoding='utf-8'),
]


def _try_parse(buf: bytes, fmt: FormatSpec, col: str) -> pd.DataFrame | None:
    """Versucht einen Buffer mit gegebenem FormatSpec zu parsen."""
    try:
        raw = pd.read_csv(
            io.BytesIO(buf),
            sep=fmt.sep,
            skiprows=fmt.skiprows,
            encoding=fmt.encoding,
            header=None,
            names=['ts', col],
            on_bad_lines='skip',
        )
        # Filtere Footer-Zeilen (CKW: 'Zeitraum', 'Total')
        raw = raw[~raw['ts'].astype(str).str.startswith(
            ('Zeitraum', 'Total', '#'), na=True
        )].copy()
        raw['ts'] = pd.to_datetime(raw['ts'], format=fmt.datetime_fmt, errors='coerce')
        raw = raw.dropna(subset=['ts'])
        if len(raw) < 48:   # Mindestens 2 Tage = 192 Slots (15 Min) oder 48 (stündl.)
            return None
        raw = raw.set_index('ts').sort_index()
        raw[col] = pd.to_numeric(raw[col], errors='coerce').fillna(0).abs()
        return raw
    except Exception:
        return None


def load_meter_csv(uploaded_file, column_name: str) -> pd.DataFrame:
    """
    Lädt eine Zähler-CSV (Import oder Export) und gibt einen
    DataFrame mit DatetimeIndex und einer Spalte zurück.

    uploaded_file: st.UploadedFile, Pfad-String oder bytes-Buffer.
    column_name: 'import_kwh' oder 'export_kwh'
    """
    if isinstance(uploaded_file, (str, bytes)):
        if isinstance(uploaded_file, str):
            with open(uploaded_file, 'rb') as f:
                buf = f.read()
        else:
            buf = uploaded_file
    else:
        buf = uploaded_file.read()
        uploaded_file.seek(0)

    for fmt in _FORMATS:
        df = _try_parse(buf, fmt, column_name)
        if df is not None:
            return df

    raise ValueError(
        'Format nicht erkannt. Bitte exportieren Sie die Daten als CSV '
        'mit Zeitstempel (TT.MM.JJJJ HH:MM) und kWh-Werten. '
        'Unterstützt: CKW, EKZ, BKW, Axpo und kompatible Formate.'
    )


def validate_and_merge(
    df_import: pd.DataFrame,
    df_export: pd.DataFrame,
) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Merged Import und Export, prüft Datenqualität.
    Gibt (merged_df, ValidationReport) zurück.
    """
    warnings = []
    errors = []

    # Outer join
    df = df_import.join(df_export, how='outer').fillna(0)

    # Erkennung der Auflösung
    if len(df) > 1:
        diffs = df.index.to_series().diff().dropna()
        most_common_min = int(diffs.mode()[0].total_seconds() / 60)
    else:
        most_common_min = 15

    if most_common_min not in (15, 30, 60):
        warnings.append(
            f'Ungewöhnliche Zeitauflösung erkannt: {most_common_min} Min. '
            'Erwartet: 15 Min, 30 Min oder 60 Min.'
        )

    # Auf 15-Min-Raster resampling falls nötig
    if most_common_min == 60:
        warnings.append('Stündliche Daten erkannt — werden auf 15-Min interpoliert (÷4).')
        df = df.resample('15min').interpolate(method='linear') / (60 / most_common_min)
    elif most_common_min == 30:
        warnings.append('30-Min-Daten erkannt — werden auf 15-Min interpoliert (÷2).')
        df = df.resample('15min').interpolate(method='linear') / (30 / 15)

    # Vollständiges 15-Min-Raster erwarten
    expected_index = pd.date_range(
        start=df.index.min().floor('D'),
        end=df.index.max().ceil('D') - pd.Timedelta(minutes=15),
        freq='15min',
    )
    gap_count = len(expected_index.difference(df.index))
    if gap_count > 0:
        pct = gap_count / len(expected_index) * 100
        if pct > 5:
            errors.append(
                f'{gap_count} fehlende Zeitslots ({pct:.1f}%) — '
                'Simulation könnte ungenau sein.'
            )
        else:
            warnings.append(
                f'{gap_count} fehlende Zeitslots ({pct:.1f}%) — '
                'werden als 0 behandelt.'
            )
        # Lücken mit 0 füllen
        df = df.reindex(expected_index, fill_value=0)

    # Sanity checks
    if df['import_kwh'].sum() == 0:
        errors.append('Netzbezug ist 0 — bitte prüfen Sie die Import-Datei.')
    if df['export_kwh'].sum() == 0:
        warnings.append(
            'Einspeisung ist 0 — Simulation möglich, aber Batterie bringt keinen Vorteil '
            'ohne Solar-Überschuss.'
        )

    coverage_pct = (1 - gap_count / max(len(expected_index), 1)) * 100

    report = ValidationReport(
        row_count=len(df),
        date_start=str(df.index.min().date()),
        date_end=str(df.index.max().date()),
        resolution_min=15,
        gap_count=gap_count,
        coverage_pct=coverage_pct,
        warnings=warnings,
        errors=errors,
    )
    return df, report
