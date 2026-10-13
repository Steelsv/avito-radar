"""Excel exporter with professional styling, auto-formatting and clickable links."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from avito_radar.analysis.classifier import is_likely_fake_or_junk
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.storage.db import ROOT_DIR

OUTPUT_DIR = ROOT_DIR / "output"

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

DEAL_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
AGENCY_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

LINK_FONT = Font(name="Calibri", size=11, color="0563C1", underline="single")
REGULAR_FONT = Font(name="Calibri", size=11)
BOLD_FONT = Font(name="Calibri", size=11, bold=True)

THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)

COLUMNS = [
    ("№", 6),
    ("Заголовок", 35),
    ("Цена (₽)", 15),
    ("Рынок (₽)", 15),
    ("Выгода", 14),
    ("Город / Адрес", 28),
    ("Метро", 18),
    ("Продавец", 22),
    ("Тип", 16),
    ("Рейтинг", 10),
    ("Сделок", 10),
    ("Теги", 25),
    ("Опубликовано", 18),
    ("Ссылка", 15),
    ("Описание", 40),
]


def export_to_excel(
    search_name: str,
    items: Sequence[ParsedItem],
    *,
    output_dir: Path | None = None,
) -> Path:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{search_name}_{timestamp}.xlsx"
    file_path = target_dir / filename

    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    # Filtered sheet (deals & private sellers, excluding junk/parts/clickbait)
    top_items = [
        it for it in items
        if not any("Агентство" in t for t in it.tags)
        and not is_likely_fake_or_junk(it)
    ]
    # Sort: best deals first, then by date/price
    sorted_top = sorted(
        top_items,
        key=lambda x: (x.market_diff_percent if x.market_diff_percent is not None else 999),
    )
    sorted_all = sorted(
        items,
        key=lambda x: (x.market_diff_percent if x.market_diff_percent is not None else 999),
    )

    sheets = [
        ("🔥 Выборка (Частные и топ)", sorted_top or sorted_all),
        ("Все объявления", sorted_all),
    ]

    for title, sheet_items in sheets:
        ws = wb.create_sheet(title)

        # Header row
        ws.append([c[0] for c in COLUMNS])
        for col_idx, (_, width) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.column_dimensions[get_column_letter(col_idx)].width = width
        ws.row_dimensions[1].height = 28

        # Data rows
        for idx, item in enumerate(sheet_items, start=1):
            diff_str = ""
            if item.market_diff_percent is not None:
                diff_str = f"{item.market_diff_percent:+.1f}%"

            row = [
                idx,
                item.title,
                item.price,
                item.market_price,
                diff_str,
                item.address or item.city,
                item.metro,
                item.seller_name,
                item.seller_type,
                item.seller_rating,
                item.closed_listings,
                ", ".join(item.tags),
                item.published_text,
                "Открыть",
                item.description[:300] if item.description else "",
            ]
            ws.append(row)
            row_idx = ws.max_row
            ws.row_dimensions[row_idx].height = 20

            # Cell styling
            is_deal = item.market_diff_percent is not None and item.market_diff_percent <= -15
            is_agency = any("Агентство" in t for t in item.tags)
            fill_style = DEAL_FILL if is_deal else (AGENCY_FILL if is_agency else None)

            for c_idx in range(1, len(COLUMNS) + 1):
                cell = ws.cell(row=row_idx, column=c_idx)
                cell.border = THIN_BORDER
                cell.font = REGULAR_FONT
                cell.alignment = Alignment(vertical="center")

                if fill_style:
                    cell.fill = fill_style

                # Numbers alignment & format
                if c_idx in (3, 4):  # Price, Market price
                    cell.number_format = "#,##0"
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if c_idx == 3 and is_deal:
                        cell.font = BOLD_FONT

                if c_idx == 5:  # Diff
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    if is_deal:
                        cell.font = BOLD_FONT

                if c_idx == 14:  # Link
                    cell.hyperlink = item.url
                    cell.font = LINK_FONT
                    cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions

    wb.save(file_path)
    return file_path
