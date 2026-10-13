import { ApiService } from './api.js';
import { TelegramService } from './telegram.js';

// Application State
const State = {
  searches: [],
  currentSearchId: 'all',
  lots: [],
  activeFilter: 'all', // 'all', 'deals', 'private', 'delivery', 'nodefects', 'dismissed'
  searchQuery: '',
  sortMode: 'deal', // 'deal', 'cheap', 'expensive', 'date'
  viewMode: 'cards', // 'cards', 'table', 'fav', 'searches'
  favorites: [],
  modalLot: null
};

// Initialize favorites
try {
  State.favorites = JSON.parse(localStorage.getItem('avitoradar_favorites') || '[]');
} catch (_) {}

// UI Selectors
const DOM = {
  searchSelector: document.getElementById('searchSelector'),
  filterInput: document.getElementById('filterInput'),
  btnClearFilter: document.getElementById('btnClearFilter'),
  filterChipsRow: document.getElementById('filterChipsRow'),
  sortSelector: document.getElementById('sortSelector'),
  statsGrid: document.getElementById('statsGrid'),
  lotsContainer: document.getElementById('lotsContainer'),
  tableWrapper: document.getElementById('tableWrapper'),
  tableBody: document.getElementById('tableBody'),
  searchesSection: document.getElementById('searchesSection'),
  searchesList: document.getElementById('searchesList'),
  emptyState: document.getElementById('emptyState'),
  modalOverlay: document.getElementById('modalOverlay'),
  bottomSheet: document.getElementById('bottomSheet'),
  newSearchModal: document.getElementById('newSearchModal'),
  deleteModal: document.getElementById('deleteModal'),
  toastContainer: document.getElementById('toastContainer'),
  btnRefresh: document.getElementById('btnRefresh'),
  statMedianPrice: document.getElementById('statMedianPrice'),
  statDealsCount: document.getElementById('statDealsCount'),
  statTopDiscount: document.getElementById('statTopDiscount'),
  statActiveRadars: document.getElementById('statActiveRadars')
};

// ==========================================================================
// Initialization
// ==========================================================================
document.addEventListener('DOMContentLoaded', async () => {
  TelegramService.init();
  setupEventListeners();
  await loadData();
});

function setupEventListeners() {
  // Search selector change
  DOM.searchSelector?.addEventListener('change', (e) => {
    TelegramService.haptic('light');
    State.currentSearchId = e.target.value;
    renderView();
  });

  // Keyword input
  DOM.filterInput?.addEventListener('input', (e) => {
    State.searchQuery = e.target.value.trim().toLowerCase();
    if (State.searchQuery) DOM.btnClearFilter?.classList.remove('hidden');
    else DOM.btnClearFilter?.classList.add('hidden');
    renderView();
  });

  DOM.btnClearFilter?.addEventListener('click', () => {
    TelegramService.haptic('light');
    DOM.filterInput.value = '';
    State.searchQuery = '';
    DOM.btnClearFilter.classList.add('hidden');
    renderView();
  });

  // Sort selector
  DOM.sortSelector?.addEventListener('change', (e) => {
    TelegramService.haptic('light');
    State.sortMode = e.target.value;
    renderView();
  });

  // Refresh button
  DOM.btnRefresh?.addEventListener('click', async () => {
    TelegramService.haptic('medium');
    DOM.btnRefresh.classList.add('animate-spin');
    await loadData();
    DOM.btnRefresh.classList.remove('animate-spin');
    showToast('Данные синхронизированы', 'success');
  });

  // Modal Backdrop Close
  DOM.modalOverlay?.addEventListener('click', closeAllModals);

  // Forms
  document.getElementById('formNewSearch')?.addEventListener('submit', handleNewSearchSubmit);
  document.getElementById('btnConfirmDelete')?.addEventListener('click', handleConfirmDelete);
}

// ==========================================================================
// Data Fetching & Sync
// ==========================================================================
async function loadData() {
  State.searches = await ApiService.getSearches();
  State.lots = await ApiService.getLots({ includeDismissed: true });

  populateSearchSelector();
  renderView();
}

function populateSearchSelector() {
  if (!DOM.searchSelector) return;
  DOM.searchSelector.innerHTML = '<option value="all">🔍 Все радары (общий поток)</option>';

  State.searches.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id;
    const count = State.lots.filter(l => l.searchId === s.id && !l.isDismissed).length;
    opt.textContent = `${s.query} (${count} шт.)`;
    if (s.id === State.currentSearchId) opt.selected = true;
    DOM.searchSelector.appendChild(opt);
  });
}

// ==========================================================================
// Filtering & Calculation
// ==========================================================================
function getVisibleLots() {
  let lots = [...State.lots];

  // Search filter
  if (State.currentSearchId && State.currentSearchId !== 'all') {
    lots = lots.filter(l => l.searchId === State.currentSearchId);
  }

  // Dismissed filter
  if (State.activeFilter === 'dismissed') {
    lots = lots.filter(l => l.isDismissed);
  } else {
    lots = lots.filter(l => !l.isDismissed);
  }

  // Favorites mode
  if (State.viewMode === 'fav') {
    lots = lots.filter(l => State.favorites.includes(String(l.id)));
  }

  // Chip filters
  if (State.activeFilter === 'deals') {
    lots = lots.filter(l => l.discount <= -12 && !l.isComboListing);
  } else if (State.activeFilter === 'private') {
    lots = lots.filter(l => l.seller.type === 'private');
  } else if (State.activeFilter === 'delivery') {
    lots = lots.filter(l => (l.badges || []).some(b => b.toLowerCase().includes('доставка')));
  } else if (State.activeFilter === 'nodefects') {
    lots = lots.filter(l => !(l.tags || []).some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное')));
  }

  // Keyword query
  if (State.searchQuery) {
    lots = lots.filter(l => {
      const text = `${l.title} ${l.description} ${l.seller.name} ${l.seller.location}`.toLowerCase();
      return text.includes(State.searchQuery);
    });
  }

  // Sort
  if (State.sortMode === 'cheap') {
    lots.sort((a, b) => a.price - b.price);
  } else if (State.sortMode === 'expensive') {
    lots.sort((a, b) => b.price - a.price);
  } else if (State.sortMode === 'date') {
    lots.sort((a, b) => b.postedAt - a.postedAt);
  } else {
    // 'deal' (discount)
    lots.sort((a, b) => (a.discount || 999) - (b.discount || 999));
  }

  return lots;
}

// ==========================================================================
// Rendering Dispatcher
// ==========================================================================
function renderView() {
  updateStats();

  if (State.viewMode === 'searches') {
    DOM.lotsContainer?.classList.add('hidden');
    DOM.tableWrapper?.classList.add('hidden');
    DOM.emptyState?.classList.add('hidden');
    DOM.searchesSection?.classList.remove('hidden');
    renderSearchesManager();
    return;
  }

  DOM.searchesSection?.classList.add('hidden');

  const visible = getVisibleLots();

  if (visible.length === 0) {
    DOM.lotsContainer?.classList.add('hidden');
    DOM.tableWrapper?.classList.add('hidden');
    DOM.emptyState?.classList.remove('hidden');
    return;
  }

  DOM.emptyState?.classList.add('hidden');

  if (State.viewMode === 'table') {
    DOM.lotsContainer?.classList.add('hidden');
    DOM.tableWrapper?.classList.remove('hidden');
    renderTableView(visible);
  } else {
    DOM.tableWrapper?.classList.add('hidden');
    DOM.lotsContainer?.classList.remove('hidden');
    renderCardsView(visible);
  }
}

function updateStats() {
  const activeLots = State.lots.filter(l => !l.isDismissed);
  const currentScoped = State.currentSearchId === 'all'
    ? activeLots
    : activeLots.filter(l => l.searchId === State.currentSearchId);

  // Clean median
  const medianPrice = currentScoped.find(l => l.marketPrice)?.marketPrice || 0;
  if (DOM.statMedianPrice) {
    DOM.statMedianPrice.textContent = medianPrice > 0 ? `${medianPrice.toLocaleString('ru-RU')} ₽` : '—';
  }

  // Deals count
  const dealsCount = currentScoped.filter(l => l.discount <= -12 && !l.isComboListing).length;
  if (DOM.statDealsCount) {
    DOM.statDealsCount.textContent = dealsCount;
  }

  // Top discount
  const topDeal = currentScoped.find(l => l.discount < 0 && !l.isComboListing);
  if (DOM.statTopDiscount) {
    DOM.statTopDiscount.textContent = topDeal ? `${topDeal.discount}%` : '0%';
  }

  // Active radars count
  if (DOM.statActiveRadars) {
    DOM.statActiveRadars.textContent = State.searches.length;
  }

  // Fav & Dismissed count badges
  const favCount = document.getElementById('favCount');
  if (favCount) favCount.textContent = State.favorites.length;

  const dismissedCount = document.getElementById('dismissedCount');
  const totalDismissed = State.lots.filter(l => l.isDismissed).length;
  if (dismissedCount) dismissedCount.textContent = totalDismissed;
}

// ==========================================================================
// Lot Cards & Vanish Logic
// ==========================================================================
function renderCardsView(lots) {
  if (!DOM.lotsContainer) return;
  DOM.lotsContainer.innerHTML = '';

  lots.forEach(lot => {
    DOM.lotsContainer.appendChild(createLotCard(lot));
  });
}

function createLotCard(lot) {
  const card = document.createElement('article');
  card.className = 'lot-card';
  card.dataset.id = lot.id;

  const isDeal = lot.discount <= -12 && !lot.isComboListing;
  const isFav = State.favorites.includes(String(lot.id));

  // Image preview
  const photoUrl = (lot.images && lot.images.length > 0) ? lot.images[0] : '';
  const mediaHtml = photoUrl ? `
    <div class="card-media-preview">
      <img src="${photoUrl}" alt="${escapeHtml(lot.title)}" loading="lazy" class="card-media-img">
      <button class="card-fav-btn ${isFav ? 'active' : ''}" onclick="window.app.toggleFav(event, '${lot.id}')" title="В избранное">★</button>
    </div>
  ` : '';

  // Deal badge or Combo alert
  let badgeHtml = '';
  if (isDeal) {
    badgeHtml = `<div class="deal-badge">🔥 ВЫГОДА ${lot.discount}%</div>`;
  } else if (lot.isComboListing) {
    badgeHtml = `<div class="deal-badge" style="background: rgba(245, 158, 11, 0.15); color: #F59E0B; border-color: rgba(245, 158, 11, 0.3)">⚠️ СБОРНЫЙ ЛОТ</div>`;
  } else {
    badgeHtml = `<span class="caption font-mono">${lot.publishedText || 'сегодня'}</span>`;
  }

  // Price formatting
  const priceFormatted = `${lot.price.toLocaleString('ru-RU')} ₽`;
  const marketFormatted = lot.marketPrice ? `${lot.marketPrice.toLocaleString('ru-RU')} ₽` : '';
  const diffSign = lot.discount <= 0 ? '' : '+';

  // Vanish button: X
  const vanishHtml = lot.isDismissed ? `
    <button class="btn-vanish" onclick="window.app.restoreLot(event, '${lot.id}')" title="Вернуть объявление" style="color: var(--success)">
      ↩
    </button>
  ` : `
    <button class="btn-vanish" onclick="window.app.vanishLot(event, '${lot.id}')" title="Скрыть объявление (Vanish)">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>
  `;

  card.innerHTML = `
    <div>
      <div class="card-header-row">
        ${badgeHtml}
        <div style="display: flex; align-items: center; gap: 4px;">
          <span class="caption font-mono">${lot.publishedText || ''}</span>
          ${vanishHtml}
        </div>
      </div>

      ${mediaHtml}

      <h3 class="lot-title">${escapeHtml(lot.title)}</h3>

      ${lot.isComboListing ? `
        <div class="combo-warning-banner">
          <span>⚠️ В описании целевой товар: <b>${lot.realPriceInDesc ? lot.realPriceInDesc.toLocaleString('ru-RU') + ' ₽' : 'см. текст'}</b></span>
        </div>
      ` : ''}

      <div class="price-block">
        <span class="price-main">${priceFormatted}</span>
        ${marketFormatted && !lot.isComboListing ? `<span class="price-market">${marketFormatted}</span>` : ''}
        ${lot.discount && !lot.isComboListing ? `<span class="price-discount">${diffSign}${lot.discount}%</span>` : ''}
      </div>
    </div>

    <div>
      <div class="card-meta-row">
        <span>${lot.seller.type === 'private' ? '👤 Частник' : '🏬 Магазин'} ${lot.seller.rating ? '★ ' + lot.seller.rating : ''}</span>
        <span>📍 ${escapeHtml(lot.seller.location)}</span>
      </div>

      <button class="btn-cta" onclick="window.app.openDetails(event, '${lot.id}')">
        <span>Открыть в терминале</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </button>
    </div>
  `;

  card.addEventListener('click', (e) => {
    // If clicked on button or vanish, skip modal
    if (e.target.closest('button') || e.target.closest('a')) return;
    openLotModal(lot);
  });

  return card;
}

// Vanish Action Implementation
async function vanishLot(event, lotId) {
  event.stopPropagation();
  TelegramService.haptic('medium');

  const card = document.querySelector(`.lot-card[data-id="${lotId}"]`);
  if (card) {
    card.classList.add('vanishing');
  }

  // Send API call in background
  ApiService.dismissLot(lotId);

  // Update in-memory state
  const target = State.lots.find(l => String(l.id) === String(lotId));
  if (target) target.isDismissed = true;

  // After 300ms animation finish, remove from DOM & update stats
  setTimeout(() => {
    if (card) card.remove();
    updateStats();
    showToast('Объявление скрыто (Vanish)', 'info');

    // If no more cards left, re-render
    const visible = getVisibleLots();
    if (visible.length === 0) renderView();
  }, 300);
}

async function restoreLot(event, lotId) {
  event.stopPropagation();
  TelegramService.haptic('success');

  await ApiService.restoreLot(lotId);
  const target = State.lots.find(l => String(l.id) === String(lotId));
  if (target) target.isDismissed = false;

  renderView();
  showToast('Объявление восстановлено', 'success');
}

// ==========================================================================
// Table View
// ==========================================================================
function renderTableView(lots) {
  if (!DOM.tableBody) return;
  DOM.tableBody.innerHTML = '';

  lots.forEach(lot => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';

    const isDeal = lot.discount <= -12 && !lot.isComboListing;
    const diffSign = lot.discount <= 0 ? '' : '+';
    const priceText = `${lot.price.toLocaleString('ru-RU')} ₽`;
    const marketText = lot.marketPrice ? `${lot.marketPrice.toLocaleString('ru-RU')} ₽` : '—';

    tr.innerHTML = `
      <td>
        <div style="font-weight: 600; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(lot.title)}</div>
        <div class="caption">${lot.publishedText || 'сегодня'}</div>
      </td>
      <td style="font-weight: 700; color: ${isDeal ? 'var(--success)' : 'var(--text-primary)'}; white-space: nowrap;">
        ${priceText}
      </td>
      <td style="color: var(--text-secondary); white-space: nowrap;">
        ${marketText}
      </td>
      <td>
        <span class="deal-badge" style="padding: 2px 6px; font-size: 10px; background: ${isDeal ? 'var(--success-bg)' : 'rgba(255,255,255,0.06)'}; color: ${isDeal ? 'var(--success)' : 'var(--text-secondary)'};">
          ${diffSign}${lot.discount}%
        </span>
      </td>
      <td style="color: var(--text-secondary); max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        ${escapeHtml(lot.seller.name)}
      </td>
      <td style="text-align: right; white-space: nowrap;">
        <button class="btn-vanish" onclick="window.app.vanishLot(event, '${lot.id}')" title="Скрыть">✕</button>
        <button class="btn-vanish" onclick="window.app.openAvito(event, '${lot.avitoUrl}')" title="Открыть на Авито" style="color: var(--primary);">↗</button>
      </td>
    `;

    tr.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      openLotModal(lot);
    });

    DOM.tableBody.appendChild(tr);
  });
}

// ==========================================================================
// Searches Manager Section
// ==========================================================================
function renderSearchesManager() {
  if (!DOM.searchesList) return;
  DOM.searchesList.innerHTML = '';

  if (State.searches.length === 0) {
    DOM.searchesList.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; background: var(--surface-card); border-radius: 16px; border: 1px solid var(--border-subtle);">
        <div style="font-size: 32px; margin-bottom: 12px;">🎯</div>
        <div class="h3" style="margin-bottom: 6px;">Нет активных радаров</div>
        <p class="caption" style="margin-bottom: 16px;">Создайте первый поиск, чтобы запустить круглосуточный мониторинг Авито.</p>
        <button class="btn-cta" onclick="window.app.openNewSearchModal()" style="max-width: 240px; margin: 0 auto;">+ Создать поиск</button>
      </div>
    `;
    return;
  }

  State.searches.forEach(s => {
    const card = document.createElement('div');
    const isActive = s.id === State.currentSearchId;
    const lotCount = State.lots.filter(l => l.searchId === s.id && !l.isDismissed).length;
    const minPriceText = s.minPrice ? `от ${s.minPrice.toLocaleString('ru-RU')} ₽` : 'без порога цены';

    card.className = 'stat-card';
    card.style.marginBottom = '12px';
    if (isActive) {
      card.style.borderColor = 'var(--primary)';
      card.style.boxShadow = 'var(--primary-glow)';
    }

    card.innerHTML = `
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <h3 class="h3">${escapeHtml(s.query)}</h3>
            ${isActive ? '<span class="brand-badge" style="background: var(--success-bg); color: var(--success); border-color: rgba(16,185,129,0.3)">АКТИВЕН</span>' : ''}
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; font-size: 11px;" class="font-mono">
            <span style="padding: 2px 8px; border-radius: 6px; background: #0E0E11; border: 1px solid var(--border-subtle);">📍 ${escapeHtml(s.city || 'Челябинск')}</span>
            <span style="padding: 2px 8px; border-radius: 6px; background: #0E0E11; border: 1px solid var(--border-subtle);">📦 ${lotCount} лотов</span>
            <span style="padding: 2px 8px; border-radius: 6px; background: #0E0E11; border: 1px solid var(--border-subtle);">💰 ${minPriceText}</span>
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px;">
        <button class="btn-cta" onclick="window.app.selectSearch('${s.id}')" style="height: 36px; font-size: 12px; flex: 2; background: ${isActive ? 'var(--surface-hover)' : 'var(--primary-gradient)'};">
          ${isActive ? '👀 Просмотр лотов' : '⚡ Выбрать этот радар'}
        </button>
        <button class="filter-chip" onclick="window.app.scanSearch('${s.id}')" style="height: 36px; flex: 1; justify-content: center;" title="Сканировать">
          🔄 Скан
        </button>
        <button class="filter-chip" onclick="window.app.promptDelete('${s.id}', '${escapeHtml(s.query)}')" style="height: 36px; color: var(--danger); border-color: rgba(239, 68, 68, 0.3); background: var(--danger-bg); justify-content: center;">
          🗑
        </button>
      </div>
    `;

    DOM.searchesList.appendChild(card);
  });
}

// ==========================================================================
// Modals & User Actions
// ==========================================================================
function openLotModal(lot) {
  TelegramService.haptic('medium');
  State.modalLot = lot;

  document.getElementById('modalTitle').textContent = lot.title;
  document.getElementById('modalPrice').textContent = `${lot.price.toLocaleString('ru-RU')} ₽`;
  document.getElementById('modalMarketPrice').textContent = lot.marketPrice ? `Оценка рынка: ${lot.marketPrice.toLocaleString('ru-RU')} ₽` : '';
  document.getElementById('modalDiscount').textContent = lot.discount ? `${lot.discount}%` : '';
  document.getElementById('modalDescription').textContent = lot.description || 'Описание отсутствует.';
  document.getElementById('modalSellerName').textContent = lot.seller.name;
  document.getElementById('modalSellerType').textContent = lot.seller.type === 'private' ? 'Частное лицо' : 'Компания / Магазин';
  document.getElementById('modalLocation').textContent = `📍 ${lot.seller.location}`;
  document.getElementById('modalDate').textContent = `⏱ ${lot.publishedText || 'сегодня'}`;

  const ratingEl = document.getElementById('modalSellerRating');
  if (lot.seller.rating) {
    ratingEl.textContent = `★ ${lot.seller.rating}`;
    ratingEl.style.display = 'inline-block';
  } else {
    ratingEl.style.display = 'none';
  }

  const imgEl = document.getElementById('modalMainImg');
  if (lot.images && lot.images.length > 0) {
    imgEl.src = lot.images[0];
    imgEl.style.display = 'block';
  } else {
    imgEl.style.display = 'none';
  }

  // Tags
  const tagsContainer = document.getElementById('modalTags');
  tagsContainer.innerHTML = (lot.tags || []).map(t => `<span class="filter-chip" style="height: 26px; font-size: 11px;">${escapeHtml(t)}</span>`).join('');

  // CTA button
  const ctaBtn = document.getElementById('modalAvitoCta');
  ctaBtn.onclick = () => TelegramService.openLink(lot.avitoUrl);

  DOM.modalOverlay?.classList.add('open');
  DOM.bottomSheet?.classList.add('open');
}

function openNewSearchModal() {
  TelegramService.haptic('medium');
  DOM.modalOverlay?.classList.add('open');
  DOM.newSearchModal?.classList.add('open');
}

let pendingDeleteId = null;
function promptDelete(id, title) {
  TelegramService.haptic('medium');
  pendingDeleteId = id;
  document.getElementById('deleteSearchTitle').textContent = title;
  DOM.modalOverlay?.classList.add('open');
  DOM.deleteModal?.classList.add('open');
}

async function handleConfirmDelete() {
  if (!pendingDeleteId) return;
  TelegramService.haptic('heavy');
  const id = pendingDeleteId;
  closeAllModals();

  await ApiService.deleteSearch(id);
  State.searches = State.searches.filter(s => s.id !== id);
  if (State.currentSearchId === id) State.currentSearchId = 'all';

  populateSearchSelector();
  renderView();
  showToast('Радар удален', 'info');
}

async function handleNewSearchSubmit(e) {
  e.preventDefault();
  const q = document.getElementById('newQueryInput').value.trim();
  const city = document.getElementById('newCitySelect').value;
  const minP = document.getElementById('newMinPriceInput').value.trim();

  if (!q) {
    showToast('Введите название товара!', 'error');
    return;
  }

  TelegramService.haptic('success');
  closeAllModals();
  showToast(`Запуск радара для «${q}»...`, 'info');

  const newSearch = await ApiService.createSearch({
    query: q,
    city: city,
    minPrice: minP ? Number(minP) : 0,
    filters: { noDefects: true }
  });

  State.searches.unshift(newSearch);
  State.currentSearchId = newSearch.id;

  populateSearchSelector();
  await loadData();
  setViewMode('cards');
  showToast(`🎯 Радар «${q}» успешно запущен!`, 'success');
}

function closeAllModals() {
  TelegramService.haptic('light');
  DOM.modalOverlay?.classList.remove('open');
  DOM.bottomSheet?.classList.remove('open');
  DOM.newSearchModal?.classList.remove('open');
  DOM.deleteModal?.classList.remove('open');
}

function setViewMode(mode) {
  TelegramService.haptic('medium');
  State.viewMode = mode;

  ['cards', 'table', 'fav', 'searches'].forEach(m => {
    const btn = document.getElementById(`tab-${m}`);
    if (btn) {
      if (m === mode) btn.classList.add('active');
      else btn.classList.remove('active');
    }
  });

  renderView();
}

function setFilterChip(filter) {
  TelegramService.haptic('light');
  State.activeFilter = filter;

  ['all', 'deals', 'private', 'delivery', 'nodefects', 'dismissed'].forEach(f => {
    const chip = document.getElementById(`chip-${f}`);
    if (chip) {
      if (f === filter) chip.classList.add('active');
      else chip.classList.remove('active');
    }
  });

  renderView();
}

function toggleFav(event, lotId) {
  event.stopPropagation();
  TelegramService.haptic('light');
  const strId = String(lotId);
  const idx = State.favorites.indexOf(strId);
  if (idx > -1) {
    State.favorites.splice(idx, 1);
  } else {
    State.favorites.push(strId);
  }
  localStorage.setItem('avitoradar_favorites', JSON.stringify(State.favorites));
  updateStats();
  renderView();
}

// Toast notification helper
function showToast(message, type = 'info') {
  if (!DOM.toastContainer) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : '⚡';
  toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;

  DOM.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, 2800);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// Export global app handlers for HTML inline attributes
window.app = {
  setViewMode,
  setFilterChip,
  toggleFav,
  vanishLot,
  restoreLot,
  openLotModal,
  openNewSearchModal,
  closeAllModals,
  promptDelete,
  selectSearch: (id) => {
    State.currentSearchId = id;
    if (DOM.searchSelector) DOM.searchSelector.value = id;
    setViewMode('cards');
  },
  scanSearch: async (id) => {
    TelegramService.haptic('medium');
    showToast('Сканирование Авито...', 'info');
    await ApiService.triggerScan(id);
    await loadData();
    showToast('Каталог обновлен!', 'success');
  },
  openDetails: (event, lotId) => {
    event.stopPropagation();
    const lot = State.lots.find(l => String(l.id) === String(lotId));
    if (lot) openLotModal(lot);
  },
  openAvito: (event, url) => {
    event.stopPropagation();
    TelegramService.openLink(url);
  },
  setQueryPreset: (q, minP) => {
    document.getElementById('newQueryInput').value = q;
    if (minP) document.getElementById('newMinPriceInput').value = minP;
  }
};
