"""
Datenmodell und Wirtschaftlichkeitsrechnung.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

BATTERY_GUARANTEE_YEARS = 10.0
DEGRADATION_RATE = 0.02  # 2%/Jahr Kapazitätsverlust (LFP typisch)


@dataclass
class UserConfig:
    grid_price: float = 0.272        # CHF/kWh Bezugspreis
    feedin_price: float = 0.080      # CHF/kWh Einspeisevergütung
    battery_sizes: list = field(default_factory=lambda: [5.0, 7.5, 10.0, 15.0])
    invest_costs: dict = field(default_factory=lambda: {
        5.0: 4550, 7.5: 5600, 10.0: 6650, 15.0: 9100
    })
    efficiency: float = 0.90
    standby_watts: float = 20.0      # Standby-Verbrauch Inverter/BMS in W
    min_power_watts: float = 100.0   # Mindestleistung für Lade-/Entladestart

    @property
    def charge_eff(self) -> float:
        """Lade-Effizienz (Wurzel aus Round-Trip)."""
        return self.efficiency ** 0.5

    @property
    def discharge_eff(self) -> float:
        """Entlade-Effizienz (Wurzel aus Round-Trip)."""
        return self.efficiency ** 0.5

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
    saved_kwh: float       # kWh/Jahr Netto-Reduktion Netzbezug (= Entladung an Last - Standby aus Netz)
    rest_import: float     # kWh/Jahr verbleibender Netzbezug
    reduction_pct: float   # % Reduktion
    chf_per_year: float    # CHF/Jahr Einsparung (Jahr 1, ohne Degradation)
    invest_chf: float      # CHF Investition (netto nach Steuer)
    amort_years: float     # Amortisationszeit mit Degradation
    standby_loss_kwh: float = 0.0  # kWh/Jahr Standby aus Netz
    charged_kwh: float = 0.0       # kWh/Jahr aus Export in Batterie (entgangene Einspeisung)
    lifetime_profit: float = 0.0   # CHF Gesamtgewinn über Garantiezeit (chf−invest, mit Degradation)

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


def compute_amort_with_degradation(
    invest_chf: float,
    chf_year1: float,
    degradation_rate: float = DEGRADATION_RATE,
    max_years: int = 40,
) -> float:
    """Amortisation unter Berücksichtigung von Degradation.
    Jährliche Einsparung sinkt um degradation_rate pro Jahr."""
    if chf_year1 <= 0:
        return float('inf')
    cumulative = 0.0
    for year in range(1, max_years + 1):
        annual = chf_year1 * (1 - degradation_rate) ** (year - 1)
        cumulative += annual
        if cumulative >= invest_chf:
            # Lineare Interpolation im letzten Jahr
            prev = cumulative - annual
            frac = (invest_chf - prev) / annual
            return year - 1 + frac
    return float('inf')


def compute_lifetime_profit(
    invest_chf: float,
    chf_year1: float,
    horizon_years: float = BATTERY_GUARANTEE_YEARS,
    degradation_rate: float = DEGRADATION_RATE,
) -> float:
    """Gesamtgewinn über Horizont (Σ degradierte Jahresersparnis − Invest).
    Negativ wenn Invest nicht erreicht wird."""
    cumulative = 0.0
    for y in range(int(horizon_years)):
        cumulative += chf_year1 * (1 - degradation_rate) ** y
    return cumulative - invest_chf


def compute_economics(
    saved_kwh: float,
    standby_loss_kwh: float,
    charged_kwh: float,
    total_import: float,
    capacity: float,
    config: UserConfig
) -> BatteryResult:
    """
    Wirtschaftlichkeitsrechnung mit korrekter Energiebilanz:

      Δ_savings = saved * grid - charged * feedin - standby_grid * grid

    saved             = AC-Entladung an Last (vermiedener Netzbezug)
    standby_loss_kwh  = Standby aus Netz (zusätzlicher Netzbezug)
    charged_kwh       = AC aus Export in Batterie (entgangene Einspeisung,
                        beinhaltet Round-Trip- und Standby-aus-SOC-Verluste)
    """
    invest = config.invest_costs.get(capacity, capacity * 910)
    net_saved = saved_kwh - standby_loss_kwh
    chf = (saved_kwh * config.grid_price
           - charged_kwh * config.feedin_price
           - standby_loss_kwh * config.grid_price)
    amort = compute_amort_with_degradation(invest, chf)
    profit = compute_lifetime_profit(invest, chf)
    return BatteryResult(
        capacity=capacity,
        saved_kwh=net_saved,
        rest_import=total_import - net_saved,
        reduction_pct=net_saved / total_import * 100 if total_import > 0 else 0,
        chf_per_year=chf,
        invest_chf=invest,
        amort_years=amort,
        standby_loss_kwh=standby_loss_kwh,
        charged_kwh=charged_kwh,
        lifetime_profit=profit,
    )


def recommend_battery(
    battery_results: list,
    config: UserConfig,
    guarantee_years: float = BATTERY_GUARANTEE_YEARS,
) -> BatteryRecommendation:
    """Empfiehlt die beste Batteriegrösse basierend auf Wirtschaftlichkeit."""
    if not battery_results:
        return BatteryRecommendation(
            best_size=None,
            reason='Keine Batteriegroessen konfiguriert.',
            verdict='not_worthwhile',
            amort_years=None,
            chf_per_year=None,
            breakeven_price=0.0,
        )

    # Selektion: max Lebensdauer-Gewinn innerhalb des sichersten Risiko-Tiers.
    # Tier-Logik: Amort innerhalb Garantie ist sicherer (Hersteller garantiert
    # Funktion). Wenn keine Variante das schafft, weiche auf 1.5×Garantie aus.
    # Innerhalb des Tiers wählt höchster Lebensdauer-Gewinn — eine grössere
    # Batterie mit längerer Amort kann mehr CHF einbringen als eine schnell
    # amortisierte kleine.
    buy_tier = [r for r in battery_results if r.amort_years <= guarantee_years]
    wait_tier = [r for r in battery_results if r.amort_years <= guarantee_years * 1.5]
    if buy_tier:
        best = max(buy_tier, key=lambda r: r.lifetime_profit)
    elif wait_tier:
        best = max(wait_tier, key=lambda r: r.lifetime_profit)
    else:
        best = min(battery_results, key=lambda r: r.amort_years)

    # Breakeven-Bezugspreis: bei dem die Investition sich über guarantee_years
    # amortisiert (mit Degradation, ohne Diskontierung).
    #
    #   year1_chf = grid * net_saved - feedin * charged
    #   total_chf = year1_chf * Σ_{y=0..N-1} (1-d)^y
    #   invest    = total_chf  ⇒  grid = (invest/(N·avg_factor) + feedin·charged) / net_saved
    avg_factor = sum((1 - DEGRADATION_RATE) ** y for y in range(int(guarantee_years))) / guarantee_years
    horizon = guarantee_years * avg_factor  # effektive Jahre nach Degradation
    if best.saved_kwh > 0 and horizon > 0:
        breakeven = (best.invest_chf / horizon + best.charged_kwh * config.feedin_price) / best.saved_kwh
    else:
        breakeven = 9.99

    breakeven_str = f'{breakeven*100:.1f} Rp./kWh' if not math.isinf(breakeven) else 'unbegrenzt'

    if best.amort_years <= guarantee_years:
        verdict = 'buy'
        reason = (f'{best.capacity:.0f} kWh amortisiert sich in {best.amort_years:.1f} Jahren '
                  f'-- innerhalb der {guarantee_years:.0f}-Jahre-Garantie. '
                  f'Gewinn ueber {guarantee_years:.0f} Jahre: CHF {best.lifetime_profit:.0f}.')
    elif best.amort_years <= guarantee_years * 1.5:
        verdict = 'wait'
        reason = (f'{best.capacity:.0f} kWh amortisiert sich in {best.amort_years:.1f} Jahren '
                  f'-- knapp ausserhalb der {guarantee_years:.0f}-Jahre-Garantie '
                  f'(Verlust ueber Garantiezeit: CHF {best.lifetime_profit:.0f}). '
                  f'Rentabel ab ~{breakeven_str}.')
    else:
        verdict = 'not_worthwhile'
        reason = (f'Keine Batterie amortisiert sich innerhalb der Garantiezeit. '
                  f'Rentabel ab ~{breakeven_str} (heute: {config.grid_price*100:.1f} Rp.).')

    return BatteryRecommendation(
        best_size=best.capacity,
        reason=reason,
        verdict=verdict,
        amort_years=best.amort_years,
        chf_per_year=best.chf_per_year,
        breakeven_price=breakeven,
    )
