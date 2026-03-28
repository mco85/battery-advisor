"""
PDF-Report-Generator für Batteriespeicher-Analyse.
Adaptiert aus generate_battery_pdf.py — nutzt DejaVu Sans (cross-platform).
"""
from __future__ import annotations
import io
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = Path(__file__).parent / 'fonts'

# ── Farben ──────────────────────────────────────────────────────────────────
DARK_BLUE   = (26,  58,  92)
GREEN       = (26, 107,  60)
LIGHT_BLUE  = (227, 242, 253)
LIGHT_GREEN = (232, 245, 233)
LIGHT_AMBER = (255, 243, 224)
LIGHT_RED   = (255, 235, 238)
TABLE_EVEN  = (244, 248, 255)
TABLE_HEAD  = (26,  58,  92)
GREY_LINE   = (220, 220, 220)
TEXT        = (26,  26,  26)
MID_GREY    = (100, 100, 100)


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__('P', 'mm', 'A4')
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(20, 20, 20)
        self.add_font('deja', '',  str(FONTS_DIR / 'DejaVuSans.ttf'))
        self.add_font('deja', 'B', str(FONTS_DIR / 'DejaVuSans-Bold.ttf'))
        self._F = 'deja'
        self.set_font(self._F, '', 10.5)
        self.add_page()

    def set_text_color_rgb(self, r, g, b): self.set_text_color(r, g, b)
    def set_draw_color_rgb(self, r, g, b): self.set_draw_color(r, g, b)
    def set_fill_color_rgb(self, r, g, b): self.set_fill_color(r, g, b)

    def rule(self, color=GREY_LINE):
        self.set_draw_color_rgb(*color)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def spacer(self, h=4): self.ln(h)

    def cover_block(self, subtitle: str):
        self.set_fill_color_rgb(*DARK_BLUE)
        self.rect(0, 0, 210, 42, 'F')
        self.set_fill_color_rgb(*GREEN)
        self.rect(0, 40, 210, 3, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font(self._F, 'B', 22)
        self.set_xy(20, 10)
        self.cell(0, 10, 'Batteriespeicher-Analyse', new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_font(self._F, '', 10)
        self.set_x(20)
        self.cell(0, 7, subtitle)
        self.set_y(50)
        self.set_text_color_rgb(*TEXT)

    def h2(self, text):
        self.spacer(5)
        self.set_font(self._F, 'B', 13)
        self.set_text_color_rgb(*DARK_BLUE)
        self.cell(0, 8, text, new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_draw_color_rgb(*GREEN)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color_rgb(*TEXT)

    def h3(self, text):
        self.spacer(3)
        self.set_font(self._F, 'B', 11)
        self.set_text_color_rgb(*DARK_BLUE)
        self.cell(0, 7, text, new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_text_color_rgb(*TEXT)

    def body(self, text, size=10.5):
        self.set_font(self._F, '', size)
        self.set_text_color_rgb(*TEXT)
        self.multi_cell(0, 5.5, text)

    def bullet(self, text, size=10):
        self.set_font(self._F, '', size)
        self.set_text_color_rgb(*TEXT)
        self.set_x(self.l_margin + 4)
        self.cell(5, 5.5, '\u2022')
        self.multi_cell(self.w - self.l_margin - self.r_margin - 9, 5.5, text)

    def callout(self, title, text, bg=LIGHT_GREEN, title_color=GREEN):
        self.spacer(2)
        self.set_fill_color_rgb(*bg)
        self.set_draw_color_rgb(*title_color)
        self.set_line_width(0.8)
        w = self.w - self.l_margin - self.r_margin
        x, y = self.get_x(), self.get_y()
        self.set_font(self._F, '', 9.5)
        lines = self.multi_cell(w - 8, 5, text, dry_run=True, output='LINES')
        total_h = 6 + len(lines) * 5 + 8
        self.rect(x, y, w, total_h, 'F')
        self.line(x, y, x, y + total_h)
        self.set_xy(x + 4, y + 3)
        self.set_font(self._F, 'B', 10)
        self.set_text_color_rgb(*title_color)
        self.cell(0, 6, title, new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_font(self._F, '', 9.5)
        self.set_text_color_rgb(*TEXT)
        self.set_x(x + 4)
        self.multi_cell(w - 8, 5, text)
        self.spacer(3)

    def table(self, headers, rows, col_widths=None, small=False):
        fs = 8.5 if small else 9.5
        w = self.w - self.l_margin - self.r_margin
        if col_widths is None:
            cw = w / len(headers)
            col_widths = [cw] * len(headers)
        row_h = 6 if small else 6.5

        self.set_fill_color_rgb(*TABLE_HEAD)
        self.set_text_color(255, 255, 255)
        self.set_font(self._F, 'B', fs)
        for h, cw in zip(headers, col_widths):
            self.cell(cw, 7, h, border=0, fill=True)
        self.ln()

        self.set_font(self._F, '', fs)
        for ri, row in enumerate(rows):
            fill = ri % 2 == 1
            if self.get_y() + row_h > self.h - self.b_margin:
                self.add_page()
                self.set_fill_color_rgb(*TABLE_HEAD)
                self.set_text_color(255, 255, 255)
                self.set_font(self._F, 'B', fs)
                for h, cw in zip(headers, col_widths):
                    self.cell(cw, 7, h, border=0, fill=True)
                self.ln()
                self.set_font(self._F, '', fs)

            if fill:
                self.set_fill_color_rgb(*TABLE_EVEN)
            else:
                self.set_fill_color(255, 255, 255)
            self.set_text_color_rgb(*TEXT)

            for cell, cw in zip(row, col_widths):
                bold = str(cell).startswith('**') and str(cell).endswith('**')
                txt = str(cell).strip('*')
                self.set_font(self._F, 'B' if bold else '', fs)
                self.cell(cw, row_h, txt, border=0, fill=fill)
            self.ln()

        self.set_draw_color_rgb(*GREY_LINE)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.spacer(4)
        self.set_text_color_rgb(*TEXT)

    def embed_image(self, img_bytes: bytes, w: int = 170, h: int = 80):
        """Bettet ein PNG-Bild (als bytes) in die PDF ein."""
        buf = io.BytesIO(img_bytes)
        y = self.get_y()
        self.image(buf, x=self.l_margin, y=y, w=w, h=h)
        self.set_y(y + h + 3)

    def footer(self):
        self.set_y(-12)
        self.set_font(self._F, '', 8)
        self.set_text_color_rgb(*MID_GREY)
        self.cell(0, 5, f'Seite {self.page_no()}', align='C')


def _get_chart_png(fig) -> bytes | None:
    """Rendert ein Plotly-Figure als PNG-Bytes (benötigt kaleido)."""
    try:
        return fig.to_image(format='png', width=900, height=380, scale=1.5)
    except Exception:
        return None


def generate_report(result, chart_figs: dict | None = None) -> bytes:
    """
    Erstellt den PDF-Report und gibt ihn als bytes zurück.

    result: AnalysisResult
    chart_figs: optional dict mit {'tagesgang': fig, 'monthly': fig, 'battery': fig}
    """
    from datetime import date as date_type

    pdf = ReportPDF()

    # ── Cover ────────────────────────────────────────────────────────────────
    r = result
    start, end = r.date_range
    subtitle = (f'Auswertungszeitraum: {start} bis {end}  |  '
                f'Stand: {date_type.today().strftime("%d.%m.%Y")}')
    if r.is_estimated:
        subtitle += '  |  SCHÄTZUNG (Monatswerte)'
    pdf.cover_block(subtitle)

    # ── Fazit ─────────────────────────────────────────────────────────────────
    rec = r.recommendation
    verdict_map = {
        'buy': (LIGHT_GREEN, GREEN),
        'wait': (LIGHT_AMBER, (184, 92, 0)),
        'not_worthwhile': (LIGHT_RED, (198, 40, 40)),
    }
    bg, col = verdict_map.get(rec.verdict, (LIGHT_GREEN, GREEN))
    verdict_label = {'buy': 'Kaufempfehlung', 'wait': 'Abwarten empfohlen',
                     'not_worthwhile': 'Aktuell nicht rentabel'}.get(rec.verdict, '')
    pdf.callout(f'Fazit: {verdict_label}', rec.reason, bg=bg, title_color=col)

    # ── Energiebilanz ─────────────────────────────────────────────────────────
    pdf.h2('Energiebilanz')
    net_cost = r.net_cost_chf
    pdf.table(
        ['Metrik', 'Wert'],
        [
            ['Jahres-Netzbezug', f'{r.total_import_kwh:.0f} kWh'],
            ['Jahres-Einspeisung', f'{r.total_export_kwh:.0f} kWh'],
            ['Netto-Stromkosten', f'CHF {net_cost:.0f}/Jahr'],
            ['Bezugspreis', f'{r.config.grid_price*100:.1f} Rp./kWh'],
            ['Einspeiseverg\u00fctung', f'{r.config.feedin_price*100:.1f} Rp./kWh'],
            ['**Nettovorteil Batterie**', f'**{r.config.net_benefit*100:.1f} Rp./kWh**'],
        ],
        col_widths=[100, 70],
    )

    # ── Batteriesimulation ────────────────────────────────────────────────────
    pdf.h2(f'Batterie-Simulation ({r.config.efficiency*100:.0f}% RT, {r.config.standby_watts:.0f}W Standby)')
    rows = []
    for br in r.battery_results:
        amort_str = f'{br.amort_years:.1f} J' if br.amort_years < 99 else '>30 J'
        best = (rec.best_size == br.capacity)
        prefix = '**' if best else ''
        suffix = '**' if best else ''
        rows.append([
            f'{prefix}{br.capacity:.0f} kWh{suffix}',
            f'{prefix}{br.saved_kwh:.0f} kWh{suffix}',
            f'-{br.standby_loss_kwh:.0f}',
            f'{prefix}CHF {br.chf_per_year:.0f}{suffix}',
            f'{prefix}CHF {br.invest_chf:.0f}{suffix}',
            f'{prefix}{amort_str}{suffix}',
        ])
    pdf.table(
        ['Kap.', 'Netto/J', 'Standby', 'CHF/J', 'Invest*', 'Amort.'],
        rows,
        col_widths=[22, 26, 20, 28, 30, 44],
        small=True,
    )
    pdf.body('* Netto nach Steuerabzug ~30% (Kanton LU / CH)', size=8.5)

    # ── Battery-Chart ─────────────────────────────────────────────────────────
    if chart_figs and 'battery' in chart_figs:
        png = _get_chart_png(chart_figs['battery'])
        if png:
            pdf.spacer(2)
            pdf.embed_image(png, w=170, h=75)

    # ── Tagesgang ─────────────────────────────────────────────────────────────
    pdf.h2('Tagesgang — Jahresdurchschnitt')
    if chart_figs and 'tagesgang' in chart_figs:
        png = _get_chart_png(chart_figs['tagesgang'])
        if png:
            pdf.embed_image(png, w=170, h=75)

    # ── Monatliche Analyse ────────────────────────────────────────────────────
    pdf.h2('Monatliche Analyse')
    if chart_figs and 'monthly' in chart_figs:
        png = _get_chart_png(chart_figs['monthly'])
        if png:
            pdf.embed_image(png, w=170, h=80)

    month_rows = []
    for m in r.monthly_breakdown:
        month_rows.append([
            m.name,
            f'{m.import_per_day:.2f}',
            f'{m.export_per_day:.2f}',
            f'{m.night_per_day:.2f}',
            f'{m.day_per_day:.2f}',
            f'{m.peak_kw:.1f}',
        ])
    pdf.table(
        ['Monat', 'Bezug/Tag', 'Einsp./Tag', 'Nacht kWh', 'Tag kWh', 'Peak kW'],
        month_rows,
        col_widths=[20, 28, 28, 26, 24, 44],
        small=True,
    )

    # ── Empfehlung ────────────────────────────────────────────────────────────
    pdf.h2('Empfehlung')
    if rec.verdict == 'buy':
        pdf.body(
            f'Die {rec.best_size:.0f} kWh Batterie amortisiert sich in '
            f'{rec.amort_years:.1f} Jahren und bringt CHF {rec.chf_per_year:.0f}/Jahr.',
            size=10,
        )
    elif rec.verdict == 'wait':
        pdf.body(
            f'Aktuell lohnt sich der Kauf knapp nicht ({rec.amort_years:.1f} Jahre '
            f'Amortisation vs. 10 Jahre Garantie). '
            f'Rentabel ab ~{rec.breakeven_price*100:.1f} Rp./kWh.',
            size=10,
        )
    else:
        pdf.body(
            f'Bei aktuellen Preisen ({r.config.grid_price*100:.1f} Rp./kWh) '
            f'amortisiert sich keine Grösse innerhalb der Garantiezeit. '
            f'Rentabel ab ~{rec.breakeven_price*100:.1f} Rp./kWh.',
            size=10,
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.rule()
    pdf.set_font(pdf._F, '', 8)
    pdf.set_text_color_rgb(*MID_GREY)
    est_note = ' | Schätzung auf Basis von Monatswerten' if r.is_estimated else ''
    pdf.multi_cell(
        0, 4.5,
        f'Simulation: stateful DC-Batterie, {r.config.efficiency*100:.0f}% Round-Trip-Effizienz. '
        f'Zeitraum: {start} bis {end}.{est_note} Alle Angaben ohne Gewähr.',
        align='C',
    )

    return bytes(pdf.output())
