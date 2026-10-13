#!/usr/bin/env python3
"""Build script for Avito Radar Mini App."""
import json
import shutil
from pathlib import Path
from avito_radar.telegram_bot import generate_api_bundle

def generate_html() -> str:
    bundle = generate_api_bundle()
    bundle_json = json.dumps(bundle, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Смотрящий за Авито — Radar Terminal</title>
  
  <!-- Telegram WebApp SDK -->
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  
  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            neon: {{
              DEFAULT: '#00ff88',
              glow: 'rgba(0, 255, 136, 0.25)',
              border: 'rgba(0, 255, 136, 0.45)',
              dim: '#00cc6a',
            }},
            amber: {{
              neon: '#ffb703',
              glow: 'rgba(255, 183, 3, 0.25)',
            }},
            crimson: {{
              neon: '#ff3366',
              glow: 'rgba(255, 51, 102, 0.25)',
            }},
            dark: {{
              bg: '#040404',
              surface: '#0b0b0e',
              card: '#111115',
              cardHover: '#17171d',
              border: 'rgba(255, 255, 255, 0.08)',
              borderHighlight: 'rgba(255, 255, 255, 0.18)',
              glass: 'rgba(14, 14, 18, 0.82)',
            }}
          }},
          fontFamily: {{
            sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"SF Pro Text"', 'Inter', 'sans-serif'],
            mono: ['"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
          }}
        }}
      }}
    }}
  </script>

  <style>
    /* iOS Momentum Scrolling & Touch Resets */
    * {{
      -webkit-tap-highlight-color: transparent;
      user-select: none;
      box-sizing: border-box;
    }}
    input, textarea, select {{
      user-select: text;
    }}
    body {{
      background-color: #040404;
      color: #f4f4f5;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", sans-serif;
      padding-top: env(safe-area-inset-top, 0px);
      padding-bottom: calc(env(safe-area-inset-bottom, 20px) + 20px);
      overflow-x: hidden;
      min-height: 100vh;
    }}

    /* Bento Grid Glassmorphic Cards */
    .bento-card {{
      background: #0b0b0e;
      border: 1px solid rgba(255, 255, 255, 0.07);
      backdrop-filter: blur(28px);
      -webkit-backdrop-filter: blur(28px);
      transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .bento-card:active {{
      transform: scale(0.992);
      border-color: rgba(255, 255, 255, 0.16);
    }}

    /* Subtle Micro-Glow effects */
    .glow-neon-card {{
      border-color: rgba(0, 255, 136, 0.38) !important;
      box-shadow: 0 0 25px -4px rgba(0, 255, 136, 0.16), inset 0 0 15px -8px rgba(0, 255, 136, 0.15);
    }}
    .glow-amber-card {{
      border-color: rgba(255, 183, 3, 0.38) !important;
      box-shadow: 0 0 25px -4px rgba(255, 183, 3, 0.15);
    }}
    .glow-crimson-card {{
      border-color: rgba(255, 51, 102, 0.38) !important;
      box-shadow: 0 0 25px -4px rgba(255, 51, 102, 0.15);
    }}

    /* Radar sweep animation */
    .radar-sweep-container {{
      position: relative;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 1px solid rgba(0, 255, 136, 0.25);
      background: radial-gradient(circle, rgba(0, 255, 136, 0.08) 0%, transparent 70%);
      overflow: hidden;
    }}
    .radar-sweep-beam {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      border-radius: 50%;
      background: conic-gradient(from 0deg, rgba(0, 255, 136, 0.45) 0deg, transparent 65deg, transparent 360deg);
      animation: radarSpin 2.4s linear infinite;
    }}
    @keyframes radarSpin {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}

    /* Header Glass */
    .glass-nav {{
      background: rgba(4, 4, 4, 0.88);
      backdrop-filter: blur(32px);
      -webkit-backdrop-filter: blur(32px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }}

    /* Filter pill */
    .filter-chip {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: #a1a1aa;
      transition: all 0.2s ease;
    }}
    .filter-chip.active {{
      background: #00ff88;
      color: #040404;
      font-weight: 700;
      border-color: #00ff88;
      box-shadow: 0 0 18px rgba(0, 255, 136, 0.35);
    }}

    /* View Mode Switcher */
    .segmented-btn.active {{
      background: #17171d;
      color: #ffffff;
      border-color: rgba(255, 255, 255, 0.16);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
    }}

    /* Modal bottom sheet transitions */
    #bottomSheet, #newSearchModal, #deleteConfirmModal {{
      transition: transform 0.32s cubic-bezier(0.16, 1, 0.3, 1);
      transform: translateY(100%);
    }}
    #bottomSheet.open, #newSearchModal.open, #deleteConfirmModal.open {{
      transform: translateY(0%);
    }}
    #modalBackdrop {{
      transition: opacity 0.26s ease;
      opacity: 0;
      pointer-events: none;
    }}
    #modalBackdrop.open {{
      opacity: 1;
      pointer-events: auto;
    }}

    /* Scrollbar */
    .no-scrollbar::-webkit-scrollbar {{ display: none; }}
    .no-scrollbar {{ -ms-overflow-style: none; scrollbar-width: none; }}
  </style>
</head>
<body class="flex flex-col antialiased">

  <!-- Toast Notification floating pill -->
  <div id="toastNotification" class="fixed top-3 inset-x-4 z-50 pointer-events-none flex justify-center transition-all duration-300 opacity-0 -translate-y-4">
    <div id="toastContent" class="pointer-events-auto px-4 py-2 rounded-2xl bg-zinc-900/95 border border-zinc-700/80 backdrop-blur-xl text-xs font-mono font-bold text-white shadow-2xl flex items-center gap-2">
      <span id="toastIcon">⚡</span>
      <span id="toastMessage">Уведомление</span>
    </div>
  </div>

  <!-- Sticky Top Glass Header -->
  <header class="sticky top-0 z-40 glass-nav px-4 pt-3 pb-2.5 space-y-2.5">
    <!-- Brand row -->
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-2.5">
        <div class="radar-sweep-container flex items-center justify-center">
          <div class="radar-sweep-beam"></div>
          <span class="relative text-sm z-10">👁️</span>
        </div>
        <div>
          <div class="flex items-center gap-1.5">
            <h1 class="text-sm font-extrabold tracking-tight text-white uppercase font-mono">AVITO // RADAR</h1>
            <span class="text-[9px] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded bg-neon/15 text-neon border border-neon/30">TERMINAL</span>
          </div>
          <p id="monitoringSub" class="text-[11px] text-zinc-400 font-mono tracking-tight flex items-center gap-1.5">
            <span class="inline-block w-1.5 h-1.5 rounded-full bg-neon animate-pulse"></span>
            24/7 Monitoring Active
          </p>
        </div>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center space-x-1.5">
        <button onclick="setViewMode('searches')" id="btnHeaderSearches" class="px-2.5 py-1.5 rounded-xl bg-zinc-900 border border-dark-border text-xs text-zinc-200 active:scale-95 flex items-center gap-1.5 font-medium transition-all">
          <span class="text-neon text-xs">🎯</span>
          <span>Поиски</span>
        </button>
        <button onclick="openNewSearchModal()" class="px-2.5 py-1.5 rounded-xl bg-neon/15 border border-neon/30 text-xs text-neon active:scale-95 flex items-center gap-1.5 font-medium transition-all">
          <span class="text-neon text-sm font-bold">+</span>
          <span>Создать</span>
        </button>
        <button onclick="refreshData()" id="btnRefresh" title="Синхронизировать" class="p-2 rounded-xl bg-zinc-900 border border-dark-border text-zinc-300 active:scale-95 transition-all">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        </button>
      </div>
    </div>

    <!-- Search selector & Quick filter (Hidden in Searches Management view) -->
    <div id="searchControlsRow" class="grid grid-cols-1 gap-2">
      <div class="relative">
        <select id="searchSelector" onchange="onSearchChange()" class="w-full bg-zinc-950 text-white text-xs font-semibold rounded-xl px-3.5 py-2.5 border border-zinc-800 focus:border-neon focus:outline-none appearance-none pr-8 truncate font-mono">
          <!-- Populated by JS -->
        </select>
        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-zinc-500">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
        </div>
      </div>

      <div class="relative flex items-center">
        <svg class="w-3.5 h-3.5 text-zinc-500 absolute left-3 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        <input type="text" id="filterKeyword" oninput="applyFilters()" placeholder="Фильтр по ключевым словам..." class="w-full bg-zinc-950/80 text-xs text-white placeholder-zinc-600 rounded-xl pl-9 pr-8 py-2 border border-zinc-850 focus:border-neon focus:outline-none font-mono">
        <button id="btnClearKeyword" onclick="clearKeyword()" class="hidden absolute right-2.5 text-zinc-500 hover:text-white text-xs p-1">✕</button>
      </div>
    </div>

    <!-- View Switcher & Filters -->
    <div class="flex items-center justify-between pt-0.5">
      <!-- Segmented View Toggle -->
      <div class="flex p-0.5 rounded-xl bg-zinc-950 border border-zinc-850 text-xs font-medium">
        <button onclick="setViewMode('feed')" id="viewMode-feed" class="segmented-btn active px-2.5 py-1 rounded-lg transition-all text-xs">
          🎴 Карточки
        </button>
        <button onclick="setViewMode('table')" id="viewMode-table" class="segmented-btn px-2.5 py-1 rounded-lg text-zinc-400 transition-all text-xs">
          📊 Таблица
        </button>
        <button onclick="setViewMode('fav')" id="viewMode-fav" class="segmented-btn px-2 py-1 rounded-lg text-zinc-400 transition-all text-xs flex items-center gap-1">
          <span>★</span> <span id="favCount" class="text-[10px] text-amber-neon">0</span>
        </button>
        <button onclick="setViewMode('searches')" id="viewMode-searches" class="segmented-btn px-2.5 py-1 rounded-lg text-zinc-400 transition-all text-xs flex items-center gap-1">
          <span>🎯</span> <span>Поиски</span>
        </button>
      </div>

      <!-- Sort selector (Hidden in Searches view) -->
      <select id="sortSelector" onchange="onSortChange()" class="bg-zinc-950 text-zinc-300 text-[11px] rounded-xl px-2.5 py-1.5 border border-zinc-850 focus:outline-none font-mono">
        <option value="deal">🔥 По выгоде</option>
        <option value="cheap">📉 Дешевле</option>
        <option value="expensive">📈 Дороже</option>
        <option value="date">⏱ Новые</option>
      </select>
    </div>

    <!-- Filter chips scroll (Hidden in Searches view) -->
    <div id="filterChipsRow" class="flex space-x-1.5 overflow-x-auto no-scrollbar pt-0.5 pb-1">
      <button onclick="setFilterCategory('all')" id="chip-all" class="filter-chip active whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-medium font-mono">
        Все <span id="count-all" class="opacity-70 ml-0.5"></span>
      </button>
      <button onclick="setFilterCategory('deals')" id="chip-deals" class="filter-chip whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-medium font-mono">
        🔥 Только выгода <span id="count-deals" class="opacity-70 ml-0.5"></span>
      </button>
      <button onclick="setFilterCategory('private')" id="chip-private" class="filter-chip whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-medium font-mono">
        👤 Частники
      </button>
      <button onclick="setFilterCategory('delivery')" id="chip-delivery" class="filter-chip whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-medium font-mono">
        📦 Доставка
      </button>
      <button onclick="setFilterCategory('nodefects')" id="chip-nodefects" class="filter-chip whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-medium font-mono">
        🛡 Без дефектов
      </button>
    </div>
  </header>

  <!-- Bento Grid Hero Section (Hidden in Searches view) -->
  <section id="bentoHero" class="px-4 pt-3.5 pb-2">
    <div class="grid grid-cols-2 gap-2.5">
      <!-- Tile 1: Market Median -->
      <div class="bento-card rounded-2xl p-3 border-dark-border flex flex-col justify-between">
        <div class="flex items-center justify-between text-zinc-400 text-[10px] font-mono uppercase tracking-wider">
          <span>Рыночная цена</span>
          <span class="text-xs">📊</span>
        </div>
        <div class="mt-1">
          <div id="heroMarketPrice" class="text-xl font-extrabold text-white font-mono">—</div>
          <p id="heroMarketHint" class="text-[10px] text-zinc-500 font-mono mt-0.5">честная медиана</p>
        </div>
      </div>

      <!-- Tile 2: Deals Spotlight -->
      <div class="bento-card rounded-2xl p-3 border-dark-border flex flex-col justify-between relative overflow-hidden">
        <div class="flex items-center justify-between text-zinc-400 text-[10px] font-mono uppercase tracking-wider">
          <span>Супер-цены</span>
          <span class="text-neon text-xs">⚡</span>
        </div>
        <div class="mt-1">
          <div class="flex items-baseline gap-1.5">
            <span id="heroDealsCount" class="text-xl font-extrabold text-neon font-mono">0</span>
            <span id="heroTopDiscount" class="text-[10px] font-bold text-neon font-mono px-1.5 py-0.2 rounded bg-neon/15">0%</span>
          </div>
          <p class="text-[10px] text-zinc-500 font-mono mt-0.5">ниже рынка</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Main Feed Container (Cards View) -->
  <main id="feedContainer" class="px-4 py-2 space-y-3 pb-24">
    <!-- Dynamic Cards Inserted Here -->
  </main>

  <!-- Table View Container (Full in-app Excel replacement) -->
  <section id="tableContainer" class="hidden px-4 py-2 pb-24">
    <div class="bento-card rounded-2xl overflow-hidden border border-dark-border">
      <div class="overflow-x-auto no-scrollbar">
        <table class="w-full text-left text-xs font-mono">
          <thead class="bg-zinc-950 text-zinc-400 uppercase text-[10px] border-b border-dark-border">
            <tr>
              <th class="py-2.5 px-3">Лот</th>
              <th class="py-2.5 px-3">Цена</th>
              <th class="py-2.5 px-3">Рынок</th>
              <th class="py-2.5 px-3">Выгода</th>
              <th class="py-2.5 px-3">Продавец</th>
              <th class="py-2.5 px-3">Действие</th>
            </tr>
          </thead>
          <tbody id="tableBody" class="divide-y divide-zinc-900 text-zinc-300">
            <!-- Table Rows Inserted Here -->
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- Searches Management Container -->
  <section id="searchesContainer" class="hidden px-4 py-2 pb-24 space-y-3">
    <!-- Searches Hero Tile -->
    <div class="bento-card rounded-2xl p-4 border-dark-border space-y-2.5">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="text-lg">🎯</span>
          <div>
            <h2 class="text-sm font-extrabold text-white font-mono uppercase tracking-tight">Управление радарами</h2>
            <p class="text-[10px] text-zinc-400 font-mono">Мониторинг 24/7 новых объявлений</p>
          </div>
        </div>
        <span id="searchesCountBadge" class="text-[10px] font-bold font-mono px-2 py-0.5 rounded-full bg-neon/15 text-neon border border-neon/30">0 радаров</span>
      </div>
      <p class="text-xs text-zinc-400 leading-relaxed font-mono">
        Создавайте новые поисковые запросы по любым товарам с отсечением фейковых цен или удаляйте завершенные поиски.
      </p>
      <button onclick="openNewSearchModal()" class="w-full py-3 px-4 rounded-xl bg-neon text-black font-extrabold text-xs font-mono tracking-tight flex items-center justify-center gap-2 active:scale-98 transition-all shadow-lg shadow-neon/15">
        <span class="text-base font-black leading-none">+</span>
        <span>СОЗДАТЬ НОВЫЙ ПОИСК</span>
      </button>
    </div>

    <!-- Active Searches List -->
    <div id="searchesList" class="space-y-3">
      <!-- Search items rendered here -->
    </div>
  </section>

  <!-- Empty State Placeholder -->
  <div id="emptyState" class="hidden flex-col items-center justify-center text-center py-20 px-6 space-y-3">
    <div class="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-xl">🔍</div>
    <div class="text-sm font-bold text-white font-mono">Нет лотов по заданным фильтрам</div>
    <p class="text-xs text-zinc-500 max-w-xs font-mono">Попробуйте сбросить фильтры или добавьте новый поисковый запрос.</p>
    <button onclick="resetFilters()" class="text-xs bg-neon/15 text-neon border border-neon/30 px-4 py-2 rounded-xl font-mono mt-2 active:scale-95">Сбросить фильтры</button>
  </div>

  <!-- iOS Bottom Sheet Detail Modal -->
  <div id="modalBackdrop" onclick="closeAllModals()" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md"></div>
  <div id="bottomSheet" class="fixed inset-x-0 bottom-0 z-50 max-h-[92vh] flex flex-col bg-[#08080a] border-t border-zinc-800 rounded-t-[32px] shadow-2xl overflow-hidden">
    <!-- Drag Handle -->
    <div class="flex justify-center pt-3 pb-1 cursor-grab" onclick="closeAllModals()">
      <div class="w-10 h-1 bg-zinc-700 rounded-full"></div>
    </div>

    <!-- Modal Content -->
    <div class="overflow-y-auto px-5 pt-2 pb-8 space-y-4 flex-1">
      <!-- Media Gallery -->
      <div id="modalGallery" class="relative rounded-2xl overflow-hidden aspect-[16/10] bg-zinc-950 border border-zinc-850">
        <img id="modalMainImg" src="" alt="" class="w-full h-full object-cover">
        <div id="modalDealBadge" class="absolute top-3 left-3 px-3 py-1 rounded-full text-xs font-black bg-neon text-black font-mono shadow-lg"></div>
        <button id="modalFavBtn" onclick="toggleModalFav()" class="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/70 backdrop-blur-md border border-white/20 flex items-center justify-center text-sm text-zinc-300">
          ★
        </button>
      </div>

      <!-- Price & Market Header -->
      <div class="space-y-1">
        <div class="flex items-baseline justify-between font-mono">
          <div id="modalPrice" class="text-2xl font-black text-white"></div>
          <div id="modalMarketPrice" class="text-xs text-zinc-400"></div>
        </div>
        <h2 id="modalTitle" class="text-sm font-semibold text-zinc-200 leading-snug"></h2>
      </div>

      <!-- Combo Listing Alert Warning -->
      <div id="modalComboWarning" class="hidden rounded-xl p-3 bg-amber-neon/10 border border-amber-neon/30 text-amber-neon text-xs space-y-1 font-mono">
        <div class="font-bold flex items-center gap-1.5">
          <span>⚠️</span> ВНИМАНИЕ: СБОРНЫЙ ЛОТ
        </div>
        <p id="modalComboWarningText" class="text-[11px] text-amber-200/90 leading-relaxed"></p>
      </div>

      <!-- Tags Breakdown -->
      <div id="modalTags" class="flex flex-wrap gap-1.5"></div>

      <!-- Seller Info Card -->
      <div class="bento-card rounded-2xl p-3.5 border-dark-border space-y-2 text-xs">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-base">👤</span>
            <div>
              <div id="modalSellerName" class="font-bold text-white"></div>
              <div id="modalSellerType" class="text-[10px] text-zinc-500 font-mono"></div>
            </div>
          </div>
          <div id="modalSellerRating" class="text-amber-neon font-bold text-xs bg-amber-neon/10 border border-amber-neon/20 px-2 py-0.5 rounded-lg font-mono">★ 5.0</div>
        </div>
        <div class="border-t border-zinc-900 pt-2 flex items-center justify-between text-[11px] text-zinc-400 font-mono">
          <span id="modalLocation">📍 Челябинск</span>
          <span id="modalDate">⏱ 2 ч назад</span>
        </div>
      </div>

      <!-- Full Description -->
      <div class="space-y-1.5">
        <h3 class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider font-mono">Описание лота</h3>
        <div id="modalDescription" class="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap bg-zinc-950 p-3.5 rounded-2xl border border-zinc-850 max-h-48 overflow-y-auto"></div>
      </div>

      <!-- Action Button -->
      <div class="pt-2">
        <a id="modalAvitoLink" href="#" target="_blank" onclick="openAvitoLink(event)" class="w-full bg-neon active:bg-neon-dim text-black font-extrabold text-sm py-3.5 px-4 rounded-2xl flex items-center justify-center space-x-2 shadow-lg shadow-neon/20 transition-all font-mono tracking-tight">
          <span>ОТКРЫТЬ НА АВИТО</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
      </div>
    </div>
  </div>

  <!-- In-App "Add Search" Modal -->
  <div id="newSearchModal" class="fixed inset-x-0 bottom-0 z-50 max-h-[92vh] flex flex-col bg-[#08080a] border-t border-zinc-800 rounded-t-[32px] shadow-2xl overflow-hidden pb-8">
    <div class="flex justify-center pt-3 pb-1 cursor-grab" onclick="closeAllModals()">
      <div class="w-10 h-1 bg-zinc-700 rounded-full"></div>
    </div>
    <div class="px-5 pt-3 space-y-4 flex-1 overflow-y-auto">
      <div>
        <h2 class="text-base font-bold text-white font-mono uppercase tracking-tight flex items-center gap-1.5">
          <span class="text-neon">+</span> Создать новый поиск
        </h2>
        <p class="text-xs text-zinc-400">Настройте радар для отслеживания любого товара</p>
      </div>

      <div class="space-y-3 font-mono text-xs">
        <div>
          <label class="block text-zinc-400 mb-1">Товар / Поисковый запрос</label>
          <input type="text" id="newQueryInput" placeholder="Например: RX 6700 XT, RTX 4070, PS5, Велосипед" class="w-full bg-zinc-950 text-white rounded-xl px-3.5 py-2.5 border border-zinc-800 focus:border-neon focus:outline-none">
          
          <!-- Quick presets -->
          <div class="flex items-center gap-1.5 flex-wrap pt-2">
            <span class="text-[10px] text-zinc-500">Быстрый выбор:</span>
            <button type="button" onclick="setQueryPreset('RX 6700 XT', 25000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">RX 6700 XT</button>
            <button type="button" onclick="setQueryPreset('RTX 4070', 40000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">RTX 4070</button>
            <button type="button" onclick="setQueryPreset('PlayStation 5', 30000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">PS 5</button>
            <button type="button" onclick="setQueryPreset('iPhone 14', 35000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">iPhone 14</button>
          </div>
        </div>

        <div>
          <label class="block text-zinc-400 mb-1">Город или Регион</label>
          <select id="newCitySelect" onchange="toggleCustomCity(this.value)" class="w-full bg-zinc-950 text-white rounded-xl px-3.5 py-2.5 border border-zinc-800 focus:border-neon focus:outline-none">
            <option value="chelyabinsk">Челябинск</option>
            <option value="moskva">Москва</option>
            <option value="sankt-peterburg">Санкт-Петербург</option>
            <option value="ekaterinburg">Екатеринбург</option>
            <option value="kazan">Казань</option>
            <option value="novosibirsk">Новосибирск</option>
            <option value="ufa">Уфа</option>
            <option value="rossiya">Вся Россия</option>
            <option value="custom">✏️ Другой город (ввести вручную)</option>
          </select>
          <div id="customCityContainer" class="hidden pt-2">
            <input type="text" id="newCustomCityInput" placeholder="Введите название города на русском (например: Самара)" class="w-full bg-zinc-950 text-white rounded-xl px-3.5 py-2.5 border border-zinc-800 focus:border-neon focus:outline-none">
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-zinc-400">Мин. цена отсечения (₽)</label>
            <span class="text-[10px] text-zinc-500">Защита от байт-цен (100 ₽)</span>
          </div>
          <input type="number" id="newMinPriceInput" placeholder="0 (без ограничения)" class="w-full bg-zinc-950 text-white rounded-xl px-3.5 py-2.5 border border-zinc-800 focus:border-neon focus:outline-none">
          <div class="flex items-center gap-1.5 flex-wrap pt-2">
            <button type="button" onclick="setMinPricePreset(0)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">0 ₽</button>
            <button type="button" onclick="setMinPricePreset(10000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">10 000 ₽</button>
            <button type="button" onclick="setMinPricePreset(25000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">25 000 ₽</button>
            <button type="button" onclick="setMinPricePreset(40000)" class="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 active:scale-95">40 000 ₽</button>
          </div>
        </div>
      </div>

      <button id="btnSubmitNewSearch" onclick="submitNewSearch()" class="w-full bg-neon text-black font-extrabold text-xs py-3.5 px-4 rounded-xl flex items-center justify-center space-x-2 font-mono tracking-tight mt-4 active:scale-98 transition-all shadow-lg shadow-neon/20">
        <span>🚀 ЗАПУСТИТЬ РАДАР</span>
      </button>
    </div>
  </div>

  <!-- Delete Confirmation Modal -->
  <div id="deleteConfirmModal" class="fixed inset-x-0 bottom-0 z-50 max-h-[90vh] flex flex-col bg-[#08080a] border-t border-zinc-800 rounded-t-[32px] shadow-2xl overflow-hidden pb-8">
    <div class="flex justify-center pt-3 pb-1 cursor-grab" onclick="closeAllModals()">
      <div class="w-10 h-1 bg-zinc-700 rounded-full"></div>
    </div>
    <div class="px-5 pt-3 space-y-4 flex-1">
      <div class="flex items-center gap-2.5">
        <div class="w-10 h-10 rounded-2xl bg-crimson-neon/10 border border-crimson-neon/30 flex items-center justify-center text-lg">⚠️</div>
        <div>
          <h2 class="text-base font-bold text-white font-mono uppercase tracking-tight">Удалить поиск?</h2>
          <p class="text-xs text-zinc-400">Радар перестанет отслеживать этот товар</p>
        </div>
      </div>

      <div class="p-3.5 rounded-xl bg-zinc-950 border border-zinc-850 text-xs font-mono text-zinc-300 space-y-1.5">
        <div>Запрос: <b id="deleteModalTitle" class="text-white"></b></div>
        <div class="text-[11px] text-zinc-400">Собранных объявлений: <span id="deleteModalCount" class="text-zinc-200">0</span> шт.</div>
        <p class="text-[11px] text-zinc-500 pt-1.5 border-t border-zinc-900">Все сохраненные данные и история лотов по этому поиску будут удалены.</p>
      </div>

      <div class="flex items-center gap-2 pt-2">
        <button onclick="closeAllModals()" class="flex-1 py-3 px-4 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-bold text-xs font-mono active:scale-95 transition-all text-center">
          ОТМЕНА
        </button>
        <button onclick="confirmDeleteSearch()" class="flex-1 py-3 px-4 rounded-xl bg-crimson-neon text-white font-extrabold text-xs font-mono active:scale-95 transition-all text-center shadow-lg shadow-crimson-neon/25">
          🗑 ДА, УДАЛИТЬ
        </button>
      </div>
    </div>
  </div>

  <script>
    // Embedded initial data bundle
    window.__INITIAL_DATA__ = {bundle_json};

    // State Variables
    let allSearches = window.__INITIAL_DATA__ || {{}};
    let currentSearchKey = Object.keys(allSearches)[0] || '';
    let currentCategoryFilter = 'all'; // 'all', 'deals', 'private', 'delivery', 'nodefects'
    let currentSortMode = 'deal'; // 'deal', 'cheap', 'expensive', 'date'
    let currentSearchText = '';
    let currentViewMode = 'feed'; // 'feed', 'table', 'fav', 'searches'
    let currentModalItem = null;
    let pendingDeleteKey = null;

    // Load LocalStorage Persistent State
    let favorites = [];
    try {{
      favorites = JSON.parse(localStorage.getItem('avito_radar_favs') || '[]');
      const custom = JSON.parse(localStorage.getItem('avito_radar_custom_searches') || '{{}}');
      Object.assign(allSearches, custom);
      const deleted = JSON.parse(localStorage.getItem('avito_radar_deleted_searches') || '[]');
      for (const delKey of deleted) {{
        delete allSearches[delKey];
      }}
    }} catch (e) {{}}

    // Telegram WebApp Setup
    const tg = window.Telegram?.WebApp;
    if (tg) {{
      tg.ready();
      tg.expand();
      tg.headerColor = '#040404';
      tg.backgroundColor = '#040404';
    }}

    function haptic(type = 'light') {{
      if (tg?.HapticFeedback) {{
        if (type === 'light') tg.HapticFeedback.impactOccurred('light');
        else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
        else if (type === 'heavy') tg.HapticFeedback.impactOccurred('heavy');
        else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
        else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
      }}
    }}

    function showToast(message, type = 'info') {{
      const toast = document.getElementById('toastNotification');
      const msgEl = document.getElementById('toastMessage');
      const iconEl = document.getElementById('toastIcon');
      msgEl.textContent = message;
      if (type === 'success') iconEl.textContent = '✅';
      else if (type === 'error') iconEl.textContent = '❌';
      else iconEl.textContent = '⚡';

      toast.classList.remove('opacity-0', '-translate-y-4');
      toast.classList.add('opacity-100', 'translate-y-0');
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => {{
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', '-translate-y-4');
      }}, 2600);
    }}

    function slugify(text) {{
      const ruToEn = {{
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i',
        'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t',
        'у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'',
        'э':'e','ю':'yu','я':'ya'
      }};
      return text.toLowerCase().split('').map(c => ruToEn[c] || c).join('').replace(/[^a-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '');
    }}

    function escapeHtml(str) {{
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }}

    // Preset Helpers for Add Modal
    function setQueryPreset(query, minP) {{
      haptic('light');
      document.getElementById('newQueryInput').value = query;
      if (minP) document.getElementById('newMinPriceInput').value = minP;
    }}

    function setMinPricePreset(minP) {{
      haptic('light');
      document.getElementById('newMinPriceInput').value = minP > 0 ? minP : '';
    }}

    function toggleCustomCity(val) {{
      const customEl = document.getElementById('customCityContainer');
      if (val === 'custom') {{
        customEl.classList.remove('hidden');
      }} else {{
        customEl.classList.add('hidden');
      }}
    }}

    // Initialize Search Selector
    function initSearchSelector() {{
      const selector = document.getElementById('searchSelector');
      selector.innerHTML = '';
      const keys = Object.keys(allSearches);

      if (keys.length === 0) {{
        currentSearchKey = '';
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Нет активных поисков';
        selector.appendChild(opt);
        return;
      }}

      if (!keys.includes(currentSearchKey)) {{
        currentSearchKey = keys[0];
      }}

      keys.forEach(k => {{
        const opt = document.createElement('option');
        opt.value = k;
        const count = allSearches[k].items?.length || 0;
        opt.textContent = `${{allSearches[k].title || k}} (${{count}} шт.)`;
        if (k === currentSearchKey) opt.selected = true;
        selector.appendChild(opt);
      }});

      updateFavCount();
    }}

    function onSearchChange() {{
      haptic('light');
      currentSearchKey = document.getElementById('searchSelector').value;
      renderActiveView();
    }}

    function setViewMode(mode) {{
      haptic('medium');
      currentViewMode = mode;
      ['feed', 'table', 'fav', 'searches'].forEach(m => {{
        const btn = document.getElementById(`viewMode-${{m}}`);
        if (btn) {{
          if (m === mode) {{
            btn.classList.add('active');
            btn.classList.remove('text-zinc-400');
          }} else {{
            btn.classList.remove('active');
            btn.classList.add('text-zinc-400');
          }}
        }}
      }});

      const searchControls = document.getElementById('searchControlsRow');
      const sortSelector = document.getElementById('sortSelector');
      const filterChips = document.getElementById('filterChipsRow');
      const bentoHero = document.getElementById('bentoHero');

      if (mode === 'searches') {{
        if (searchControls) searchControls.classList.add('hidden');
        if (sortSelector) sortSelector.classList.add('hidden');
        if (filterChips) filterChips.classList.add('hidden');
        if (bentoHero) bentoHero.classList.add('hidden');
      }} else {{
        if (searchControls) searchControls.classList.remove('hidden');
        if (sortSelector) sortSelector.classList.remove('hidden');
        if (filterChips) filterChips.classList.remove('hidden');
        if (bentoHero) bentoHero.classList.remove('hidden');
      }}

      renderActiveView();
    }}

    function setFilterCategory(cat) {{
      haptic('light');
      currentCategoryFilter = cat;
      ['all', 'deals', 'private', 'delivery', 'nodefects'].forEach(c => {{
        const chip = document.getElementById(`chip-${{c}}`);
        if (chip) {{
          if (c === cat) chip.classList.add('active');
          else chip.classList.remove('active');
        }}
      }});
      renderActiveView();
    }}

    function onSortChange() {{
      haptic('light');
      currentSortMode = document.getElementById('sortSelector').value;
      renderActiveView();
    }}

    function applyFilters() {{
      const val = document.getElementById('filterKeyword').value.trim().toLowerCase();
      currentSearchText = val;
      const btnClear = document.getElementById('btnClearKeyword');
      if (val) btnClear.classList.remove('hidden');
      else btnClear.classList.add('hidden');
      renderActiveView();
    }}

    function clearKeyword() {{
      haptic('light');
      document.getElementById('filterKeyword').value = '';
      applyFilters();
    }}

    function resetFilters() {{
      haptic('light');
      currentCategoryFilter = 'all';
      currentSearchText = '';
      document.getElementById('filterKeyword').value = '';
      document.getElementById('btnClearKeyword').classList.add('hidden');
      setFilterCategory('all');
      renderActiveView();
    }}

    // Filter, Sort and Query Core Logic
    function getProcessedItems() {{
      const searchObj = allSearches[currentSearchKey];
      let items = [];

      if (currentViewMode === 'fav') {{
        const allItemsMap = new Map();
        Object.values(allSearches).forEach(s => {{
          (s.items || []).forEach(it => allItemsMap.set(String(it.id), it));
        }});
        items = favorites.map(id => allItemsMap.get(String(id))).filter(Boolean);
      }} else {{
        if (!searchObj || !searchObj.items) return [];
        items = [...searchObj.items];
      }}

      // Update counters
      const dealsCount = items.filter(it => it.market_diff_percent && it.market_diff_percent <= -12 && !it.is_combo_listing).length;
      const countAll = document.getElementById('count-all');
      const countDeals = document.getElementById('count-deals');
      if (countAll) countAll.textContent = items.length;
      if (countDeals) countDeals.textContent = dealsCount;

      // Filter: Category
      if (currentCategoryFilter === 'deals') {{
        items = items.filter(it => it.market_diff_percent && it.market_diff_percent <= -12 && !it.is_combo_listing);
      }} else if (currentCategoryFilter === 'private') {{
        items = items.filter(it => it.tags.some(t => t.includes('Частный')));
      }} else if (currentCategoryFilter === 'delivery') {{
        items = items.filter(it => it.badges.some(b => b.toLowerCase().includes('доставка')));
      }} else if (currentCategoryFilter === 'nodefects') {{
        items = items.filter(it => !it.tags.some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное')));
      }}

      // Filter: Keyword
      if (currentSearchText) {{
        items = items.filter(it => {{
          const hay = `${{it.title}} ${{it.description}} ${{it.seller_name}} ${{it.address}}`.toLowerCase();
          return hay.includes(currentSearchText);
        }});
      }}

      // Sort
      items.sort((a, b) => {{
        if (currentSortMode === 'deal') {{
          const diffA = a.market_diff_percent ?? 999;
          const diffB = b.market_diff_percent ?? 999;
          return diffA - diffB;
        }} else if (currentSortMode === 'cheap') {{
          return (a.price || 9999999) - (b.price || 9999999);
        }} else if (currentSortMode === 'expensive') {{
          return (b.price || 0) - (a.price || 0);
        }}
        return 0; // default order
      }});

      return items;
    }}

    // Main render dispatcher
    function renderActiveView() {{
      const feedContainer = document.getElementById('feedContainer');
      const tableContainer = document.getElementById('tableContainer');
      const searchesContainer = document.getElementById('searchesContainer');
      const emptyState = document.getElementById('emptyState');

      if (currentViewMode === 'searches') {{
        feedContainer.classList.add('hidden');
        tableContainer.classList.add('hidden');
        emptyState.classList.add('hidden');
        searchesContainer.classList.remove('hidden');
        renderSearchesManager();
        return;
      }}

      searchesContainer.classList.add('hidden');

      const items = getProcessedItems();
      const searchObj = allSearches[currentSearchKey];

      // Update Bento Hero Tiles
      const median = searchObj?.items?.find(it => it.market_price)?.market_price;
      const heroMarketPrice = document.getElementById('heroMarketPrice');
      if (heroMarketPrice) heroMarketPrice.textContent = median ? `${{median.toLocaleString('ru-RU')}} ₽` : '—';

      const topDeal = items.find(it => it.market_diff_percent && it.market_diff_percent < 0 && !it.is_combo_listing);
      const heroDealsCount = document.getElementById('heroDealsCount');
      if (heroDealsCount) heroDealsCount.textContent = items.filter(it => it.market_diff_percent && it.market_diff_percent <= -12 && !it.is_combo_listing).length;
      const heroTopDiscount = document.getElementById('heroTopDiscount');
      if (heroTopDiscount) heroTopDiscount.textContent = topDeal ? `${{topDeal.market_diff_percent}}%` : '0%';

      if (items.length === 0) {{
        feedContainer.innerHTML = '';
        document.getElementById('tableBody').innerHTML = '';
        feedContainer.classList.add('hidden');
        tableContainer.classList.add('hidden');
        emptyState.classList.remove('hidden');
        emptyState.classList.add('flex');
        return;
      }}

      emptyState.classList.add('hidden');
      emptyState.classList.remove('flex');

      if (currentViewMode === 'table') {{
        feedContainer.classList.add('hidden');
        tableContainer.classList.remove('hidden');
        renderTableView(items);
      }} else {{
        tableContainer.classList.add('hidden');
        feedContainer.classList.remove('hidden');
        renderFeedView(items);
      }}
    }}

    // Render Cards View
    function renderFeedView(items) {{
      const container = document.getElementById('feedContainer');
      container.innerHTML = '';
      items.forEach(item => {{
        container.appendChild(createBentoCard(item));
      }});
    }}

    // Render Table View
    function renderTableView(items) {{
      const tbody = document.getElementById('tableBody');
      tbody.innerHTML = '';
      items.forEach((item) => {{
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-zinc-900/60 active:bg-zinc-800/80 cursor-pointer transition-colors';
        tr.onclick = () => openModal(item);

        const isDeal = item.market_diff_percent && item.market_diff_percent <= -12 && !item.is_combo_listing;
        const diffText = item.market_diff_percent ? `${{item.market_diff_percent}}%` : '—';
        const priceText = item.price ? `${{item.price.toLocaleString('ru-RU')}} ₽` : '—';
        const marketText = item.market_price ? `${{item.market_price.toLocaleString('ru-RU')}} ₽` : '—';

        tr.innerHTML = `
          <td class="py-2.5 px-3">
            <div class="font-bold text-white truncate max-w-[130px]">${{escapeHtml(item.title)}}</div>
            <div class="text-[10px] text-zinc-500">${{escapeHtml(item.published_text || 'сегодня')}}</div>
          </td>
          <td class="py-2.5 px-3 font-bold ${{isDeal ? 'text-neon' : 'text-zinc-200'}} whitespace-nowrap">${{priceText}}</td>
          <td class="py-2.5 px-3 text-zinc-400 whitespace-nowrap">${{marketText}}</td>
          <td class="py-2.5 px-3">
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${{isDeal ? 'bg-neon/15 text-neon' : 'bg-zinc-800 text-zinc-400'}}">${{diffText}}</span>
          </td>
          <td class="py-2.5 px-3 text-zinc-400 truncate max-w-[90px]">${{escapeHtml(item.seller_name || 'Частник')}}</td>
          <td class="py-2.5 px-3 whitespace-nowrap text-right">
            <button onclick="event.stopPropagation(); openAvitoLinkDirect('${{item.url}}')" class="px-2 py-1 bg-zinc-800 hover:bg-neon hover:text-black rounded text-[10px] font-bold transition-all">↗</button>
          </td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    // Card Component
    function createBentoCard(item) {{
      const card = document.createElement('article');
      const isTopDeal = item.market_diff_percent && item.market_diff_percent <= -15 && !item.is_combo_listing;
      const isCombo = item.is_combo_listing;
      const isFav = favorites.includes(item.id);

      card.className = `bento-card rounded-2xl overflow-hidden flex flex-col cursor-pointer ${{
        isTopDeal ? 'glow-neon-card' : isCombo ? 'glow-amber-card' : ''
      }}`;

      const photoUrl = (item.images && item.images.length > 0) ? item.images[0] : '';
      const photoHtml = photoUrl ? `
        <div class="relative w-full aspect-[16/10] bg-zinc-950 overflow-hidden">
          <img src="${{photoUrl}}" alt="${{escapeHtml(item.title)}}" loading="lazy" class="w-full h-full object-cover">
          ${{isTopDeal ? `
            <div class="absolute top-2.5 left-2.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-neon text-black font-mono shadow-lg flex items-center space-x-1">
              <span>🔥</span>
              <span>${{item.market_diff_percent}}% ВЫГОДА</span>
            </div>
          ` : ''}}
          ${{isCombo ? `
            <div class="absolute top-2.5 left-2.5 px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-neon text-black font-mono shadow-lg">
              ⚠️ СБОРНЫЙ ЛОТ
            </div>
          ` : ''}}
          <button onclick="event.stopPropagation(); toggleFavorite(${{item.id}})" class="absolute top-2.5 right-2.5 w-7 h-7 rounded-full bg-black/65 backdrop-blur-md border border-white/20 flex items-center justify-center text-xs ${{isFav ? 'text-amber-neon' : 'text-zinc-400'}}">
            ★
          </button>
          <div class="absolute bottom-2 right-2 px-2 py-0.5 rounded-md text-[10px] font-mono bg-black/75 backdrop-blur-md text-zinc-300">
            ${{escapeHtml(item.published_text || 'сегодня')}}
          </div>
        </div>
      ` : '';

      const priceFmt = item.price ? `${{item.price.toLocaleString('ru-RU')}} ₽` : 'Цена не указана';
      let marketDiffHtml = '';
      if (item.market_price && !isCombo) {{
        const diffRur = item.price - item.market_price;
        if (diffRur < 0) {{
          marketDiffHtml = `<span class="text-[11px] text-neon font-mono font-bold">Рынок: ${{item.market_price.toLocaleString('ru-RU')}} ₽ (выгода ${{Math.abs(diffRur).toLocaleString('ru-RU')}} ₽)</span>`;
        }} else {{
          marketDiffHtml = `<span class="text-[11px] text-zinc-500 font-mono">Рынок: ${{item.market_price.toLocaleString('ru-RU')}} ₽</span>`;
        }}
      }}

      let comboBanner = '';
      if (isCombo) {{
        const realP = item.real_price_in_desc ? `${{item.real_price_in_desc.toLocaleString('ru-RU')}} ₽` : 'см. описание';
        comboBanner = `
          <div class="mt-2 p-2 rounded-xl bg-amber-neon/10 border border-amber-neon/30 text-[11px] text-amber-neon font-mono flex items-center justify-between">
            <span>⚠️ В описании целевой товар: <b>${{realP}}</b></span>
          </div>
        `;
      }}

      const tagsHtml = (item.tags || []).slice(0, 3).map(t => {{
        let colorClass = 'bg-zinc-900 text-zinc-400 border-zinc-800';
        if (t.includes('Выгодно') || t.includes('Супер-цена')) colorClass = 'bg-neon/10 text-neon border-neon/30';
        else if (t.includes('Частный')) colorClass = 'bg-zinc-800 text-zinc-200 border-zinc-700';
        else if (t.includes('Сборное') || t.includes('Реальная цена')) colorClass = 'bg-amber-neon/10 text-amber-neon border-amber-neon/30';
        else if (t.includes('Дефект') || t.includes('Запчасти')) colorClass = 'bg-crimson-neon/10 text-crimson-neon border-crimson-neon/30';
        return `<span class="text-[10px] font-mono px-2 py-0.5 rounded border ${{colorClass}}">${{escapeHtml(t)}}</span>`;
      }}).join('');

      card.innerHTML = `
        ${{photoHtml}}
        <div class="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
          <div class="space-y-1">
            <div class="flex items-baseline justify-between">
              <span class="text-lg font-black font-mono ${{isTopDeal ? 'text-neon' : 'text-white'}}">${{priceFmt}}</span>
              ${{item.seller_rating ? `<span class="text-[11px] text-amber-neon font-bold font-mono">★ ${{item.seller_rating}}</span>` : ''}}
            </div>
            ${{marketDiffHtml}}
            <h3 class="text-xs font-semibold text-zinc-200 line-clamp-2 leading-snug pt-0.5">${{escapeHtml(item.title)}}</h3>
            ${{comboBanner}}
          </div>

          <div class="space-y-2 pt-2">
            <div class="flex flex-wrap gap-1">${{tagsHtml}}</div>
            <div class="flex items-center justify-between text-[11px] text-zinc-500 font-mono border-t border-zinc-850 pt-2">
              <span class="truncate max-w-[160px]">📍 ${{escapeHtml(item.address || item.city)}}</span>
              <button class="text-neon font-bold text-xs flex items-center gap-1 active:scale-95">
                Терминал →
              </button>
            </div>
          </div>
        </div>
      `;

      card.onclick = () => openModal(item);
      return card;
    }}

    // Searches Manager UI Rendering
    function renderSearchesManager() {{
      const container = document.getElementById('searchesList');
      container.innerHTML = '';
      const keys = Object.keys(allSearches);
      
      const badge = document.getElementById('searchesCountBadge');
      if (badge) badge.textContent = `${{keys.length}} ${{keys.length === 1 ? 'радар' : keys.length < 5 ? 'радара' : 'радаров'}}`;

      if (keys.length === 0) {{
        container.innerHTML = `
          <div class="bento-card rounded-2xl p-8 text-center space-y-3 border-dark-border">
            <div class="text-3xl">🎯</div>
            <div class="text-sm font-bold text-white font-mono">Нет активных радаров</div>
            <p class="text-xs text-zinc-500 font-mono">Создайте новый поиск, чтобы бот начал отслеживать рынок.</p>
            <button onclick="openNewSearchModal()" class="text-xs bg-neon text-black font-extrabold px-4 py-2.5 rounded-xl font-mono active:scale-95">
              + Создать первый поиск
            </button>
          </div>
        `;
        return;
      }}

      keys.forEach(key => {{
        const s = allSearches[key];
        const isActive = key === currentSearchKey;
        const itemsCount = (s.items || []).length;
        const minPriceText = s.min_price ? `от ${{s.min_price.toLocaleString('ru-RU')}} ₽` : 'без порога цены';
        const cityText = s.city || 'Вся Россия';

        const card = document.createElement('div');
        card.className = `bento-card rounded-2xl p-4 border transition-all ${{isActive ? 'glow-neon-card border-neon/50' : 'border-dark-border'}}`;
        card.innerHTML = `
          <div class="flex items-start justify-between gap-2">
            <div class="space-y-1.5 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <h3 class="text-sm font-extrabold text-white leading-snug font-mono">${{escapeHtml(s.title || key)}}</h3>
                ${{isActive ? '<span class="text-[9px] font-black font-mono uppercase px-2 py-0.5 rounded-full bg-neon text-black">АКТИВНЫЙ</span>' : ''}}
              </div>
              <div class="flex items-center gap-1.5 flex-wrap text-[11px] text-zinc-400 font-mono pt-0.5">
                <span class="px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">📍 ${{escapeHtml(cityText)}}</span>
                <span class="px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">📦 ${{itemsCount}} лотов</span>
                <span class="px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">💰 ${{minPriceText}}</span>
                <span class="px-2 py-0.5 rounded-lg bg-neon/10 border border-neon/30 text-neon font-bold">⚡ 24/7</span>
              </div>
            </div>
          </div>

          <div class="border-t border-zinc-850 mt-3 pt-3 flex items-center justify-between gap-2">
            <button onclick="selectAndOpenSearch('${{key}}')" class="flex-1 py-2.5 px-3 rounded-xl ${{isActive ? 'bg-zinc-800 text-zinc-200' : 'bg-neon/15 text-neon border border-neon/30'}} text-xs font-bold font-mono active:scale-95 transition-all text-center">
              ${{isActive ? '👀 Открыть лоты' : '⚡ Выбрать этот радар'}}
            </button>
            <button onclick="scanSearch('${{key}}')" id="btnScan_${{key}}" title="Обновить каталог с Авито" class="py-2.5 px-3 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white text-xs font-mono active:scale-95 transition-all flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
              <span>Скан</span>
            </button>
            <button onclick="promptDeleteSearch('${{key}}', '${{escapeHtml(s.title || key)}}', ${{itemsCount}})" class="py-2.5 px-3 rounded-xl bg-crimson-neon/10 border border-crimson-neon/30 text-crimson-neon text-xs font-mono font-bold active:scale-95 transition-all flex items-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
              <span>Удалить</span>
            </button>
          </div>
        `;
        container.appendChild(card);
      }});
    }}

    function selectAndOpenSearch(key) {{
      haptic('medium');
      currentSearchKey = key;
      initSearchSelector();
      setViewMode('feed');
      showToast(`Радар «${{allSearches[key]?.title || key}}» активирован`, 'info');
    }}

    // Search Scanning Trigger
    async function scanSearch(key) {{
      haptic('medium');
      const btn = document.getElementById(`btnScan_${{key}}`);
      if (btn) btn.classList.add('animate-pulse');
      showToast('Сканирование Авито...', 'info');

      try {{
        const res = await fetch('/api/searches/scan', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ name: key }})
        }});
        if (res.ok) {{
          const data = await res.json();
          if (data.bundle) {{
            allSearches = data.bundle;
            initSearchSelector();
            renderSearchesManager();
            showToast('✅ Каталог обновлен!', 'success');
            haptic('success');
            return;
          }}
        }}
      }} catch (err) {{
        console.log('Scan call offline/failed:', err);
      }} finally {{
        if (btn) btn.classList.remove('animate-pulse');
      }}
      showToast('Сканирование завершено', 'info');
    }}

    // Search Deletion
    function promptDeleteSearch(key, title, count) {{
      haptic('medium');
      pendingDeleteKey = key;
      document.getElementById('deleteModalTitle').textContent = title;
      document.getElementById('deleteModalCount').textContent = count;
      document.getElementById('modalBackdrop').classList.add('open');
      document.getElementById('deleteConfirmModal').classList.add('open');
    }}

    async function confirmDeleteSearch() {{
      if (!pendingDeleteKey) return;
      haptic('heavy');
      const key = pendingDeleteKey;
      closeAllModals();

      showToast('Удаление поиска...', 'info');

      try {{
        await fetch('/api/searches/delete', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ name: key }})
        }});
      }} catch (err) {{
        console.log('Backend delete call offline/failed:', err);
      }}

      // Persistent local deletion
      const deleted = JSON.parse(localStorage.getItem('avito_radar_deleted_searches') || '[]');
      if (!deleted.includes(key)) {{
        deleted.push(key);
        localStorage.setItem('avito_radar_deleted_searches', JSON.stringify(deleted));
      }}
      const custom = JSON.parse(localStorage.getItem('avito_radar_custom_searches') || '{{}}');
      delete custom[key];
      localStorage.setItem('avito_radar_custom_searches', JSON.stringify(custom));

      delete allSearches[key];

      if (currentSearchKey === key) {{
        const remKeys = Object.keys(allSearches);
        currentSearchKey = remKeys.length > 0 ? remKeys[0] : '';
      }}

      initSearchSelector();
      renderSearchesManager();
      showToast('🗑 Поиск успешно удален', 'success');
    }}

    // New Search Submit
    async function submitNewSearch() {{
      const q = document.getElementById('newQueryInput').value.trim();
      const citySelect = document.getElementById('newCitySelect').value;
      const customCityInput = document.getElementById('newCustomCityInput');
      const city = (citySelect === 'custom' && customCityInput) ? customCityInput.value.trim() : citySelect;
      const minP = document.getElementById('newMinPriceInput').value.trim();

      if (!q) {{
        showToast('Введите название товара!', 'error');
        haptic('error');
        return;
      }}

      haptic('medium');
      const btn = document.getElementById('btnSubmitNewSearch');
      btn.disabled = true;
      btn.innerHTML = '<span>Сканирование каталога Авито...</span>';

      try {{
        const res = await fetch('/api/searches', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ query: q, city: city, min_price: minP ? parseInt(minP) : 0 }})
        }});
        if (res.ok) {{
          const data = await res.json();
          await refreshData();
          if (data.name && allSearches[data.name]) {{
            currentSearchKey = data.name;
          }}
          closeAllModals();
          setViewMode('feed');
          showToast(`🎯 Радар для «${{q}}» запущен!`, 'success');
          haptic('success');
          return;
        }}
      }} catch (err) {{
        console.log('Backend create failed/offline, creating locally:', err);
      }} finally {{
        btn.disabled = false;
        btn.innerHTML = '<span>🚀 ЗАПУСТИТЬ РАДАР</span>';
      }}

      // Fallback if backend offline
      const key = `${{slugify(q)}}_${{city}}`;
      const newRecord = {{
        name: key,
        title: q,
        city: city,
        min_price: minP ? parseInt(minP) : null,
        category_type: 'goods',
        items: []
      }};
      allSearches[key] = newRecord;
      const custom = JSON.parse(localStorage.getItem('avito_radar_custom_searches') || '{{}}');
      custom[key] = newRecord;
      localStorage.setItem('avito_radar_custom_searches', JSON.stringify(custom));

      currentSearchKey = key;
      closeAllModals();
      initSearchSelector();
      setViewMode('feed');
      showToast(`🎯 Радар для «${{q}}» запущен!`, 'success');
      haptic('success');
    }}

    // Item Details Modal
    function openModal(item) {{
      haptic('medium');
      currentModalItem = item;

      document.getElementById('modalTitle').textContent = item.title;
      document.getElementById('modalPrice').textContent = item.price ? `${{item.price.toLocaleString('ru-RU')}} ₽` : 'Цена не указана';
      document.getElementById('modalMarketPrice').textContent = item.market_price ? `Оценка рынка: ${{item.market_price.toLocaleString('ru-RU')}} ₽` : '';
      document.getElementById('modalDescription').textContent = item.description || 'Описание отсутствует.';
      document.getElementById('modalSellerName').textContent = item.seller_name || 'Частный продавец';
      document.getElementById('modalSellerType').textContent = item.seller_type || 'Частное лицо';
      document.getElementById('modalLocation').textContent = `📍 ${{item.address || item.city || 'Челябинск'}}`;
      document.getElementById('modalDate').textContent = `⏱ ${{item.published_text || 'сегодня'}}`;

      if (item.seller_rating) {{
        document.getElementById('modalSellerRating').textContent = `★ ${{item.seller_rating}} (${{item.closed_listings || 0}} сделок)`;
        document.getElementById('modalSellerRating').style.display = 'block';
      }} else {{
        document.getElementById('modalSellerRating').style.display = 'none';
      }}

      const img = document.getElementById('modalMainImg');
      if (item.images && item.images.length > 0) {{
        img.src = item.images[0];
        img.style.display = 'block';
      }} else {{
        img.style.display = 'none';
      }}

      const dealBadge = document.getElementById('modalDealBadge');
      if (item.market_diff_percent && item.market_diff_percent <= -12 && !item.is_combo_listing) {{
        dealBadge.textContent = `🔥 ${{item.market_diff_percent}}% НИЖЕ РЫНКА`;
        dealBadge.style.display = 'block';
      }} else {{
        dealBadge.style.display = 'none';
      }}

      const comboWarn = document.getElementById('modalComboWarning');
      const comboText = document.getElementById('modalComboWarningText');
      if (item.is_combo_listing) {{
        const realP = item.real_price_in_desc ? `${{item.real_price_in_desc.toLocaleString('ru-RU')}} ₽` : 'указана в тексте';
        comboText.innerHTML = `В шапке объявления указана заниженная цена (<b>${{item.price?.toLocaleString('ru-RU')}} ₽</b>). В описании целевая модель продаётся от <b>${{realP}}</b>!`;
        comboWarn.classList.remove('hidden');
      }} else {{
        comboWarn.classList.add('hidden');
      }}

      const tagsContainer = document.getElementById('modalTags');
      tagsContainer.innerHTML = (item.tags || []).map(t => `<span class="text-xs font-mono font-medium px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">${{escapeHtml(t)}}</span>`).join('');

      document.getElementById('modalAvitoLink').href = item.url;
      updateModalFavBtn();

      document.getElementById('modalBackdrop').classList.add('open');
      document.getElementById('bottomSheet').classList.add('open');
    }}

    function closeAllModals() {{
      haptic('light');
      document.getElementById('modalBackdrop').classList.remove('open');
      document.getElementById('bottomSheet').classList.remove('open');
      document.getElementById('newSearchModal').classList.remove('open');
      document.getElementById('deleteConfirmModal').classList.remove('open');
    }}

    function openNewSearchModal() {{
      haptic('medium');
      document.getElementById('modalBackdrop').classList.add('open');
      document.getElementById('newSearchModal').classList.add('open');
    }}

    function openAvitoLink(event) {{
      haptic('success');
      if (currentModalItem && tg?.openLink) {{
        event.preventDefault();
        tg.openLink(currentModalItem.url);
      }}
    }}

    function openAvitoLinkDirect(url) {{
      haptic('success');
      if (tg?.openLink) {{
        tg.openLink(url);
      }} else {{
        window.open(url, '_blank');
      }}
    }}

    // Favorites Logic
    function toggleFavorite(itemId) {{
      haptic('light');
      const idx = favorites.indexOf(itemId);
      if (idx > -1) {{
        favorites.splice(idx, 1);
      }} else {{
        favorites.push(itemId);
      }}
      localStorage.setItem('avito_radar_favs', JSON.stringify(favorites));
      updateFavCount();
      renderActiveView();
    }}

    function toggleModalFav() {{
      if (!currentModalItem) return;
      toggleFavorite(currentModalItem.id);
      updateModalFavBtn();
    }}

    function updateModalFavBtn() {{
      const btn = document.getElementById('modalFavBtn');
      if (!currentModalItem) return;
      const isFav = favorites.includes(currentModalItem.id);
      btn.className = `absolute top-3 right-3 w-8 h-8 rounded-full bg-black/70 backdrop-blur-md border border-white/20 flex items-center justify-center text-sm ${{isFav ? 'text-amber-neon' : 'text-zinc-400'}}`;
    }}

    function updateFavCount() {{
      const favEl = document.getElementById('favCount');
      if (favEl) favEl.textContent = favorites.length;
    }}

    // Backend Synchronization
    async function refreshData() {{
      haptic('medium');
      const btn = document.getElementById('btnRefresh');
      btn.classList.add('animate-spin');
      const sub = document.getElementById('monitoringSub');
      if (sub) sub.textContent = 'Синхронизация данных...';

      try {{
        const resp = await fetch('/api/bundle');
        if (resp.ok) {{
          const freshData = await resp.json();
          if (freshData && Object.keys(freshData).length > 0) {{
            allSearches = freshData;
            initSearchSelector();
            renderActiveView();
            showToast('Данные синхронизированы', 'success');
            haptic('success');
          }}
        }}
      }} catch (err) {{
        console.log('Backend sync offline:', err);
      }} finally {{
        btn.classList.remove('animate-spin');
        if (sub) sub.textContent = '24/7 Monitoring Active';
      }}
    }}

    // Initialize application
    initSearchSelector();
    renderActiveView();
  </script>
</body>
</html>
"""
    return html

def main():
    html_content = generate_html()
    web_dir = Path("web")
    web_dir.mkdir(exist_ok=True)
    (web_dir / "index.html").write_text(html_content, encoding="utf-8")
    Path("index.html").write_text(html_content, encoding="utf-8")
    print(f"Mini App built successfully! Size: {len(html_content)} bytes")

if __name__ == "__main__":
    main()
