"""
Datenmodell und Wirtschaftlichkeitsrechnung.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserConfig:
    grid_price: float = 0.272        # CHF/kWh Bezugspreis
    feedin_price: float = 0.080      # CHF/kWh Einspeisevergütung
    battery_sizes: list = field(default_factory=lambda: [5.0, 7.5, 10.0, 15.0])
    invest_costs: dict = field(default_factory=lambda: {
        5.0: 4550, 7.5: 5600, 10.0: 6650, 15.0: 9100
    })
    efficiency: float = 0.90

    @property
    def net_benefit(self) -> float:
        return self.grid_price - self.feedin_price

    @property
    def active_sizes(self) -> list:
        """Nur Grössen mit definiertem Invest-Preis."""
        return [s for s in self.battery_sizes if s in self.invest_costs]


@dataclass
class MonthStats:
    month: int            # 1–12
    import_per_day: float
    export_per_day: float
    night_per_day: float
    day_per_day: float
    peak_kw: float

    @property
    def name(self) -> str:
        return ['', 'Jan', 'Feb', 'Mrz', 'Apr', 'Mai', 'Jun',
                'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'][self.month]


@dataclass
class BatteryResult:
    capacity: float        # kWh
    saved_kwh: float       # kWh/Jahr gespart
    rest_import: float     # kWh/Jahr verbleibender Netzbezug
    reduction_pct: float   # % Reduktion
    chf_per_year: float    # CHF/Jahr Einsparung
    invest_chf: float      # CHF Investition (netto nach Steuer)
    amort_years: float     # Amortisationszeit in Jahren

    @property
    def amort_color(self) -> str:
        if self.amort_years < 10:
            return 'green'
        elif self.amort_years < 15:
            return 'orange'
        return 'red'


@dataclass
class BatteryRecommendation:
    best_size: Optional[float]   # None wenn keine sinnvoll
    reason: str
    verdict: str                 # 'buy' | 'wait' | 'not_worthwhile'
    amort_years: Optional[float]
    chf_per_year: Optional[float]
    breakeven_price: float       # CHF/kWh Preis bei dem es rentabel wird


@dataclass
class AnalysisResult:
    total_import_kwh: float
    total_export_kwh: float
    date_range: tuple             # (start_date, end_date)
    tagesgang_import: dict        # Stunde (int) → Watt (float)
    tagesgang_export: dict
    night_import_kwh: float       # Nacht-Jahresbezug
    day_import_kwh: float         # Tag-Jahresbezug
    night_profile: dict           # Stunde → Watt (nur Nacht-Slots)
    monthly_breakdown: list       # list[MonthStats]
    battery_results: list         # list[BatteryResult]
    recommendation: BatteryRecommendation
    config: UserConfig
    is_estimated: bool = False    # True = Monats-Fallback verwendet

    @property
    def net_cost_chf(self) -> float:
        return (self.total_import_kwh * self.config.grid_price
                - self.total_export_kwh * self.config.feedin_price)

    @property
    def autonomy_pct(self) -> float:
        """Anteil Eigenversorgung."""
        total_consumption = self.total_import_kwh + (
            self.total_export_kwh - self.total_import_kwh
            if self.total_export_kwh > self.total_import_kwh else 0
        )
        # Einfache Näherung: 1 - import/consumption
        # Consumption = import + (export eigentlich = solar - direkt)
        # Besser: aus import/export direkt
        if self.total_import_kwh + self.total_export_kwh == 0:
            return 0.0
        return max(0.0, 1.0 - self.total_import_kwh /
                   (self.total_import_kwh + self.total_export_kwh) * 2) * 100


def compute_economics(
    saved_kwh: float,
    total_import: float,
    capacity: float,
    config: UserConfig
) -> BatteryResult:
    invest = config.invest_costs.get(capacity, capacity * 910)
    net_benefit = config.net_benefit
    chf = saved_kwh * net_benefit
    amort = invest / chf if chf > 0 else float('inf')
    return BatteryResult(
        capacity=capacity,
        saved_kwh=saved_kwh,
        rest_import=total_import - saved_kwh,
        reduction_pct=saved_kwh / total_import * 100 if total_import > 0 else 0,
        chf_per_year=chf,
        invest_chf=invest,
        amort_years=amort,
    )


def recommend_battery(
    battery_results: list,
    config: UserConfig,
    guarantee_years: float = 10.0
) -> BatteryRecommendation:
    """Empfiehlt die beste Batteriegrösse basierend auf Wirtschaftlichkeit."""
    if not battery_results:
        return BatteryRecommendation(
            best_size=None,
            reason='Keine Batteriegrößen konfiguriert.',
            verdict='not_worthwhile',
            amort_years=None,
            chf_per_year=None,
            breakeven_price=0.0,
        )

    # Sortiere nach bestem Preis-Leistungs-Verhältnis (niedrigste Amort.)
    sorted_results = sorted(battery_results, key=lambda r: r.amort_years)
    best = sorted_results[0]

    # Breakeven-Preis: bei welchem Bezugspreis amortisiert best in guarantee_years?
    # invest = years * saved_kwh * (breakeven - feedin)
    # breakeven = invest/(years*saved_kwh) + feedin
    if best.saved_kwh > 0:
        breakeven = best.invest_chf / (guarantee_years * best.saved_kwh) + config.feedin_price
    else:
        breakeven = float('inf')

    if best.amort_years <= guarantee_years:
        verdict = 'buy'
        reason = (f'{best.capacity:.0f} kWh amortisiert sich in {best.amort_years:.1f} Jahren '
                  f'— innerhalb der {guarantee_years:.0f} Jahre Garantie.')
    elif best.amort_years <= guarantee_years * 1.5:
        verdict = 'wait'
        reason = (f'{best.capacity:.0f} kWh amortisiert sich in {best.amort_years:.1f} Jahren '
                  f'— knapp ausserhalb der {guarantee_years:.0f} Jahre Garantie. '
                  f'Rentabel ab ~{breakeven*100:.1f} Rp./kWh.')
    else:
        verdict = 'not_worthwhile'
        reason = (f'Keine Batteriegrösse amortisiert sich innerhalb der Garantiezeit. '
                  f'Rentabel ab ~{breakeven*100:.1f} Rp./kWh (heute: {config.grid_price*100:.1f} Rp.).')

    return BatteryRecommendation(
        best_size=best.capacity,
        reason=reason,
        verdict=verdict,
        amort_years=best.amort_years,
        chf_per_year=best.chf_per_year,
        breakeven_price=breakeven,
    )
