#!/usr/bin/env python3
"""Avito Radar — Личный интеллектуальный парсер и монитор объявлений Авито.

Запуск:
    python run.py              # Интерактивное меню с красивым интерфейсом
    python run.py add <URL>    # Быстро добавить поиск по ссылке
    python run.py scan <имя>   # Собрать все объявления в базу и Excel
    python run.py watch <имя>  # Мониторинг новых объявлений в реальном времени с Telegram
    python run.py export <имя> # Сформировать свежую таблицу Excel
    python run.py list         # Список сохранённых поисков
    python run.py telegram     # Настройка или проверка Telegram-бота
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows
if sys.platform.startswith("win"):
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if reconf:
            try:
                reconf(encoding="utf-8", errors="replace")
            except Exception:
                pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    import questionary
except ImportError:
    questionary = None

from avito_radar.config import AppSettings, load_settings, save_settings
from avito_radar.core.client import AvitoClient
from avito_radar.engine import create_search_from_url, scan_search, watch_searches
from avito_radar.exporters.excel import export_to_excel
from avito_radar.notifications.telegram import (
    TelegramConfig,
    TelegramNotifier,
    auto_detect_chat_id,
    load_telegram_config,
    save_telegram_config,
)
from avito_radar.parsers.item_parser import ParsedItem, parse_catalog_item
from avito_radar.analysis.classifier import classify_item, extract_goods_group
from avito_radar.analysis.market import annotate_market_prices
from avito_radar.storage.db import (
    SearchRecord,
    delete_search,
    list_searches,
    load_listings,
    load_scan_state,
    load_search,
)

console = Console()

BANNER = """[bold cyan]
   ___         _  __             ___            __            
  / _ | _  __ (_)/ /_ ___       / _ \\ ___ _ ___/ /___ _ ____ 
 / __ |/ |/ // // __// _ \\     / , _// _ `// _  // _ `// __/ 
/_/ |_||___//_/ \\__/ \\___/    /_/|_| \\_,_/ \\_,_/ \\_,_//_/    
[/bold cyan][dim]         Смотрящий за Авито — личный мониторинг и радар[/dim]
"""


def show_banner() -> None:
    console.print(BANNER)


def prompt_text(prompt: str, default: str = "") -> str:
    if questionary:
        return questionary.text(prompt, default=default).ask() or ""
    val = input(f"{prompt} [{default}]: " if default else f"{prompt}: ").strip()
    return val or default


def prompt_confirm(prompt: str, default: bool = True) -> bool:
    if questionary:
        return bool(questionary.confirm(prompt, default=default).ask())
    ans = input(f"{prompt} (д/н) [{'д' if default else 'н'}]: ").strip().lower()
    if not ans:
        return default
    return ans in ("д", "y", "yes", "да")


def prompt_choice(title: str, choices: list[str]) -> int | None:
    if questionary:
        selected = questionary.select(title, choices=choices + ["Назад / Отмена"]).ask()
        if not selected or selected == "Назад / Отмена":
            return None
        return choices.index(selected)
    console.print(f"\n[bold]{title}[/bold]")
    for idx, c in enumerate(choices, start=1):
        console.print(f"  [cyan]{idx}.[/cyan] {c}")
    console.print("  [dim]0. Назад[/dim]")
    while True:
        res = input("> ").strip()
        if res in ("0", ""):
            return None
        if res.isdigit() and 1 <= int(res) <= len(choices):
            return int(res) - 1
        console.print("[red]Введите номер из списка.[/red]")


# ==============================================================================
# Commands
# ==============================================================================

def cmd_add(url: str, custom_name: str | None = None) -> None:
    console.print(f"\n[cyan]🔍 Анализирую ссылку на Авито...[/cyan]")
    client = AvitoClient(delay=2.0)

    try:
        record = create_search_from_url(client, url, custom_name=custom_name)
    except Exception as exc:
        console.print(f"[bold red]✗ Ошибка распознавания ссылки:[/bold red] {exc}")
        return

    table = Table(show_header=False, box=None)
    table.add_row("[bold]Название:[/bold]", f"[green]{record.title}[/green]")
    table.add_row("[bold]Идентификатор:[/bold]", f"[cyan]{record.name}[/cyan]")
    table.add_row("[bold]Город:[/bold]", record.city)
    table.add_row("[bold]Категория:[/bold]", record.category_type)
    table.add_row("[bold]Параметры фильтров:[/bold]", f"{len(record.params)} параметров определено")

    panel = Panel(table, title="[bold green]✓ Поиск успешно создан и сохранён![/bold green]", border_style="green")
    console.print(panel)


def cmd_list() -> None:
    searches = list_searches()
    if not searches:
        console.print("[yellow]Пока нет сохранённых поисков.[/yellow] Добавьте через пункт «Добавить поиск» или команду `python run.py add <URL>`.")
        return

    table = Table(title="Сохранённые поиски", header_style="bold cyan")
    table.add_column("№", style="dim", width=4)
    table.add_column("Имя", style="bold")
    table.add_column("Категория", style="magenta")
    table.add_column("Город", style="yellow")
    table.add_column("Объявлений", justify="right")
    table.add_column("Статус", style="green")
    table.add_column("Заголовок")

    for idx, s in enumerate(searches, start=1):
        listings = load_listings(s)
        state = load_scan_state(s)
        status = "Собран полностью" if state.get("complete") else f"Стр. {state.get('next_page', 1)}"
        table.add_row(
            str(idx),
            s.name,
            s.category_type,
            s.city,
            str(len(listings)),
            status,
            s.title[:45] + ("..." if len(s.title) > 45 else ""),
        )

    console.print(table)


def cmd_scan(name: str, full: bool = False, max_pages: int | None = None) -> None:
    search = load_search(name)
    if not search:
        console.print(f"[bold red]✗ Поиск «{name}» не найден.[/bold red]")
        return

    settings = load_settings()
    console.print(f"\n[cyan]▶ Запуск сбора объявлений для «{search.title}»...[/cyan]")

    def on_progress(evt: dict[str, Any]) -> None:
        if evt["event"] == "PAGE_START":
            console.print(f"  [dim]Загружаю страницу {evt['page']}...[/dim]")
        elif evt["event"] == "PAGE_DONE":
            console.print(
                f"  [green]✓[/green] Стр. {evt['page']}: найдено [bold]{evt['items_found']}[/bold] "
                f"(новых [bold green]{evt['new_items']}[/bold green], всего в каталоге ~{evt['total_in_search']})"
            )
        elif evt["event"] == "INTERRUPTED":
            console.print(f"\n[yellow]⚠ Сбор прерван пользователем. Прогресс сохранён (стр. {evt['saved_page']}).[/yellow]")

    total_count, excel_path = scan_search(
        search,
        settings=settings,
        start_from_scratch=full,
        max_pages=max_pages,
        progress_callback=on_progress,
    )

    console.print(f"\n[bold green]✓ Сбор завершён![/bold green] Всего в базе: [bold]{total_count}[/bold] объявлений.")
    console.print(f"[cyan]📊 Таблица Excel сохранена:[/cyan] [bold underline]{excel_path}[/bold underline]\n")

    if sys.platform.startswith("win") and prompt_confirm("Открыть сформированную таблицу Excel сейчас?", default=True):
        os.startfile(str(excel_path))


def cmd_watch(names: list[str], interval: float | None = None) -> None:
    searches: list[SearchRecord] = []
    for n in names:
        s = load_search(n)
        if s:
            searches.append(s)
        else:
            console.print(f"[red]Поиск «{n}» не найден, пропускаю.[/red]")

    if not searches:
        console.print("[red]Нет доступных поисков для мониторинга.[/red]")
        return

    settings = load_settings()
    inter = interval or settings.watch_interval

    console.print(Panel(
        f"[bold]Мониторинг активен для:[/bold] {', '.join(s.name for s in searches)}\n"
        f"[dim]Интервал проверки: {inter:.0f} сек. Для остановки нажмите Ctrl+C.[/dim]",
        title="[bold green]👁 Режим реального времени (Watch)[/bold green]",
        border_style="green",
    ))

    def on_event(event: str, data: dict[str, Any]) -> None:
        now_str = time.strftime("%H:%M:%S")
        if event == "PRIMED":
            console.print(f"[dim]{now_str}[/dim] [green]✓ База «{data['search']}» инициализирована ({data['remembered_items']} объявлений в памяти). Ожидаю новые...[/green]")
        elif event == "ALERT":
            item: ParsedItem = data["item"]
            console.print(f"\n[dim]{now_str}[/dim] [bold yellow]🔔 НОВОЕ ОБЪЯВЛЕНИЕ [{data['search']}]:[/bold yellow] [bold]{item.title}[/bold] — [green]{item.price_formatted}[/green]")
            if item.tags:
                console.print(f"      [dim]Теги: {', '.join(item.tags)}[/dim]")
            console.print(f"      [cyan]{item.url}[/cyan]\n")
        elif event == "REPUBLISHED_IGNORED":
            console.print(f"[dim]{now_str} · пропущено переопубликованное старое: {data['item']} ({data['views']} просмотров)[/dim]")
        elif event == "TELEGRAM_ERROR":
            console.print(f"[red]✗ Ошибка Telegram: {data['error']}[/red]")
        elif event == "WATCH_ERROR":
            console.print(f"[yellow]⚠ Ошибка запроса ({data['search']}): {data['error']}[/yellow]")
        elif event == "CYCLE_COMPLETE":
            console.print(f"[dim]{now_str} · цикл #{data['cycle']} завершён. Следующая проверка через {data['next_in_seconds']} сек...[/dim]")
        elif event == "WATCH_STOPPED":
            console.print("\n[yellow]Мониторинг остановлен.[/yellow]")

    watch_searches(searches, settings=settings, interval_seconds=inter, on_event=on_event)


def cmd_export(name: str) -> None:
    search = load_search(name)
    if not search:
        console.print(f"[red]Поиск «{name}» не найден.[/red]")
        return

    raw_listings = load_listings(search)
    if not raw_listings:
        console.print(f"[yellow]В поиске «{name}» пока нет объявлений. Сначала запустите сбор (scan).[/yellow]")
        return

    items: list[ParsedItem] = []
    for raw in raw_listings.values():
        parsed = parse_catalog_item(raw)
        classify_item(parsed, category_type=search.category_type)
        items.append(parsed)

    annotate_market_prices(
        items,
        group_key_fn=lambda x: extract_goods_group(x.title) if search.category_type == "goods" else "all",
    )

    path = export_to_excel(search.name, items)
    console.print(f"[bold green]✓ Экспорт готов:[/bold green] [underline]{path}[/underline]")
    if sys.platform.startswith("win") and prompt_confirm("Открыть файл Excel?", default=True):
        os.startfile(str(path))


def cmd_telegram_setup() -> None:
    console.print(Panel(
        "1. Откройте Telegram и найдите официального бота [bold cyan]@BotFather[/bold cyan]\n"
        "2. Отправьте команду [bold]/newbot[/bold] и задайте имя для своего бота\n"
        "3. Скопируйте полученный [bold]API токен[/bold] (вида 123456:ABC-DEF...)",
        title="[bold]Подключение Telegram-бота[/bold]",
    ))

    token = prompt_text("Вставьте токен бота").strip()
    if not token:
        console.print("[red]Токен не указан.[/red]")
        return

    console.print(f"\n[cyan]Проверяю токен...[/cyan]")
    try:
        me = TelegramNotifier(TelegramConfig(token=token, chat_id=0)).api_get_me(token) if hasattr(TelegramNotifier, 'api_get_me') else None
    except Exception:
        pass

    console.print(f"[yellow]Теперь откройте вашего бота в Telegram, отправьте ему сообщение [bold]/start[/bold] и нажмите Enter.[/yellow]")
    input("Нажмите Enter после отправки /start...")

    try:
        chat_id, user_name = auto_detect_chat_id(token)
        cfg = TelegramConfig(token=token, chat_id=chat_id, enabled=True)
        save_telegram_config(cfg)
        notifier = TelegramNotifier(cfg)
        notifier.send_test_message()
        console.print(Panel(
            f"[bold green]✓ Бот успешно привязан к чату «{user_name}» (ID: {chat_id})![/bold green]\n"
            f"Тестовое уведомление отправлено.",
            border_style="green",
        ))
    except Exception as exc:
        console.print(f"[bold red]✗ Не удалось определить чат:[/bold red] {exc}")


def cmd_telegram_test() -> None:
    cfg = load_telegram_config()
    if not cfg:
        console.print("[yellow]Telegram ещё не настроен. Запустите настройку через меню или команду `python run.py telegram`.[/yellow]")
        return
    try:
        notifier = TelegramNotifier(cfg)
        notifier.send_test_message()
        console.print("[green]✓ Тестовое сообщение успешно отправлено в Telegram![/green]")
    except Exception as exc:
        console.print(f"[red]✗ Ошибка отправки:[/red] {exc}")


# ==============================================================================
# Interactive Menu
# ==============================================================================

def interactive_menu() -> None:
    while True:
        show_banner()
        menu_items = [
            "➕ Добавить поиск по ссылке с Авито",
            "📋 Мои поиски (список и управление)",
            "🚀 Собрать все объявления (Scan в Excel)",
            "👁 Мониторинг в реальном времени (Watch + Telegram)",
            "📊 Экспорт поиска в Excel (.xlsx)",
            "🤖 Интерактивный Telegram-бот (управление кнопками)",
            "⚙️ Настройка Telegram / Настройки парсера",
        ]

        choice = prompt_choice("Главное меню", menu_items)
        if choice is None:
            console.print("\n[dim]До свидания![/dim]\n")
            break

        if choice == 0:  # Add
            console.print("\n[bold]Вставьте полную ссылку на поиск или категорию с Авито:[/bold]")
            url = prompt_text("URL").strip()
            if url:
                c_name = prompt_text("Своё имя для поиска (оставьте пустым для авто)", default="").strip() or None
                cmd_add(url, custom_name=c_name)
                searches = list_searches()
                latest = searches[-1] if searches else None
                if latest and prompt_confirm("Собрать объявления по этому поиску прямо сейчас?", default=True):
                    cmd_scan(latest.name)
            input("\nНажмите Enter для продолжения...")

        elif choice == 1:  # List
            cmd_list()
            searches = list_searches()
            if searches:
                sub_choice = prompt_choice("Действие с поиском", ["Собрать (Scan)", "Следить (Watch)", "Экспорт в Excel", "Удалить поиск"])
                if sub_choice is not None:
                    target_idx = prompt_choice("Выберите поиск", [s.name for s in searches])
                    if target_idx is not None:
                        target_search = searches[target_idx]
                        if sub_choice == 0:
                            cmd_scan(target_search.name)
                        elif sub_choice == 1:
                            cmd_watch([target_search.name])
                        elif sub_choice == 2:
                            cmd_export(target_search.name)
                        elif sub_choice == 3:
                            if prompt_confirm(f"Точно удалить поиск «{target_search.name}»?", default=False):
                                delete_search(target_search.name)
                                console.print(f"[green]✓ Поиск «{target_search.name}» удалён.[/green]")
            input("\nНажмите Enter для продолжения...")

        elif choice == 2:  # Scan
            searches = list_searches()
            if not searches:
                console.print("[yellow]Нет сохранённых поисков.[/yellow]")
            else:
                idx = prompt_choice("Какой поиск собрать?", [f"{s.name} ({s.title})" for s in searches])
                if idx is not None:
                    cmd_scan(searches[idx].name)
            input("\nНажмите Enter для продолжения...")

        elif choice == 3:  # Watch
            searches = list_searches()
            if not searches:
                console.print("[yellow]Нет сохранённых поисков.[/yellow]")
            else:
                options = ["Следить за ВСЕМИ поисками"] + [f"{s.name} ({s.title})" for s in searches]
                w_choice = prompt_choice("За чем следить?", options)
                if w_choice is not None:
                    target_names = [s.name for s in searches] if w_choice == 0 else [searches[w_choice - 1].name]
                    speeds = [
                        ("Быстро (раз в 1 минуту)", 60),
                        ("Стандартно (раз в 2 минуты, рекомендуется)", 120),
                        ("Спокойно (раз в 4 минуты)", 240),
                    ]
                    sp_idx = prompt_choice("Интервал проверки", [s[0] for s in speeds])
                    interval = speeds[sp_idx][1] if sp_idx is not None else 120
                    cmd_watch(target_names, interval=interval)
            input("\nНажмите Enter для продолжения...")

        elif choice == 4:  # Export
            searches = list_searches()
            if not searches:
                console.print("[yellow]Нет сохранённых поисков.[/yellow]")
            else:
                idx = prompt_choice("Какой поиск экспортировать?", [s.name for s in searches])
                if idx is not None:
                    cmd_export(searches[idx].name)
            input("\nНажмите Enter для продолжения...")

        elif choice == 5:  # Bot launcher
            console.print(Panel(
                "[bold green]Запуск интерактивного Telegram-бота...[/bold green]\n"
                "• Вы можете управлять поиском через кнопки прямо в Telegram!\n"
                "• Для остановки бота нажмите Ctrl+C.",
                title="Telegram Bot Service",
            ))
            from avito_radar.telegram_bot import start_bot_service
            start_bot_service()
            input("\nНажмите Enter для продолжения...")

        elif choice == 6:  # Settings & Telegram Setup
            tg_cfg = load_telegram_config()
            status = f"[green]Подключен (чат: {tg_cfg.chat_id})[/green]" if tg_cfg else "[yellow]Не настроен[/yellow]"
            console.print(f"\nСтатус Telegram: {status}")
            sub_set = prompt_choice("Что настроить?", [
                "Привязать Telegram заново / Тест",
                "Параметры парсера (задержки, фильтры)",
            ])
            if sub_set == 0:
                tg_choice = prompt_choice("Telegram", ["Настроить заново / подключить", "Отправить тестовое сообщение"])
                if tg_choice == 0:
                    cmd_telegram_setup()
                elif tg_choice == 1:
                    cmd_telegram_test()
            elif sub_set == 1:
                cfg = load_settings()
                console.print(Panel(
                    f"• Задержка между запросами: [bold]{cfg.request_delay} с[/bold]\n"
                    f"• Интервал мониторинга: [bold]{cfg.watch_interval} с[/bold]\n"
                    f"• Максимум страниц при сборе: [bold]{cfg.max_scan_pages}[/bold]\n"
                    f"• Фильтр: только частные продавцы: [bold]{'Да' if cfg.alert_private_only else 'Нет'}[/bold]\n"
                    f"• Фильтр: исключать старые переопубликованные: [bold]{'Да' if cfg.alert_no_republished else 'Нет'}[/bold]",
                    title="Текущие настройки",
                ))
                if prompt_confirm("Изменить настройки?", default=False):
                    try:
                        cfg.request_delay = float(prompt_text("Задержка между запросами (сек)", default=str(cfg.request_delay)))
                        cfg.watch_interval = float(prompt_text("Интервал мониторинга (сек)", default=str(cfg.watch_interval)))
                        cfg.max_scan_pages = int(prompt_text("Макс. страниц сканирования", default=str(cfg.max_scan_pages)))
                        cfg.alert_private_only = prompt_confirm("Уведомлять только о частных лицах?", default=cfg.alert_private_only)
                        cfg.alert_no_republished = prompt_confirm("Исключать переопубликованные объявления?", default=cfg.alert_no_republished)
                        save_settings(cfg)
                        console.print("[green]✓ Настройки сохранены![/green]")
                    except ValueError as err:
                        console.print(f"[red]Ошибка ввода: {err}[/red]")
            input("\nНажмите Enter для продолжения...")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main() -> None:
    if len(sys.argv) <= 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(description="Avito Radar — личный парсер и монитор Авито")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_add = subparsers.add_parser("add", help="добавить поиск по ссылке")
    p_add.add_argument("url", help="URL страницы каталога Авито")
    p_add.add_argument("--name", help="своё имя поиска")

    subparsers.add_parser("list", help="список сохранённых поисков")

    p_scan = subparsers.add_parser("scan", help="собрать все объявления")
    p_scan.add_argument("name", help="имя поиска")
    p_scan.add_argument("--full", action="store_true", help="начать заново с 1 страницы")
    p_scan.add_argument("--pages", type=int, help="макс. число страниц")

    p_watch = subparsers.add_parser("watch", help="мониторинг в реальном времени")
    p_watch.add_argument("names", nargs="+", help="имена поисков")
    p_watch.add_argument("--interval", type=float, help="интервал проверки в секундах")

    p_export = subparsers.add_parser("export", help="экспорт в Excel")
    p_export.add_argument("name", help="имя поиска")

    p_tg = subparsers.add_parser("telegram", help="настройка или тест Telegram")
    p_tg.add_argument("--setup", action="store_true", help="мастер настройки")
    p_tg.add_argument("--test", action="store_true", help="отправить тестовое сообщение")

    subparsers.add_parser("bot", help="запустить интерактивного Telegram-бота")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.url, custom_name=args.name)
    elif args.command == "list":
        cmd_list()
    elif args.command == "scan":
        cmd_scan(args.name, full=args.full, max_pages=args.pages)
    elif args.command == "watch":
        cmd_watch(args.names, interval=args.interval)
    elif args.command == "export":
        cmd_export(args.name)
    elif args.command == "bot":
        from avito_radar.telegram_bot import start_bot_service
        start_bot_service()
    elif args.command == "telegram":
        if args.setup:
            cmd_telegram_setup()
        elif args.test:
            cmd_telegram_test()
        else:
            cmd_telegram_setup()


if __name__ == "__main__":
    main()
