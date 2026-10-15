"""Core workflow engine for Avito Radar: Add, Scan, Watch, Export."""

from __future__ import annotations

import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from avito_radar.analysis.classifier import classify_item, extract_goods_group
from avito_radar.analysis.market import annotate_market_prices
from avito_radar.config import AppSettings, load_settings
from avito_radar.core.client import AvitoClient
from avito_radar.exporters.excel import export_to_excel
from avito_radar.notifications.telegram import TelegramNotifier, load_telegram_config
from avito_radar.parsers.item_parser import ParsedItem, inspect_item_views, parse_catalog_item
from avito_radar.parsers.url_resolver import SearchConfig, resolve_url
from avito_radar.storage.db import (
    SearchRecord,
    append_alert,
    load_listings,
    load_locations_cache,
    load_scan_state,
    load_search,
    load_seen,
    save_listings,
    save_locations_cache,
    save_scan_state,
    save_search,
    save_seen,
)

SORT_BY_DATE_PARAM = {"s": "104"}


def create_search_from_url(
    client: AvitoClient,
    url: str,
    *,
    custom_name: str | None = None,
    city_override: str | None = None,
    user_id: str | int = "",
) -> SearchRecord:
    cache = load_locations_cache()
    resolved: SearchConfig = resolve_url(client, url, locations_cache=cache, city_override=city_override)
    save_locations_cache(cache)

    name = custom_name or resolved.name
    record = SearchRecord(
        name=name,
        title=resolved.title,
        category_type=resolved.category_type,
        catalog_url=resolved.catalog_url,
        city=resolved.city,
        params=resolved.params,
        user_id=str(user_id or "").strip(),
    )
    save_search(record)
    return record


def scan_search(
    search: SearchRecord,
    *,
    client: AvitoClient | None = None,
    settings: AppSettings | None = None,
    start_from_scratch: bool = False,
    max_pages: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[int, Path]:
    """Crawl search pages, store items, compute market analytics, and export to Excel."""
    cfg = settings or load_settings()
    cl = client or AvitoClient(delay=cfg.request_delay)

    listings_data = load_listings(search)
    seen_data = load_seen(search)
    state_data = load_scan_state(search)

    start_page = 1 if (start_from_scratch or state_data.get("complete")) else int(state_data.get("next_page", 1))
    limit_pages = max_pages or cfg.max_scan_pages
    current_page = start_page
    total_new_items = 0

    params = {**search.params, **SORT_BY_DATE_PARAM}
    if search.min_price:
        params["pmin"] = str(search.min_price)
    if search.max_price:
        params["pmax"] = str(search.max_price)

    try:
        while current_page < start_page + limit_pages:
            if progress_callback:
                progress_callback({
                    "event": "PAGE_START",
                    "search": search.name,
                    "page": current_page,
                })

            page = cl.fetch_catalog_page(
                catalog_url=search.catalog_url,
                params=params,
                page_number=current_page,
            )

            now_str = datetime.now().isoformat()
            page_new = 0

            for raw_item in page.items:
                item_id_str = str(raw_item["id"])
                listings_data[item_id_str] = raw_item
                if item_id_str not in seen_data:
                    seen_data[item_id_str] = now_str
                    page_new += 1
                    total_new_items += 1

            save_listings(search, listings_data)
            save_seen(search, seen_data)

            is_done = page.is_last or current_page >= cfg.max_scan_pages
            save_scan_state(search, {"complete": is_done, "next_page": 1 if is_done else current_page + 1})

            if progress_callback:
                progress_callback({
                    "event": "PAGE_DONE",
                    "search": search.name,
                    "page": current_page,
                    "items_found": len(page.items),
                    "new_items": page_new,
                    "total_in_search": page.total_count,
                    "is_last": is_done,
                })

            if is_done:
                break
            current_page += 1

    except KeyboardInterrupt:
        if progress_callback:
            progress_callback({"event": "INTERRUPTED", "search": search.name, "saved_page": current_page})

    # Parse and enrich all collected listings
    parsed_items: list[ParsedItem] = []
    for raw in listings_data.values():
        parsed = parse_catalog_item(raw)
        q_str = search.title or search.params.get("q", "")
        classify_item(parsed, category_type=search.category_type, search_query=q_str)
        parsed_items.append(parsed)

    # Market stats
    annotate_market_prices(
        parsed_items,
        group_key_fn=lambda x: extract_goods_group(x.title) if search.category_type == "goods" else "all",
    )

    # Export to Excel
    excel_path = export_to_excel(search.name, parsed_items)
    return len(parsed_items), excel_path


def watch_searches(
    searches: list[SearchRecord],
    *,
    client: AvitoClient | None = None,
    settings: AppSettings | None = None,
    interval_seconds: float | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> None:
    """Continuously monitor multiple searches for newly published listings."""
    cfg = settings or load_settings()
    cl = client or AvitoClient(delay=cfg.request_delay)
    interval = interval_seconds or cfg.watch_interval

    tg_config = load_telegram_config()
    notifier = TelegramNotifier(tg_config) if (tg_config and tg_config.enabled) else None

    emit = on_event or (lambda event, data: None)
    emit("WATCH_STARTED", {
        "searches": [s.name for s in searches],
        "interval": interval,
        "telegram_enabled": notifier is not None,
    })

    # Prime searches: initial items are remembered so only subsequent items trigger alerts
    primed_searches: set[str] = set()
    watched_context = []

    for s in searches:
        listings = load_listings(s)
        seen = load_seen(s)
        watched_context.append({"search": s, "listings": listings, "seen": seen})

    cycle = 0
    try:
        while True:
            cycle += 1
            for ctx in watched_context:
                s: SearchRecord = ctx["search"]
                listings: dict[str, dict[str, Any]] = ctx["listings"]
                seen: dict[str, str] = ctx["seen"]

                is_first_pass = s.name not in primed_searches
                params = {**s.params, **SORT_BY_DATE_PARAM}
                changed = False
                new_ad_count = 0

                try:
                    for page_num in range(1, s.watch_pages + 1):
                        page = cl.fetch_catalog_page(
                            catalog_url=s.catalog_url,
                            params=params,
                            page_number=page_num,
                        )

                        now_dt = datetime.now()
                        now_str = now_dt.isoformat()

                        for raw in page.items:
                            item_id_str = str(raw["id"])
                            if item_id_str in seen:
                                continue

                            seen[item_id_str] = now_str
                            listings[item_id_str] = raw
                            changed = True

                            if is_first_pass:
                                new_ad_count += 1
                                continue

                            # Fresh item detected!
                            parsed = parse_catalog_item(raw)
                            q_str = s.title or s.params.get("q", "")
                            classify_item(parsed, category_type=s.category_type, search_query=q_str)

                            # Filter mismatched models (e.g. iPhone 13 when searching iPhone 15)
                            if getattr(parsed, "is_mismatched_model", False):
                                continue

                            # Filter accessories if configured
                            if getattr(s, "exclude_accessories", True) and getattr(parsed, "is_accessory", False):
                                continue

                            # Filter private only
                            if s.private_only and any("Агентство" in t or "Магазин" in t for t in parsed.tags):
                                continue

                            # Inspect views to verify truly fresh listing
                            if s.new_only:
                                total_v, today_v, is_repub = inspect_item_views(cl, parsed.url, s.catalog_url)
                                parsed.total_views = total_v
                                parsed.today_views = today_v
                                parsed.is_republished = is_repub
                                if is_repub:
                                    emit("REPUBLISHED_IGNORED", {"item": parsed.title, "views": total_v})
                                    continue

                            # Append alert
                            append_alert(s, parsed)
                            emit("ALERT", {"search": s.name, "item": parsed})

                            # Telegram alert
                            if notifier:
                                try:
                                    notifier.send_notification(s.title, parsed)
                                except Exception as exc:
                                    emit("TELEGRAM_ERROR", {"error": str(exc)})

                    if changed:
                        save_listings(s, listings)
                        save_seen(s, seen)

                    if is_first_pass:
                        primed_searches.add(s.name)
                        emit("PRIMED", {"search": s.name, "remembered_items": new_ad_count})

                except Exception as exc:
                    emit("WATCH_ERROR", {"search": s.name, "error": str(exc)})

            emit("CYCLE_COMPLETE", {"cycle": cycle, "next_in_seconds": round(interval)})
            time.sleep(interval * random.uniform(0.85, 1.15))

    except KeyboardInterrupt:
        emit("WATCH_STOPPED", {})
