/**
 * AvitoRadar PRO - View layer (tabs, sheets, feed, payments).
 * Depends on js/core.js (SafeStorage, ApiService, TelegramService, State, SLUI,
 * classifiers) and js/suggestions.js (window.Suggestions). Plain script, no modules.
 */

// ==========================================================================
// 20. Small helpers
// ==========================================================================
const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtPrice(n) {
  const v = Number(n);
  if (!Number.isFinite(v) || v <= 0) return '';
  return v.toLocaleString('ru-RU');
}

// Safe interpolation into single-quoted JS args inside double-quoted HTML attrs
function jsArg(v) {
  return escapeHtml(String(v ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'"));
}

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function timeAgo(ts) {
  const t = Number(ts);
  if (!Number.isFinite(t) || t <= 0) return '';
  const diff = Date.now() - t;
  if (diff < 0) return 'только что';
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'только что';
  if (m < 60) return `${m} мин назад`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} ч назад`;
  const d = Math.floor(h / 24);
  return `${d} дн назад`;
}

function formatCountdown(iso) {
  const end = new Date(iso).getTime();
  const diff = end - Date.now();
  if (!Number.isFinite(diff) || diff <= 0) return 'срок истек';
  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (d > 0) return `осталось ${d} дн ${h} ч`;
  if (h > 0) return `осталось ${h} ч ${m} мин`;
  return `осталось ${m} мин`;
}

function formatVariantBadge(variant) {
  if (typeof variant !== 'string') return '';
  let v = variant.trim();
  if (!v) return '';
  v = v.replace(/,\s*/g, ' · ').replace(/(\d)\s*GB\b/gi, '$1 ГБ').replace(/(\d)\s*TB\b/gi, '$1 ТБ');
  return v;
}

async function copyTextToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      return true;
    } catch (_) {
      return false;
    }
  }
}

// ==========================================================================
// 21. User / plan model + lot profit helpers (new backend contract)
// ==========================================================================
State.user = null;
State.activeTab = 'radars';
State.sheet = null;
State.analysis = { loading: false, result: null, limited: false };
State.yookassaUnavailable = false;
State.addressError = '';
State.addressSaving = false;
State.editingAddress = false;
State.addressHintShown = false;

function normalizeUser(raw) {
  const d = raw || {};
  const plan = d.plan === 'pro' ? 'pro' : 'free';
  return {
    user_id: d.user_id || getCurrentUserId(),
    plan,
    pro_expires_at: d.pro_expires_at || null,
    radars_used: Number.isFinite(+d.radars_used) ? +d.radars_used : State.searches.length,
    radars_limit: Number.isFinite(+d.radars_limit) && +d.radars_limit > 0 ? +d.radars_limit : (plan === 'pro' ? 15 : 1),
    analysis_used_today: Number.isFinite(+d.analysis_used_today) ? +d.analysis_used_today : 0,
    analysis_limit: Number.isFinite(+d.analysis_limit) && +d.analysis_limit > 0 ? +d.analysis_limit : 3,
    trial_available: Boolean(d.trial_available),
    home_address: typeof d.home_address === 'string' && d.home_address.trim() ? d.home_address.trim() : null,
    referral_url: d.referral_url || '',
    stars_price_month: Number.isFinite(+d.stars_price_month) && +d.stars_price_month > 0 ? +d.stars_price_month : 299,
    stars_price_year: Number.isFinite(+d.stars_price_year) && +d.stars_price_year > 0 ? +d.stars_price_year : 1999,
    quiet_hours: normalizeQuietHours(d.quiet_hours)
  };
}

function normalizeQuietHours(raw) {
  const qh = raw || {};
  const hour = (v, fallback) => {
    const n = Number(v);
    return Number.isFinite(n) && n >= 0 && n <= 23 ? Math.round(n) : fallback;
  };
  return {
    enabled: Boolean(qh.enabled),
    start: hour(qh.start, 23),
    end: hour(qh.end, 8)
  };
}

function isPro() {
  const u = State.user;
  if (!u || u.plan !== 'pro') return false;
  if (!u.pro_expires_at) return true;
  return new Date(u.pro_expires_at).getTime() > Date.now();
}

function getLotDistanceKm(lot) {
  const v = Number(lot && lot.distance_km);
  return Number.isFinite(v) && v >= 0 ? v : null;
}

function formatDistanceKm(km) {
  if (km === null) return '';
  if (km < 1) return '<1 км';
  return `~${Number(km).toFixed(1)} км`;
}

function buildDistanceBadgeHtml(lot) {
  const km = getLotDistanceKm(lot);
  if (km === null) return '';
  const pinStroke = km <= 5 ? '#FFCC00' : 'currentColor';
  return `<span>
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="${pinStroke}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
    <span class="mono">${escapeHtml(formatDistanceKm(km))}</span>
  </span>`;
}

function getLotMarket(lot) {
  return num(lot.market_median) || num(lot.marketPrice) || 0;
}

function formatPriceDropDays(days) {
  const d = Number(days);
  if (!Number.isFinite(d) || d < 1) return 'сегодня';
  return `за ${Math.round(d)} дн`;
}

function buildPriceDropHtml(lot) {
  const drop = lot && lot.price_drop;
  const amount = num(drop && drop.amount);
  if (!drop || !amount) return '';
  return `<span class="badge-price-drop">
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>
    <span class="mono">-${fmtPrice(amount)} ₽</span> ${escapeHtml(formatPriceDropDays(drop.days))}
  </span>`;
}

const SELLER_SCORE_META = {
  reliable: { color: '#FFCC00', icon: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>' },
  reseller: { color: '#A1A1AA', icon: '<rect width="20" height="14" x="2" y="7" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>' },
  new: { color: '#F87171', icon: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>' },
  regular: { color: '#A1A1AA', icon: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>' }
};

function buildSellerScoreHtml(lot, idAttr) {
  const score = lot && lot.seller_score;
  if (!score || !score.label) return '';
  const meta = SELLER_SCORE_META[score.level] || SELLER_SCORE_META.regular;
  return `<span class="seller-score" ${idAttr ? `id="${idAttr}"` : ''} style="color: ${meta.color};">
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${meta.icon}</svg>
    ${escapeHtml(score.label)}
  </span>`;
}

function buildMarketAnalogsHtml(lot) {
  const samples = num(lot && lot.market_samples);
  const minPrice = num(lot && lot.market_min_price);
  if (!samples || samples < 3 || !minPrice) return '';
  return `<span class="market-analogs">
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>
    Аналогов на рынке: <span class="mono">${samples}</span> · от <span class="mono">${fmtPrice(minPrice)} ₽</span>
  </span>`;
}

function getLotProfitAbs(lot) {
  if (Number.isFinite(+lot.profit_abs)) return Math.round(+lot.profit_abs);
  const m = getLotMarket(lot);
  if (m > 0 && lot.price > 0) return Math.round(m - lot.price);
  return 0;
}

function getLotProfitPct(lot) {
  if (Number.isFinite(+lot.profit_pct)) return Math.round(+lot.profit_pct * 10) / 10;
  const m = getLotMarket(lot);
  if (m > 0 && lot.price > 0) return Math.round(((m - lot.price) / m) * 1000) / 10;
  return 0;
}

function getLotBuyPrice(lot) {
  return num(lot.recommended_buy) || 0;
}

// Fresh lots (younger than 15 min) are blurred for free users.
// Backend may flag them explicitly via delayed / is_delayed.
const PRO_FRESH_WINDOW_MS = 15 * 60 * 1000;

function isLotLocked(lot) {
  if (isPro()) return false;
  if (lot.delayed === true || lot.is_delayed === true) return true;
  const t = Number(lot.postedAt);
  if (Number.isFinite(t) && t > 0) return (Date.now() - t) < PRO_FRESH_WINDOW_MS;
  return false;
}

// ==========================================================================
// 22. ApiService extensions (new endpoints, same auth headers)
// ==========================================================================
Object.assign(ApiService, {
  async getBundle() {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/bundle?user_id=${encodeURIComponent(uid)}`, {
        headers: getApiHeaders()
      });
      if (res.ok) {
        this.networkFailed = false;
        return await res.json();
      }
      this.networkFailed = true;
    } catch (err) {
      this.networkFailed = true;
      console.warn('[API] getBundle failed:', err.message);
    }
    return null;
  },

  async getUser() {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/user?user_id=${encodeURIComponent(uid)}`, {
        headers: getApiHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        return data.user || (data.plan ? data : null);
      }
    } catch (err) {
      console.warn('[API] getUser failed:', err.message);
    }
    return null;
  },

  async activateTrial() {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/trial`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ user_id: uid })
      });
      if (res.ok) return await res.json();
    } catch (err) {
      console.warn('[API] activateTrial failed:', err.message);
    }
    return null;
  },

  async payStars(planId) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/pay/stars`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ user_id: uid, plan_id: planId })
      });
      if (res.ok) return await res.json();
    } catch (err) {
      console.warn('[API] payStars failed:', err.message);
    }
    return null;
  },

  // Returns { payment_url } or { notAvailable: true } on 501.
  async payYookassa(planId) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/pay/yookassa`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ user_id: uid, plan_id: planId })
      });
      if (res.status === 501) return { notAvailable: true };
      if (res.ok) return await res.json();
    } catch (err) {
      console.warn('[API] payYookassa failed:', err.message);
    }
    return null;
  },

  // Returns analysis payload, or { limited: true } on 429, or { error: true }.
  async runAnalysis(query, city) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/analysis`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ user_id: uid, query, city })
      });
      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        return { limited: true, ...data };
      }
      if (!res.ok) return { error: true, status: res.status };
      return await res.json();
    } catch (err) {
      console.warn('[API] runAnalysis failed:', err.message);
      return { error: true, offline: true };
    }
  },

  // payload: string | {address} | {lat, lon, display_name}
  // Returns { ok: true, display_name, lat, lon } on 200,
  // { ok: false, message } on 422, { ok: false, offline: true } on network failure.
  async setAddress(payload) {
    const uid = getCurrentUserId();
    let body;
    if (typeof payload === 'string' || payload == null) {
      body = { user_id: uid, address: payload || '' };
    } else {
      body = { user_id: uid, ...payload };
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/user/address`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify(body)
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({ ok: true }));
        return { ok: true, ...data };
      }
      if (res.status === 422) {
        const data = await res.json().catch(() => ({}));
        return { ok: false, message: data.message || 'Адрес не найден, уточните улицу и город' };
      }
      return { ok: false, message: 'Сервер недоступен' };
    } catch (err) {
      console.warn('[API] setAddress failed:', err.message);
      return { ok: false, offline: true, message: 'Сервер недоступен' };
    }
  },

  // Address autocomplete. Returns array (may be empty) or null on network failure.
  async suggestAddress(q) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/address/suggest?user_id=${encodeURIComponent(uid)}&q=${encodeURIComponent(q)}`, {
        headers: getApiHeaders()
      });
      if (!res.ok) return null;
      const data = await res.json();
      return Array.isArray(data.suggestions) ? data.suggestions : [];
    } catch (err) {
      return null;
    }
  },

  // Reverse geocoding. Returns { display_name, short, lat, lon } or null (404 / network).
  async reverseAddress(lat, lon) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/address/reverse?user_id=${encodeURIComponent(uid)}&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`, {
        headers: getApiHeaders()
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (err) {
      return null;
    }
  },

  // Best-effort quiet-hours update (POST /api/user/quiet_hours)
  async setQuietHours(enabled, start, end) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/user/quiet_hours`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ user_id: uid, enabled, start, end })
      });
      if (res.ok) return { ok: true };
      const data = await res.json().catch(() => ({}));
      return { ok: false, message: data.message || 'Сервер недоступен' };
    } catch (err) {
      console.warn('[API] setQuietHours failed:', err.message);
      return { ok: false, message: 'Сервер недоступен' };
    }
  },

  // Best-effort radar activity toggle (no-op while backend has no such route)
  async toggleSearchActive(id, isActive) {
    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/searches/toggle`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ id, name: id, is_active: isActive, user_id: uid })
      });
    } catch (_) {}
    return true;
  }
});

// ==========================================================================
// 23. Toasts
// ==========================================================================
function showToast(message, type = 'info') {
  const container = $('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const icon = type === 'success'
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FFCC00" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
    : type === 'error'
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F87171" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
    : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
  toast.innerHTML = `<span style="display: inline-flex; align-items: center;">${icon}</span><span>${escapeHtml(message)}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 260);
  }, 2800);
}

// ==========================================================================
// 24. Bottom sheet controller (with drag-to-close)
// ==========================================================================
const SHEET_IDS = ['sheetRadar', 'sheetLot', 'sheetDelete'];

function openSheet(id) {
  State.sheet = id;
  $('sheetBackdrop')?.classList.add('open');
  SHEET_IDS.forEach(sid => $(sid)?.classList.toggle('open', sid === id));
  document.body.style.overflow = 'hidden';
  syncTelegramButtons();
}

function closeSheets() {
  if (!State.sheet) return;
  TelegramService.haptic('light');
  State.sheet = null;
  $('sheetBackdrop')?.classList.remove('open');
  SHEET_IDS.forEach(sid => $(sid)?.classList.remove('open'));
  document.body.style.overflow = '';
  State.pendingDeleteId = null;
  syncTelegramButtons();
}

function attachSheetDrag(sheet) {
  const handle = sheet?.querySelector('.sheet-handle-bar');
  if (!handle) return;
  let startY = 0;
  let dy = 0;
  let dragging = false;

  handle.addEventListener('touchstart', (e) => {
    dragging = true;
    startY = e.touches[0].clientY;
    dy = 0;
    sheet.classList.add('dragging');
  }, { passive: true });

  handle.addEventListener('touchmove', (e) => {
    if (!dragging) return;
    dy = Math.max(0, e.touches[0].clientY - startY);
    sheet.style.transform = `translateY(${dy}px)`;
  }, { passive: true });

  const end = () => {
    if (!dragging) return;
    dragging = false;
    sheet.classList.remove('dragging');
    sheet.style.transform = '';
    if (dy > 90) closeSheets();
  };
  handle.addEventListener('touchend', end);
  handle.addEventListener('touchcancel', end);
}

// ==========================================================================
// 25. Tab controller + Telegram MainButton / BackButton
// ==========================================================================
const TAB_IDS = ['radars', 'analysis', 'feed', 'pro'];

function switchTab(tab) {
  if (!TAB_IDS.includes(tab)) return;
  TelegramService.haptic('light');
  State.activeTab = tab;

  TAB_IDS.forEach(t => {
    $(`screen-${t}`)?.classList.toggle('active', t === tab);
    document.querySelector(`.nav-item[data-tab="${t}"]`)?.classList.toggle('active', t === tab);
  });

  const fab = $('fabAddRadar');
  if (fab) fab.style.display = tab === 'radars' ? 'flex' : 'none';

  renderScreen(tab);
  syncTelegramButtons();
}

function renderScreen(tab) {
  if (tab === 'radars') renderRadars();
  else if (tab === 'feed') renderFeed();
  else if (tab === 'analysis') renderAnalysisScreen();
  else if (tab === 'pro') renderPro();
}

function syncTelegramButtons() {
  if (!tg) return;
  try {
    if (tg.BackButton) {
      if (State.sheet || State.activeTab !== 'radars') tg.BackButton.show();
      else tg.BackButton.hide();
    }
  } catch (_) {}
  syncMainButton();
}

function syncMainButton() {
  if (!tg?.MainButton) return;
  try {
    const q = ($('analysisQuery')?.value || '').trim();
    if (State.activeTab === 'analysis' && !State.sheet && q.length >= 2 && !State.analysis.loading) {
      tg.MainButton.setText('Оценить рынок');
      if (!tg.MainButton.isVisible) tg.MainButton.show();
    } else if (tg.MainButton.isVisible) {
      tg.MainButton.hide();
    }
  } catch (_) {}
}

function renderHeader() {
  const badge = $('headerPlanBadge');
  if (badge) {
    const pro = isPro();
    badge.textContent = pro ? 'PRO' : 'FREE';
    badge.classList.toggle('is-pro', pro);
  }
}

// ==========================================================================
// 26. Scan progress modal
// ==========================================================================
const ScanProgress = {
  timer: null,
  percent: 15,

  start(query, city) {
    const modal = $('scanProgressModal');
    if (!modal) return;
    if (this.timer) clearInterval(this.timer);
    this.percent = 15;

    const cityAbbr = getCityAbbr(city);
    const cityLabel = (city && String(city).toLowerCase() === 'rossiya') ? 'Вся Россия' : `[${cityAbbr}]`;

    const t = $('scanModalTitle');
    const s = $('scanModalSub');
    if (t) t.textContent = `Сканирование «${query}»`;
    if (s) s.textContent = `Регион: ${cityLabel} · Мониторинг Авито 24/7`;

    this.setProgress(15, 'Подключение к каталогу Avito...', 1);
    modal.classList.remove('hidden');

    this.timer = setInterval(() => {
      if (this.percent < 45) {
        this.percent += 8;
        this.setProgress(this.percent, `Поиск лотов «${query}» на Авито...`, 2);
      } else if (this.percent < 75) {
        this.percent += 6;
        this.setProgress(this.percent, 'Сбор объявлений, цен и фото...', 2);
      } else if (this.percent < 90) {
        this.percent += 3;
        this.setProgress(this.percent, 'Оценка рыночной стоимости...', 3);
      }
    }, 450);
  },

  setProgress(pct, text, activeStep) {
    const bar = $('scanProgressBar');
    const pctEl = $('scanStatusPercent');
    const stepEl = $('scanStatusStepText');
    if (bar) bar.style.width = `${Math.min(100, pct)}%`;
    if (pctEl) pctEl.textContent = `${Math.min(100, Math.round(pct))}%`;
    if (stepEl && text) stepEl.textContent = text;

    for (let i = 1; i <= 4; i++) {
      const pill = $(`scanPill${i}`);
      if (!pill) continue;
      pill.className = i < activeStep ? 'scan-pill done' : i === activeStep ? 'scan-pill active' : 'scan-pill';
    }
  },

  finish(count) {
    if (this.timer) clearInterval(this.timer);
    this.setProgress(100, count > 0 ? `Найдено ${count} объявлений · Готово` : 'Сканирование завершено', 4);
    setTimeout(() => $('scanProgressModal')?.classList.add('hidden'), 600);
  }
};

// ==========================================================================
// 27. Data loading (bundle-first, legacy endpoints as fallback)
// ==========================================================================
async function loadData() {
  if (State.lots.length === 0 && State.activeTab === 'feed') renderFeedSkeletons(4);

  try {
    const savedFavs = SafeStorage.getItem(getUserStorageKey('favorites'));
    if (savedFavs) State.favorites = JSON.parse(savedFavs);
  } catch (_) {}

  const bundle = await ApiService.getBundle();
  let gotSearches = false;
  let gotLots = false;

  if (bundle && typeof bundle === 'object' && !Array.isArray(bundle)) {
    if (bundle.user) State.user = normalizeUser(bundle.user);
    if (Array.isArray(bundle.searches)) {
      State.searches = bundle.searches;
      gotSearches = true;
    }
    if (Array.isArray(bundle.lots)) {
      State.lots = bundle.lots;
      gotLots = true;
    }
  }

  if (!gotSearches) State.searches = await ApiService.getSearches();
  if (!gotLots) State.lots = await ApiService.getLots({ includeDismissed: true });

  if (!State.user) {
    const u = await ApiService.getUser();
    if (u) State.user = normalizeUser(u);
  }

  const dismissedSet = ApiService.getDismissedIds();
  State.lots.forEach(l => {
    if (dismissedSet.has(String(l.id))) l.isDismissed = true;
  });

  // Offline / stale-data signaling
  const wasOffline = State.networkError;
  State.networkError = ApiService.networkFailed && State.searches.length === 0 && State.lots.length === 0;
  if (State.networkError && !wasOffline) {
    TelegramService.haptic('error');
    showToast('Нет соединения с сервером', 'error');
  } else if (wasOffline && !ApiService.networkFailed) {
    TelegramService.haptic('success');
    showToast('Соединение восстановлено', 'success');
  } else if (ApiService.networkFailed && !State.networkError) {
    const now = Date.now();
    if (!State.lastStaleToastAt || now - State.lastStaleToastAt > 20000) {
      State.lastStaleToastAt = now;
      TelegramService.haptic('warning');
      showToast('Сервер недоступен - показаны сохраненные данные', 'error');
    }
  }

  if (State.currentSearchId && State.currentSearchId !== 'all' &&
      !State.searches.some(s => s.id === State.currentSearchId)) {
    State.currentSearchId = 'all';
  }

  renderHeader();
  renderScreen(State.activeTab);
}

async function refreshUser() {
  const u = await ApiService.getUser();
  if (u) State.user = normalizeUser(u);
  renderHeader();
}

// ==========================================================================
// 28. Radars tab
// ==========================================================================
function getRadarsUsage() {
  const u = State.user;
  const used = Math.max(u ? u.radars_used : 0, State.searches.length);
  const limit = u ? u.radars_limit : (isPro() ? 15 : 1);
  return { used, limit };
}

function radarsLimitReached() {
  const { used, limit } = getRadarsUsage();
  return used >= limit;
}

function renderRadars() {
  const limitCard = $('radarsLimitCard');
  const list = $('radarsList');
  if (!list) return;

  const { used, limit } = getRadarsUsage();
  const maxed = used >= limit;

  if (limitCard) {
    limitCard.classList.remove('hidden');
    const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
    limitCard.innerHTML = `
      <div class="limit-row">
        <span class="limit-label">${isPro() ? 'Радаров использовано (PRO)' : 'Радаров на бесплатном тарифе'}</span>
        <span class="limit-value mono ${maxed ? 'is-maxed' : ''}">${used} из ${limit}</span>
      </div>
      <div class="progress"><div class="progress-fill ${maxed ? 'is-maxed' : ''}" style="width: ${pct}%;"></div></div>
    `;
  }

  if (State.searches.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#FFCC00" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
        </svg>
        <div class="h3">Радары пока не настроены</div>
        <p class="caption">Добавьте товар для мониторинга. Бот круглосуточно сканирует Авито и перехватывает предложения ниже рынка.</p>
        <button class="btn btn-accent" onclick="window.app.openRadarSheet()">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          <span>Создать радар</span>
        </button>
      </div>
    `;
    return;
  }

  list.innerHTML = '';

  State.searches.forEach(s => {
    const lotCount = State.lots.filter(l => l.searchId === s.id && !l.isDismissed).length;
    const cleanTitle = cleanQueryTitle(s.query || s.title || s.id);
    const minPriceText = s.minPrice ? `от ${fmtPrice(s.minPrice)} ₽` : 'без порога цены';
    const interval = s.interval || s.interval_text || 'каждые 5 мин';
    const isActive = s.isActive !== false;

    const card = document.createElement('div');
    card.className = 'radar-card';
    card.innerHTML = `
      <div class="radar-card-top">
        <div style="min-width: 0; flex: 1;">
          <h3 class="radar-card-title">${escapeHtml(cleanTitle)}</h3>
          <div class="radar-card-meta">
            <span>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
              ${escapeHtml(s.city || 'Челябинск')}
            </span>
            <span>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              ${escapeHtml(interval)}
            </span>
            <span class="mono">${lotCount} находок</span>
            <span class="mono">${escapeHtml(minPriceText)}</span>
          </div>
        </div>
        <label class="switch" title="${isActive ? 'Радар активен' : 'Радар на паузе'}">
          <input type="checkbox" ${isActive ? 'checked' : ''} onchange="window.app.toggleRadarActive('${jsArg(s.id)}', this.checked)">
          <span class="switch-track"></span>
          <span class="switch-thumb"></span>
        </label>
      </div>
      <div class="radar-card-actions">
        <button class="btn btn-ghost" style="flex: 1.4;" onclick="window.app.selectRadar('${jsArg(s.id)}')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          <span>Лоты (${lotCount})</span>
        </button>
        <button class="btn btn-ghost" style="flex: 1;" onclick="window.app.scanSearch('${jsArg(s.id)}')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg>
          <span>Скан</span>
        </button>
        <button class="btn btn-danger" style="flex: 0 0 44px; padding: 0;" onclick="window.app.promptDelete('${jsArg(s.id)}', '${jsArg(formatSearchDisplay(s))}')" title="Удалить радар">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
        </button>
      </div>
    `;
    list.appendChild(card);
  });
}

function selectRadar(id) {
  TelegramService.haptic('light');
  State.currentSearchId = id;
  switchTab('feed');
}

function toggleRadarActive(id, checked) {
  TelegramService.haptic('selection');
  const s = State.searches.find(x => x.id === id);
  if (s) {
    s.isActive = checked;
    SafeStorage.setItem(getUserStorageKey('searches'), JSON.stringify(State.searches));
  }
  ApiService.toggleSearchActive(id, checked);
  showToast(checked ? 'Радар активирован' : 'Радар поставлен на паузу', 'info');
}

function openRadarSheet() {
  TelegramService.haptic('medium');
  const main = $('radarSheetMain');
  const upsell = $('radarSheetUpsell');
  const limited = radarsLimitReached();
  if (main) main.classList.toggle('hidden', limited);
  if (upsell) upsell.classList.toggle('hidden', !limited);
  openSheet('sheetRadar');
}

function setQueryPreset(q, minP) {
  TelegramService.haptic('light');
  const qInput = $('newQueryInput');
  if (qInput) qInput.value = q;
  const priceInput = $('newMinPrice');
  if (priceInput && typeof minP === 'number') {
    priceInput.value = String(Math.min(Number(priceInput.max), Math.max(Number(priceInput.min), minP)));
    priceInput.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

// ==========================================================================
// 29. Create / delete / scan radar
// ==========================================================================
async function handleNewSearchSubmit(e) {
  if (e) e.preventDefault();

  if (radarsLimitReached()) {
    openRadarSheet();
    return;
  }

  const qEl = $('newQueryInput');
  const cityEl = $('newCitySelect');
  const q = qEl ? qEl.value.trim() : '';
  const city = cityEl ? cityEl.value : 'chelyabinsk';

  if (!q) {
    showToast('Введите название товара', 'error');
    return;
  }

  const excludeAccEl = $('newExcludeAccessories');
  const excludeAcc = excludeAccEl ? excludeAccEl.checked : true;
  const minPriceEl = $('newMinPrice');
  const minPrice = minPriceEl ? Math.max(0, minPriceEl.valueAsNumber || 0) : 0;

  TelegramService.haptic('success');
  closeSheets();
  ScanProgress.start(q, city);

  try {
    const newSearch = await ApiService.createSearch({
      query: q,
      city: city,
      minPrice: minPrice,
      filters: { noDefects: true, excludeAccessories: excludeAcc }
    });

    State.searches = State.searches.filter(s => s.id !== newSearch.id);
    State.searches.unshift(newSearch);
    State.currentSearchId = newSearch.id;
    if (State.user) State.user.radars_used = getRadarsUsage().used;

    await loadData();
    ScanProgress.finish(0);
    TelegramService.haptic('success');
    switchTab('radars');
    showToast('Радар создан, первый скан идет', 'success');
  } catch (err) {
    console.error('Search creation failed:', err);
    ScanProgress.finish(0);
    showToast('Ошибка при запуске радара', 'error');
  }
}

function promptDelete(id, title) {
  TelegramService.haptic('medium');
  State.pendingDeleteId = id;
  const titleEl = $('deleteSearchTitle');
  if (titleEl) titleEl.textContent = title;
  openSheet('sheetDelete');
}

async function handleConfirmDelete() {
  if (!State.pendingDeleteId) return;
  TelegramService.haptic('heavy');
  const id = State.pendingDeleteId;
  closeSheets();

  await ApiService.deleteSearch(id);
  State.searches = State.searches.filter(s => s.id !== id);
  State.lots = State.lots.filter(l => l.searchId !== id);
  SafeStorage.setItem(getUserStorageKey('lots'), JSON.stringify(State.lots));
  if (State.user) State.user.radars_used = getRadarsUsage().used;

  if (State.currentSearchId === id) State.currentSearchId = 'all';

  renderHeader();
  renderScreen(State.activeTab);
  showToast('Радар удален из отслеживания', 'info');
}

async function scanSearch(id) {
  TelegramService.haptic('medium');
  const s = State.searches.find(x => x.id === id);
  const title = s ? (s.query || s.title || id) : id;
  const city = s ? s.city : 'Челябинск';
  ScanProgress.start(title, city);

  try {
    const scanOk = await ApiService.triggerScan(id);
    await loadData();
    const lotsCount = State.lots.filter(l => l.searchId === id && !l.isDismissed).length;
    ScanProgress.finish(lotsCount);
    if (!scanOk && ApiService.networkFailed) {
      TelegramService.haptic('error');
      showToast('Сервер не отвечает - сканирование не запустилось', 'error');
      return;
    }
    TelegramService.haptic(lotsCount > 0 ? 'success' : 'medium');
    renderScreen(State.activeTab);
    showToast(lotsCount > 0 ? `Найдено ${lotsCount} лотов` : 'Новых лотов пока нет', lotsCount > 0 ? 'success' : 'info');
  } catch (err) {
    ScanProgress.finish(0);
    showToast('Ошибка при сканировании', 'error');
  }
}

// ==========================================================================
// 30. Analysis tab
// ==========================================================================
function renderAnalysisScreen() {
  renderAnalysisMeta();
  renderAnalysisResult();
  syncMainButton();
}

function renderAnalysisMeta() {
  const el = $('analysisRemaining');
  if (!el) return;
  if (isPro()) {
    el.textContent = 'Безлимитные оценки · PRO';
    el.style.color = 'var(--accent)';
    return;
  }
  const u = State.user;
  if (!u) {
    el.textContent = '';
    return;
  }
  const left = Math.max(0, u.analysis_limit - u.analysis_used_today);
  el.textContent = `Осталось оценок сегодня: ${left}`;
  el.style.color = left === 0 ? 'var(--warn)' : '';
}

async function submitAnalysis(e) {
  if (e) e.preventDefault();
  const qEl = $('analysisQuery');
  const cityEl = $('analysisCity');
  const q = qEl ? qEl.value.trim() : '';
  const city = cityEl ? cityEl.value : 'rossiya';

  if (!q) {
    showToast('Введите название товара', 'error');
    return;
  }

  if (!isPro() && State.user && State.user.analysis_used_today >= State.user.analysis_limit) {
    State.analysis.limited = true;
    State.analysis.result = null;
    renderAnalysisResult();
    TelegramService.haptic('warning');
    return;
  }

  TelegramService.haptic('medium');
  State.analysis.loading = true;
  State.analysis.limited = false;
  State.analysis.result = null;
  $('analysisSkeleton')?.classList.remove('hidden');
  renderAnalysisResult();
  syncMainButton();

  const r = await ApiService.runAnalysis(q, city);

  State.analysis.loading = false;
  $('analysisSkeleton')?.classList.add('hidden');

  if (r && r.limited) {
    State.analysis.limited = true;
    State.analysis.result = null;
    TelegramService.haptic('warning');
  } else if (!r || r.error) {
    State.analysis.result = null;
    State.analysis.limited = false;
    TelegramService.haptic('error');
    showToast(r && r.offline ? 'Нет соединения с сервером' : 'Не удалось выполнить оценку', 'error');
  } else {
    State.analysis.result = r;
    State.analysis.limited = false;
    if (State.user && !isPro()) State.user.analysis_used_today += 1;
    TelegramService.haptic('success');
  }

  renderAnalysisMeta();
  renderAnalysisResult();
  syncMainButton();
}

function renderAnalysisResult() {
  const box = $('analysisResult');
  if (!box) return;

  if (State.analysis.limited) {
    box.innerHTML = `
      <div class="card" style="text-align: center; border-color: var(--accent-border);">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#FFCC00" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="margin: 4px auto 10px;"><path d="M11.6 3.3a.5.5 0 0 1 .8 0l2.9 5.5a1 1 0 0 0 1.5.3l4.3-3.6a.5.5 0 0 1 .8.5L19 16.2a1 1 0 0 1-1 .8H6a1 1 0 0 1-1-.8L2.1 6a.5.5 0 0 1 .8-.5l4.3 3.6a1 1 0 0 0 1.5-.3z"/><path d="M5 21h14"/></svg>
        <div class="h3" style="margin-bottom: 6px;">Лимит оценок исчерпан</div>
        <p class="caption" style="margin-bottom: 16px; line-height: 1.55;">На бесплатном тарифе доступно ${State.user ? State.user.analysis_limit : 3} оценки в сутки. PRO снимает лимит полностью.</p>
        <button class="btn btn-accent" onclick="window.app.switchTab('pro')">Перейти на PRO</button>
      </div>
    `;
    return;
  }

  const r = State.analysis.result;
  if (!r) {
    box.innerHTML = '';
    return;
  }

  const median = num(r.market_median ?? r.median ?? r.marketMedian);
  const buy = num(r.recommended_buy ?? r.recommendedBuy ?? r.buy_price);
  const lo = num(r.price_min ?? r.min ?? r.range_min ?? (r.range && r.range.min));
  const hi = num(r.price_max ?? r.max ?? r.range_max ?? (r.range && r.range.max));
  const count = num(r.sample_size ?? r.count ?? r.items_count ?? r.lots_count ?? r.lots);

  if (!median) {
    box.innerHTML = `
      <div class="card" style="text-align: center;">
        <div class="h3" style="margin-bottom: 6px;">Недостаточно данных</div>
        <p class="caption">По этому запросу пока мало объявлений для честной оценки. Попробуйте уточнить модель или регион.</p>
      </div>
    `;
    return;
  }

  box.innerHTML = `
    <div class="card">
      <div class="caption-dim" style="text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;">Медиана рынка</div>
      <div class="analysis-result-median">${fmtPrice(median)} ₽</div>
      ${count ? `<div class="caption-dim mono">по выборке из ${count} объявлений</div>` : ''}
      <div class="analysis-grid">
        <div class="analysis-cell">
          <div class="caption-dim">Выкуп до</div>
          <div class="mono is-accent">${buy ? fmtPrice(buy) + ' ₽' : '-'}</div>
        </div>
        <div class="analysis-cell">
          <div class="caption-dim">Диапазон рынка</div>
          <div class="mono">${lo && hi ? `${fmtPrice(lo)} - ${fmtPrice(hi)} ₽` : '-'}</div>
        </div>
      </div>
      ${buy && median ? `<p class="caption" style="margin-top: 12px; line-height: 1.5;">Все что дешевле <b class="mono" style="color: var(--accent);">${fmtPrice(buy)} ₽</b> - потенциально выгодный выкуп под перепродажу по медиане.</p>` : ''}
    </div>
  `;
}

// ==========================================================================
// 31. Feed tab
// ==========================================================================
function setFeedChip(chip) {
  TelegramService.haptic('light');
  State.activeFilter = chip;
  document.querySelectorAll('#feedChips .chip').forEach(c => {
    c.classList.toggle('active', c.dataset.chip === chip);
  });
  renderFeed();
}

function applyFeedFilter(query) {
  State.searchQuery = (query || '').trim().toLowerCase();
  const input = $('feedFilterInput');
  if (input && input.value !== query) input.value = query || '';
  renderFeed();
}

function getVisibleLots() {
  let lots = [...State.lots];

  const currentSearch = State.searches.find(s => s.id === State.currentSearchId);
  const searchQ = currentSearch?.query || '';

  if (State.currentSearchId && State.currentSearchId !== 'all') {
    lots = lots.filter(l => l.searchId === State.currentSearchId);
    if (searchQ) lots = lots.filter(l => isItemMatchingSearch(l.title, l.description, searchQ));
  }

  if (State.activeFilter === 'dismissed') lots = lots.filter(l => l.isDismissed);
  else lots = lots.filter(l => !l.isDismissed);

  const shouldFilterAcc = State.excludeAccessories && State.activeFilter !== 'all' && State.activeFilter !== 'dismissed';
  if (shouldFilterAcc) lots = lots.filter(l => !isAccessoryLot(l, searchQ));

  if (State.activeFilter === 'deals') {
    lots = lots.filter(l => {
      const defect = getLotDefectInfo(l);
      return getLotProfitAbs(l) > 0 && !l.isComboListing && !defect.isDefect && !isExchangeLot(l) && !isAccessoryLot(l, searchQ);
    });
  } else if (State.activeFilter === 'private') {
    lots = lots.filter(l => l.seller?.type === 'private');
  } else if (State.activeFilter === 'nodefects') {
    lots = lots.filter(l => !(l.tags || []).some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное')));
  }

  if (State.searchQuery) {
    lots = lots.filter(l => {
      const text = `${l.title} ${l.description || ''} ${l.seller?.name || ''} ${l.seller?.location || ''}`.toLowerCase();
      return text.includes(State.searchQuery);
    });
  }

  if (State.sortMode === 'cheap') lots.sort((a, b) => (a.price || 0) - (b.price || 0));
  else if (State.sortMode === 'expensive') lots.sort((a, b) => (b.price || 0) - (a.price || 0));
  else if (State.sortMode === 'date') lots.sort((a, b) => (b.postedAt || 0) - (a.postedAt || 0));
  else lots.sort((a, b) => getLotProfitAbs(b) - getLotProfitAbs(a));

  return lots;
}

function renderFeed() {
  const list = $('feedList');
  const empty = $('feedEmpty');
  if (!list) return;

  renderFeedSelectors();

  const hintEl = $('feedAddressHint');
  if (hintEl) {
    const noAddress = !State.user || !State.user.home_address;
    const showHint = noAddress && !State.addressHintShown && State.lots.length > 0;
    if (showHint) {
      State.addressHintShown = true;
      hintEl.innerHTML = `
        <span>Укажите адрес в профиле, чтобы видеть расстояние до находок</span>
        <button class="btn btn-accent btn-sm" style="flex: 0 0 auto; height: 30px; font-size: 11px; padding: 0 12px;" onclick="window.app.goToAddress()">Указать</button>
        <button class="address-hint-close" onclick="window.app.dismissAddressHint()" title="Скрыть подсказку">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      `;
    }
    hintEl.classList.toggle('hidden', !showHint);
  }

  const dismissedEl = $('dismissedCount');
  if (dismissedEl) dismissedEl.textContent = State.lots.filter(l => l.isDismissed).length;

  const dot = $('feedNavDot');
  if (dot) {
    const hasDeals = State.lots.some(l => !l.isDismissed && getLotProfitAbs(l) > 0);
    dot.classList.toggle('hidden', !hasDeals);
  }

  const visible = getVisibleLots();

  if (visible.length === 0) {
    list.innerHTML = '';
    list.classList.add('hidden');
    if (empty) {
      empty.classList.remove('hidden');
      renderFeedEmpty(empty);
    }
    return;
  }

  if (empty) {
    empty.classList.add('hidden');
    empty.innerHTML = '';
  }
  list.classList.remove('hidden');

  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  list.innerHTML = '';
  visible.forEach((lot, idx) => {
    const card = createFeedCard(lot);
    if (!reducedMotion) {
      card.classList.add('card-enter');
      card.style.animationDelay = `${Math.min(idx, 10) * 45}ms`;
    }
    list.appendChild(card);
  });
}

function renderFeedSelectors() {
  const sel = $('feedSearchSelect');
  if (sel) {
    const prev = State.currentSearchId || 'all';
    sel.innerHTML = '';
    const allOpt = document.createElement('option');
    allOpt.value = 'all';
    allOpt.textContent = 'Все радары';
    sel.appendChild(allOpt);
    State.searches.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      const count = State.lots.filter(l => l.searchId === s.id && !l.isDismissed).length;
      opt.textContent = `${formatSearchDisplay(s)} (${count})`;
      sel.appendChild(opt);
    });
    sel.value = State.searches.some(s => s.id === prev) ? prev : 'all';
    State.currentSearchId = sel.value;
  }
  const sortSel = $('feedSortSelect');
  if (sortSel && sortSel.value !== State.sortMode) sortSel.value = State.sortMode;
}

function renderFeedSkeletons(count) {
  const list = $('feedList');
  if (!list) return;
  list.classList.remove('hidden');
  list.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const sk = document.createElement('div');
    sk.className = 'sk-card';
    sk.innerHTML = `
      <div class="skeleton sk-media"></div>
      <div class="skeleton sk-line w40"></div>
      <div class="skeleton sk-line w80"></div>
      <div class="skeleton sk-line h20"></div>
      <div class="skeleton sk-line w60"></div>
    `;
    list.appendChild(sk);
  }
}

function renderFeedEmpty(box) {
  if (State.networkError) {
    box.innerHTML = `
      <div class="fb-retry-scope" data-feedback="retry" tabindex="-1">
        <div class="fb-retry-card" data-state="error">
          <span class="fb-icon"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.2 7a8 8 0 0 1 13.4-1L20 8M4 16l1.4 2A8 8 0 0 0 18.8 17"/></svg></span>
          <h3 data-title>Не удалось загрузить данные</h3>
          <p data-detail>Сервер не отвечает. Ваши радары и избранное сохранены на этом устройстве.</p>
          <div class="fb-row">
            <button type="button" class="fb-button fb-button--light" data-action="retry">Повторить</button>
            <small data-state-label>ОШИБКА ЗАПРОСА</small>
          </div>
        </div>
        <span class="fb-sr" data-live role="status" aria-live="polite" aria-atomic="true"></span>
        <span class="fb-sr" data-error role="alert" aria-atomic="true"></span>
      </div>
    `;
    const retryRoot = box.querySelector('.fb-retry-scope');
    if (retryRoot) {
      SLUI.mountRetry(retryRoot, {
        onAction: async () => {
          TelegramService.haptic('light');
          await loadData();
          if (ApiService.networkFailed) throw new Error('server-unreachable');
        }
      });
    }
    return;
  }

  if (State.searches.length === 0) {
    box.innerHTML = `
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#FFCC00" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
        <div class="h3">Сначала создайте радар</div>
        <p class="caption">Лента наполнится находками, как только радар начнет мониторинг Авито.</p>
        <button class="btn btn-accent" onclick="window.app.switchTab('radars'); window.app.openRadarSheet()">Создать радар</button>
      </div>
    `;
    return;
  }

  if (State.activeFilter !== 'all' || State.searchQuery) {
    box.innerHTML = `
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
        <div class="h3">Ничего не найдено</div>
        <p class="caption">Под текущий фильтр ничего не подходит. Сбросьте фильтры, чтобы увидеть все лоты.</p>
        <button class="btn btn-ghost" onclick="window.app.setFeedChip('all'); window.app.applyFeedFilter('');">Сбросить фильтры</button>
      </div>
    `;
    return;
  }

  const scopedId = State.currentSearchId;
  box.innerHTML = `
    <div class="empty-state">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#A1A1AA" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <div class="h3">Объявлений пока нет</div>
      <p class="caption">Радар работает 24/7 и пришлет уведомление при появлении свежих лотов. Можно запустить сканирование вручную.</p>
      ${scopedId && scopedId !== 'all'
        ? `<button class="btn btn-accent" onclick="window.app.scanSearch('${jsArg(scopedId)}')">Просканировать Авито сейчас</button>`
        : `<button class="btn btn-accent" onclick="window.app.refreshAll()">Обновить ленту</button>`}
    </div>
  `;
}

function buildDealBadgeHtml(lot, profitAbs, profitPct) {
  if (lot.deal_badge) {
    return `<span class="badge-deal">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>
      ${escapeHtml(lot.deal_badge)}
    </span>`;
  }
  if (profitAbs > 0) {
    const pctText = profitPct !== 0 ? ` (${profitPct > 0 ? '-' : ''}${Math.abs(profitPct)}%)` : '';
    return `<span class="badge-deal">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>
      -${fmtPrice(profitAbs)} ₽${pctText}
    </span>`;
  }
  return '';
}

function createFeedCard(lot) {
  const card = document.createElement('article');
  card.className = 'lot-card' + (lot.is_repost === true ? ' is-repost' : '');
  card.dataset.id = lot.id;

  const defectInfo = getLotDefectInfo(lot);
  const exchangeInfo = isExchangeLot(lot);
  const searchObj = State.searches.find(s => s.id === lot.searchId);
  const searchQ = searchObj?.query || '';
  const isAccLot = isAccessoryLot(lot, searchQ);

  const market = getLotMarket(lot);
  const profitAbs = getLotProfitAbs(lot);
  const profitPct = getLotProfitPct(lot);
  const buyPrice = getLotBuyPrice(lot);
  const isDeal = profitAbs > 0 && !defectInfo.isDefect && !exchangeInfo;
  const isHot = isDeal && Math.abs(profitPct) >= 15 && !isAccLot && !lot.isComboListing;
  if (isHot) card.classList.add('is-hot');

  const locked = isLotLocked(lot);
  const isFav = State.favorites.includes(String(lot.id));

  // Media
  const photoUrl = (lot.images && lot.images.length > 0) ? lot.images[0] : '';
  const mediaHtml = photoUrl ? `
    <div class="lot-media">
      <img src="${escapeHtml(photoUrl)}" alt="${escapeHtml(lot.title)}" loading="lazy">
      <button class="fav-btn ${isFav ? 'active' : ''}" aria-pressed="${isFav}" onclick="window.app.toggleFav(event, '${jsArg(lot.id)}')" title="В избранное">
        <svg class="sl-like__heart" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
          <path class="sl-like__outline" d="M12 20S3 14.5 3 8.5a4.6 4.6 0 0 1 9-1.4 4.6 4.6 0 0 1 9 1.4C21 14.5 12 20 12 20Z"/>
          <path class="sl-like__fill" d="M12 20S3 14.5 3 8.5a4.6 4.6 0 0 1 9-1.4 4.6 4.6 0 0 1 9 1.4C21 14.5 12 20 12 20Z"/>
        </svg>
      </button>
    </div>
  ` : '';

  // Status badges
  let statusBadge = '';
  if (defectInfo.isDefect) {
    statusBadge = `<span class="badge-soft is-danger">${escapeHtml(defectInfo.label)}</span>`;
  } else if (exchangeInfo) {
    statusBadge = `<span class="badge-soft is-warn">Обмен</span>`;
  } else if (lot.isComboListing || lot.isInDescOrList) {
    statusBadge = `<span class="badge-soft is-warn">Сборный лот</span>`;
  }
  const dealBadge = isDeal ? buildDealBadgeHtml(lot, profitAbs, profitPct) : '';
  const priceDropBadge = buildPriceDropHtml(lot);
  const sellerScoreBadge = buildSellerScoreHtml(lot);
  const repostTag = lot.is_repost === true ? '<span class="badge-repost">Повтор</span>' : '';

  // Market line
  let marketLine = '';
  if (market > 0) {
    marketLine = `Рынок: <b>${fmtPrice(market)} ₽</b>`;
    if (buyPrice > 0) marketLine += ` · Выкуп до: <b>${fmtPrice(buyPrice)} ₽</b>`;
  }

  const variantText = formatVariantBadge(lot.variant);
  const sellerName = lot.seller?.name || 'Частник';
  const sellerLoc = lot.seller?.location || searchObj?.city || '';
  const timeText = lot.publishedText || timeAgo(lot.postedAt) || '';

  const vanishHtml = lot.isDismissed
    ? `<button class="vanish-btn" onclick="window.app.restoreLot(event, '${jsArg(lot.id)}')" title="Вернуть" style="color: var(--accent);">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>
      </button>`
    : `<button class="vanish-btn" onclick="window.app.vanishLot(event, '${jsArg(lot.id)}')" title="Скрыть">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>`;

  card.innerHTML = `
    ${mediaHtml}
    <div class="lot-body">
      <div class="lot-badge-row">
        ${dealBadge}
        ${priceDropBadge}
        ${statusBadge}
        ${repostTag}
        <span style="flex: 1;"></span>
        ${vanishHtml}
      </div>
      <h3 class="lot-title">${escapeHtml(lot.title)}</h3>
      ${variantText ? `<div class="caption-dim" style="margin-bottom: 6px;">${escapeHtml(variantText)}</div>` : ''}
      <div class="lot-price mono">${fmtPrice(lot.price)} ₽${lot.realPriceInDesc ? ` <span class="lot-price-note">в описании ${fmtPrice(lot.realPriceInDesc)} ₽</span>` : ''}</div>
      ${marketLine ? `<div class="lot-market">${marketLine}</div>` : ''}
      ${buildMarketAnalogsHtml(lot) ? `<div class="market-analogs-row">${buildMarketAnalogsHtml(lot)}</div>` : ''}
      <div class="lot-meta">
        <span>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          ${escapeHtml(sellerName)}
        </span>
        ${sellerScoreBadge}
        ${sellerLoc ? `<span>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          ${escapeHtml(sellerLoc)}
        </span>` : ''}
        ${timeText ? `<span class="mono">${escapeHtml(timeText)}</span>` : ''}
        ${buildDistanceBadgeHtml(lot)}
      </div>
      <div class="lot-actions">
        <button class="btn btn-primary-outline" onclick="window.app.openAvito(event, '${jsArg(lot.avitoUrl || '')}')">
          <span>Открыть на Авито</span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </button>
        <button class="btn btn-ghost" onclick="window.app.copyTradeTemplate(event, '${jsArg(lot.id)}')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
          <span>Торг</span>
        </button>
      </div>
    </div>
    ${locked ? `
      <div class="lot-lock" onclick="window.app.switchTab('pro')">
        <span class="lot-lock-badge">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Мгновенные уведомления в PRO
        </span>
        <span class="lot-lock-text">Свежий лот младше 15 минут. Free-тариф показывает его с задержкой.</span>
      </div>
    ` : ''}
  `;

  if (!locked) {
    card.addEventListener('click', (e) => {
      if (e.target.closest('button') || e.target.closest('a')) return;
      openLotModal(lot);
    });
    attachSwipeToCard(card, lot);
  }

  return card;
}

// Swipe-left to vanish (same mechanics as the legacy build)
function attachSwipeToCard(card, lot) {
  // Desktop without a touchscreen: no swipe gestures, keep mouse wheel untouched.
  const hasTouch = 'ontouchstart' in window || (navigator.maxTouchPoints || 0) > 0;
  if (document.body.classList.contains('platform-desktop') && !hasTouch) return;

  let startX = 0;
  let startY = 0;
  let currentX = 0;
  let isSwiping = false;
  let isHorizontal = null;

  card.addEventListener('touchstart', (e) => {
    if (e.target.closest('button') || e.target.closest('a')) return;
    const touch = e.touches[0];
    startX = touch.clientX;
    startY = touch.clientY;
    currentX = startX;
    isSwiping = true;
    isHorizontal = null;
    card.style.transition = 'none';
  }, { passive: true });

  card.addEventListener('touchmove', (e) => {
    if (!isSwiping) return;
    const touch = e.touches[0];
    currentX = touch.clientX;
    const diffX = currentX - startX;
    const diffY = touch.clientY - startY;

    if (isHorizontal === null) {
      if (Math.abs(diffX) > 8 || Math.abs(diffY) > 8) {
        isHorizontal = Math.abs(diffX) > Math.abs(diffY);
      }
    }
    if (!isHorizontal) return;

    if (diffX < 0) {
      if (e.cancelable) e.preventDefault();
      card.style.transform = `translateX(${diffX}px)`;
      card.style.opacity = String(Math.max(0.3, 1 - Math.abs(diffX) / 280));
      if (diffX < -80 && !card.dataset.hapticFired) {
        TelegramService.haptic('light');
        card.dataset.hapticFired = 'true';
      } else if (diffX >= -80 && card.dataset.hapticFired) {
        delete card.dataset.hapticFired;
      }
    } else {
      card.style.transform = 'translateX(0)';
      card.style.opacity = '1';
    }
  }, { passive: false });

  const endSwipe = () => {
    if (!isSwiping) return;
    isSwiping = false;
    delete card.dataset.hapticFired;
    const diffX = currentX - startX;
    if (isHorizontal && diffX < -80) {
      TelegramService.haptic('warning');
      card.classList.add('vanished-swipe');
      setTimeout(() => vanishLot(null, lot.id), 240);
    } else {
      card.style.transition = 'transform 220ms cubic-bezier(0.16, 1, 0.3, 1), opacity 220ms ease';
      card.style.transform = 'translateX(0)';
      card.style.opacity = '1';
    }
    isHorizontal = null;
  };

  card.addEventListener('touchend', endSwipe);
  card.addEventListener('touchcancel', endSwipe);
}

// ==========================================================================
// 32. Lot actions: fav, vanish, details, trade template
// ==========================================================================
function toggleFav(event, lotId) {
  if (event) event.stopPropagation();
  TelegramService.haptic('light');
  const strId = String(lotId);
  const idx = State.favorites.indexOf(strId);
  const nowFav = idx === -1;
  if (nowFav) State.favorites.push(strId);
  else State.favorites.splice(idx, 1);
  SafeStorage.setItem(getUserStorageKey('favorites'), JSON.stringify(State.favorites));
  renderFeed();
  const heart = document.querySelector(`.lot-card[data-id="${CSS.escape(strId)}"] .fav-btn .sl-like__heart`);
  SLUI.pulseLikeHeart(heart, nowFav);
}

async function vanishLot(event, lotId) {
  if (event) event.stopPropagation();
  TelegramService.haptic('warning');
  const card = document.querySelector(`.lot-card[data-id="${CSS.escape(String(lotId))}"]`);
  if (card && !card.classList.contains('vanished-swipe')) {
    card.classList.add('vanishing');
    setTimeout(() => applyVanish(lotId), 250);
  } else {
    applyVanish(lotId);
  }
}

function applyVanish(lotId) {
  const lot = State.lots.find(l => String(l.id) === String(lotId));
  if (lot) lot.isDismissed = true;
  ApiService.dismissLot(lotId);
  renderFeed();
  showToast('Объявление скрыто', 'info');
}

async function restoreLot(event, lotId) {
  if (event) event.stopPropagation();
  TelegramService.haptic('success');
  const lot = State.lots.find(l => String(l.id) === String(lotId));
  if (lot) lot.isDismissed = false;
  await ApiService.restoreLot(lotId);
  renderFeed();
  showToast('Объявление возвращено в ленту', 'success');
}

function openAvito(event, url) {
  if (event) event.stopPropagation();
  if (!url) return;
  TelegramService.openLink(url);
}

async function copyTradeTemplate(event, lotId) {
  if (event) event.stopPropagation();
  const lot = State.lots.find(l => String(l.id) === String(lotId));
  if (!lot) return;
  const buy = getLotBuyPrice(lot);
  const target = buy > 0 ? buy : (lot.price || 0);
  const text = `Здравствуйте! Интересует «${lot.title}». Готов забрать сегодня и оплатить сразу. Рассмотрите ${fmtPrice(target)} ₽?`;
  const ok = await copyTextToClipboard(text);
  if (ok) {
    TelegramService.haptic('success');
    showToast('Шаблон скопирован', 'success');
  } else {
    TelegramService.haptic('error');
    showToast('Не удалось скопировать', 'error');
  }
}

function openLotModal(lot) {
  TelegramService.haptic('medium');
  State.modalLot = lot;

  const market = getLotMarket(lot);
  const profitAbs = getLotProfitAbs(lot);
  const profitPct = getLotProfitPct(lot);
  const buyPrice = getLotBuyPrice(lot);

  const set = (id, val) => { const el = $(id); if (el) el.textContent = val; };

  set('modalTitle', lot.title || '');
  set('modalPrice', `${fmtPrice(lot.price)} ₽`);
  set('modalDescription', lot.description || 'Описание отсутствует.');
  set('modalSellerNameText', lot.seller?.name || 'Частник');
  set('modalSellerType', lot.seller?.type === 'private' ? 'Частное лицо' : 'Компания / Магазин');
  set('modalLocation', lot.seller?.location || '');
  set('modalDate', lot.publishedText || timeAgo(lot.postedAt) || '');

  const mDrop = $('modalPriceDrop');
  if (mDrop) mDrop.innerHTML = buildPriceDropHtml(lot);

  const mAnalogs = $('modalMarketAnalogs');
  if (mAnalogs) mAnalogs.innerHTML = buildMarketAnalogsHtml(lot);

  const mScore = $('modalSellerScore');
  if (mScore) {
    const scoreHtml = buildSellerScoreHtml(lot);
    mScore.innerHTML = scoreHtml;
    mScore.style.display = scoreHtml ? 'inline-flex' : 'none';
  }

  const mDist = $('modalDistance');
  if (mDist) {
    const km = getLotDistanceKm(lot);
    mDist.textContent = km === null ? '' : `${formatDistanceKm(km)} от вас`;
  }

  const mMarket = $('modalMarketPrice');
  if (mMarket) {
    if (market > 0) {
      mMarket.innerHTML = `Рынок: <b>${fmtPrice(market)} ₽</b>` + (buyPrice > 0 ? ` · Выкуп до: <b>${fmtPrice(buyPrice)} ₽</b>` : '');
    } else {
      mMarket.textContent = '';
    }
  }

  const mDeal = $('modalDealBadge');
  if (mDeal) mDeal.innerHTML = buildDealBadgeHtml(lot, profitAbs, profitPct);

  const ratingEl = $('modalSellerRating');
  const ratingVal = $('modalSellerRatingVal');
  if (ratingEl && ratingVal) {
    if (lot.seller?.rating) {
      ratingVal.textContent = lot.seller.rating;
      ratingEl.style.display = 'inline-flex';
    } else {
      ratingEl.style.display = 'none';
    }
  }

  const imgEl = $('modalMainImg');
  if (imgEl) {
    if (lot.images && lot.images.length > 0) {
      imgEl.src = lot.images[0];
      imgEl.style.display = 'block';
    } else {
      imgEl.style.display = 'none';
    }
  }

  const tagsContainer = $('modalTags');
  if (tagsContainer) {
    tagsContainer.innerHTML = (lot.tags || []).slice(0, 5)
      .map(t => `<span class="badge-soft">${escapeHtml(t)}</span>`).join('');
  }

  const ctaBtn = $('modalAvitoCta');
  if (ctaBtn) ctaBtn.onclick = () => TelegramService.openLink(lot.avitoUrl);

  const tradeBtn = $('modalTradeBtn');
  if (tradeBtn) tradeBtn.onclick = (e) => copyTradeTemplate(e, lot.id);

  openSheet('sheetLot');
}

// ==========================================================================
// 33. PRO tab: plan, trial, payments, referral
// ==========================================================================
let proCountdownTimer = null;

function renderPro() {
  const box = $('proContent');
  if (!box) return;

  const u = State.user;
  const pro = isPro();
  const { used, limit } = getRadarsUsage();
  const aUsed = u ? u.analysis_used_today : 0;
  const aLimit = u ? u.analysis_limit : 3;

  const priceMonth = u ? u.stars_price_month : 299;
  const priceYear = u ? u.stars_price_year : 1999;

  const planHero = pro ? `
    <div class="plan-hero is-pro">
      <div class="plan-hero-top">
        <div class="plan-name">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFCC00" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M11.6 3.3a.5.5 0 0 1 .8 0l2.9 5.5a1 1 0 0 0 1.5.3l4.3-3.6a.5.5 0 0 1 .8.5L19 16.2a1 1 0 0 1-1 .8H6a1 1 0 0 1-1-.8L2.1 6a.5.5 0 0 1 .8-.5l4.3 3.6a1 1 0 0 0 1.5-.3z"/><path d="M5 21h14"/></svg>
          <span class="pro-mark">PRO</span>
        </div>
        <span id="proCountdown" class="plan-countdown">${u && u.pro_expires_at ? formatCountdown(u.pro_expires_at) : 'активен'}</span>
      </div>
      <p class="caption" style="line-height: 1.5;">До 15 радаров, мгновенные уведомления без задержки и безлимитные оценки рынка.</p>
    </div>
  ` : `
    <div class="plan-hero">
      <div class="plan-hero-top">
        <div class="plan-name">Free</div>
        <span class="plan-badge">ТЕКУЩИЙ ТАРИФ</span>
      </div>
      <p class="caption" style="line-height: 1.55; margin-bottom: 14px;">1 радар, лоты с задержкой 15 минут, ${aLimit} оценки рынка в сутки.</p>
      <div class="feature-row"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>PRO: до 15 радаров одновременно</div>
      <div class="feature-row"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>Мгновенные уведомления без задержки</div>
      <div class="feature-row"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>Безлимитная оценка рынка</div>
    </div>
  `;

  const trialBlock = (!pro && u && u.trial_available) ? `
    <button class="btn btn-ghost" style="border-color: var(--accent-border); color: var(--accent);" onclick="window.app.startTrial()">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <span>Пробный PRO на 24 часа</span>
    </button>
  ` : '';

  const tariffs = !pro ? `
    <div class="tariff-card">
      <div>
        <div class="tariff-name">PRO · 30 дней</div>
        <div class="caption-dim">полный доступ на месяц</div>
      </div>
      <div style="text-align: right;">
        <div class="tariff-price">${priceMonth} <small>STARS</small></div>
        <button class="btn btn-accent btn-sm" style="margin-top: 8px; width: auto;" onclick="window.app.payWithStars('pro_month')">Купить</button>
      </div>
    </div>
    <div class="tariff-card is-best">
      <span class="tariff-best-tag">ВЫГОДНЕЕ</span>
      <div>
        <div class="tariff-name">PRO · 12 месяцев</div>
        <div class="caption-dim">2 месяца в подарок</div>
      </div>
      <div style="text-align: right;">
        <div class="tariff-price">${priceYear} <small>STARS</small></div>
        <button class="btn btn-accent btn-sm" style="margin-top: 8px; width: auto;" onclick="window.app.payWithStars('pro_year')">Купить</button>
      </div>
    </div>
    ${State.yookassaUnavailable ? '' : `
      <button class="btn btn-ghost" onclick="window.app.payWithCard('pro_month')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
        <span>Оплатить картой / СБП</span>
      </button>
    `}
  ` : '';

  const referralUrl = u ? u.referral_url : '';
  const referralBlock = referralUrl ? `
    <div class="referral-box">
      <div class="h3" style="font-size: 14px; margin-bottom: 4px;">Пригласите друга</div>
      <p class="caption" style="line-height: 1.5;">+3 дня PRO за каждого друга, который запустит бота по вашей ссылке.</p>
      <div class="referral-url">${escapeHtml(referralUrl)}</div>
      <div class="btn-row">
        <button class="btn btn-accent btn-sm" onclick="window.app.shareReferral()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          <span>Пригласить друга</span>
        </button>
        <button class="btn btn-ghost btn-sm" onclick="window.app.copyReferral()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
          <span>Копировать</span>
        </button>
      </div>
    </div>
  ` : '';

  const quiet = State.user ? State.user.quiet_hours : normalizeQuietHours(null);
  const quietOptions = (selected) => {
    let opts = '';
    for (let h = 0; h <= 23; h++) {
      opts += `<option value="${h}" ${h === selected ? 'selected' : ''}>${String(h).padStart(2, '0')}:00</option>`;
    }
    return opts;
  };
  const quietBlock = `
    <div class="card" id="quietHoursCard">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px;">
        <div class="caption-dim" style="text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;">Тихие часы</div>
        <label class="switch">
          <input type="checkbox" id="quietSwitch" ${quiet.enabled ? 'checked' : ''} onchange="window.app.onQuietChange()">
          <span class="switch-track"></span>
          <span class="switch-thumb"></span>
        </label>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
        <span class="caption">с</span>
        <select id="quietStart" class="select mono" style="flex: 1; height: 34px; font-size: 12px;" onchange="window.app.onQuietChange()">${quietOptions(quiet.start)}</select>
        <span class="caption">до</span>
        <select id="quietEnd" class="select mono" style="flex: 1; height: 34px; font-size: 12px;" onchange="window.app.onQuietChange()">${quietOptions(quiet.end)}</select>
      </div>
      <p class="caption" style="line-height: 1.5;">В это время бот не будет будить вас уведомлениями - находки придут после окончания тихих часов.</p>
    </div>
  `;

  const hasAddress = Boolean(u && u.home_address);
  const addressBlock = `
    <div class="card" id="addressCard">
      <div class="caption-dim" style="text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; margin-bottom: 10px;">Мой адрес</div>
      ${hasAddress && !State.editingAddress ? `
        <div class="address-row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#FFCC00" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="flex: 0 0 auto;"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          <span class="address-text">${escapeHtml(u.home_address)}</span>
          <button class="address-clear-btn" onclick="window.app.clearAddress()" title="Удалить адрес">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <p class="caption" style="line-height: 1.5; margin-bottom: 12px;">В карточках и уведомлениях отображается расстояние до объявления.</p>
        <button class="btn btn-ghost btn-sm" onclick="window.app.editAddress()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"/></svg>
          <span>Изменить</span>
        </button>
      ` : `
        ${hasAddress ? '' : `<p class="caption" style="line-height: 1.5; margin-bottom: 10px;">Укажите адрес - в карточках и уведомлениях появится расстояние до объявления.</p>`}
        <div class="input-icon-wrap" style="margin-bottom: 8px;">
          <span class="input-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          </span>
          <input type="text" id="addressInput" class="input" placeholder="Город, улица, дом" autocomplete="off" enterkeyhint="done" style="padding-right: 44px;" value="${escapeHtml(hasAddress ? u.home_address : '')}">
          <button type="button" class="address-locate-btn" id="btnDetectAddress" title="Определить автоматически" aria-label="Определить адрес автоматически" onclick="window.app.detectAddress()">
            <svg id="detectAddressIcon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="7"/><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/><line x1="1" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="23" y2="12"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/></svg>
          </button>
          <div id="addressSuggest" class="address-suggest hidden"></div>
        </div>
        <div id="addressError" class="address-error ${State.addressError ? '' : 'hidden'}">${escapeHtml(State.addressError)}</div>
        <button class="btn btn-accent btn-sm" id="btnSaveAddress" ${State.addressSaving ? 'disabled' : ''} onclick="window.app.saveAddress()">
          <span>Сохранить</span>
        </button>
      `}
    </div>
  `;

  box.innerHTML = `
    ${planHero}
    ${quietBlock}
    ${addressBlock}
    <div class="stat-mini-grid">
      <div class="stat-mini">
        <div class="caption-dim">Радары</div>
        <div class="mono">${used} / ${limit}</div>
      </div>
      <div class="stat-mini">
        <div class="caption-dim">Оценки сегодня</div>
        <div class="mono">${pro ? 'безлимит' : `${aUsed} / ${aLimit}`}</div>
      </div>
    </div>
    ${trialBlock}
    ${tariffs}
    ${referralBlock}
  `;

  if (proCountdownTimer) clearInterval(proCountdownTimer);
  if (pro && u && u.pro_expires_at) {
    proCountdownTimer = setInterval(() => {
      const el = $('proCountdown');
      if (!el) {
        clearInterval(proCountdownTimer);
        return;
      }
      el.textContent = formatCountdown(u.pro_expires_at);
    }, 30000);
  }

  initAddressSuggest();
}

// ==========================================================================
// 33a. Address autocomplete (GET /api/address/suggest)
// ==========================================================================
const AddressSuggest = {
  items: [],
  active: -1,
  timer: null,
  reqId: 0,

  render(items) {
    const list = $('addressSuggest');
    if (!list) return;
    this.items = items;
    this.active = -1;
    list.innerHTML = '';

    if (items.length === 0) {
      list.innerHTML = '<div class="address-suggest-empty">Ничего не найдено - уточните улицу и город</div>';
      list.classList.remove('hidden');
      return;
    }

    items.forEach((s, i) => {
      const short = String(s.short || '').trim();
      const full = String(s.display_name || '').trim();
      const item = document.createElement('div');
      item.className = 'address-suggest-item';
      item.dataset.idx = String(i);
      item.innerHTML = `
        <svg class="address-suggest-pin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
        <div class="address-suggest-text">
          <div class="address-suggest-short">${escapeHtml(short || full)}</div>
          ${full && full !== short ? `<div class="address-suggest-full">${escapeHtml(full)}</div>` : ''}
        </div>
      `;
      item.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        this.select(i);
      });
      list.appendChild(item);
    });
    list.classList.remove('hidden');
  },

  close() {
    const list = $('addressSuggest');
    if (list) {
      list.classList.add('hidden');
      list.innerHTML = '';
    }
    this.items = [];
    this.active = -1;
  },

  highlight() {
    const list = $('addressSuggest');
    if (!list) return;
    list.querySelectorAll('.address-suggest-item').forEach(el => {
      el.classList.toggle('active', Number(el.dataset.idx) === this.active);
    });
    const activeEl = list.querySelector('.address-suggest-item.active');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
  },

  async query(q) {
    if (q.trim().length < 3) {
      this.close();
      return;
    }
    const reqId = ++this.reqId;
    const res = await ApiService.suggestAddress(q.trim());
    if (reqId !== this.reqId) return;
    if (res === null) {
      this.close();
      return;
    }
    this.render(res.slice(0, 5));
  },

  select(i) {
    const s = this.items[i];
    const input = $('addressInput');
    if (!s || !input) return;
    input.value = String(s.display_name || s.short || '');
    this.close();
    saveAddress({ lat: s.lat, lon: s.lon, display_name: s.display_name });
  }
};

let addressSuggestDocBound = false;

function initAddressSuggest() {
  const input = $('addressInput');
  if (!input || input.dataset.suggestBound === '1') return;
  input.dataset.suggestBound = '1';

  input.addEventListener('input', () => {
    if (AddressSuggest.timer) clearTimeout(AddressSuggest.timer);
    AddressSuggest.timer = setTimeout(() => {
      AddressSuggest.query(input.value).catch(() => AddressSuggest.close());
    }, 350);
  });

  input.addEventListener('keydown', (e) => {
    const list = $('addressSuggest');
    const isOpen = list && !list.classList.contains('hidden') && AddressSuggest.items.length > 0;
    if (!isOpen) {
      if (e.key === 'Enter') {
        e.preventDefault();
        saveAddress();
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      AddressSuggest.active = (AddressSuggest.active + 1) % AddressSuggest.items.length;
      AddressSuggest.highlight();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      AddressSuggest.active = (AddressSuggest.active <= 0) ? AddressSuggest.items.length - 1 : AddressSuggest.active - 1;
      AddressSuggest.highlight();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const idx = AddressSuggest.active >= 0 ? AddressSuggest.active : 0;
      AddressSuggest.select(idx);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      AddressSuggest.close();
    }
  });

  input.addEventListener('blur', () => {
    setTimeout(() => {
      const list = $('addressSuggest');
      if (list && list.contains(document.activeElement)) return;
      AddressSuggest.close();
    }, 120);
  });

  if (!addressSuggestDocBound) {
    addressSuggestDocBound = true;
    document.addEventListener('pointerdown', (e) => {
      const list = $('addressSuggest');
      const inp = $('addressInput');
      if (!list || list.classList.contains('hidden')) return;
      if (!list.contains(e.target) && e.target !== inp) AddressSuggest.close();
    });
  }
}

async function saveAddress(selected, silent) {
  const input = $('addressInput');
  if (!input || State.addressSaving) return;

  let payload;
  if (selected && typeof selected === 'object') {
    payload = { lat: selected.lat, lon: selected.lon, display_name: selected.display_name };
  } else {
    const value = (input.value || '').trim();
    if (!value) {
      State.addressError = 'Введите адрес';
      const errEl = $('addressError');
      if (errEl) {
        errEl.textContent = State.addressError;
        errEl.classList.remove('hidden');
      }
      TelegramService.haptic('error');
      return;
    }
    payload = value;
  }

  State.addressSaving = true;
  const btn = $('btnSaveAddress');
  if (btn) btn.disabled = true;

  const r = await ApiService.setAddress(payload);

  State.addressSaving = false;
  if (btn) btn.disabled = false;

  if (r && r.ok) {
    State.addressError = '';
    State.editingAddress = false;
    if (!State.user) State.user = normalizeUser(null);
    State.user.home_address = r.display_name || (typeof payload === 'object' ? payload.display_name : payload);
    AddressSuggest.close();
    TelegramService.haptic('success');
    showToast(silent ? 'Адрес определен автоматически' : 'Адрес сохранен', 'success');
    renderPro();
  } else {
    State.addressError = (r && r.message) || 'Сервер недоступен';
    const errEl = $('addressError');
    if (errEl) {
      errEl.textContent = State.addressError;
      errEl.classList.remove('hidden');
    }
    TelegramService.haptic('error');
    if (r && r.offline) showToast('Сервер недоступен', 'error');
    input.focus();
  }
}

async function clearAddress() {
  if (State.addressSaving) return;
  State.addressSaving = true;
  const r = await ApiService.setAddress('');
  State.addressSaving = false;
  if (r && r.ok) {
    State.editingAddress = false;
    State.addressError = '';
    if (State.user) State.user.home_address = null;
    TelegramService.haptic('light');
    showToast('Адрес удален', 'info');
    renderPro();
  } else {
    TelegramService.haptic('error');
    showToast('Сервер недоступен', 'error');
  }
}

function editAddress() {
  TelegramService.haptic('light');
  State.editingAddress = true;
  State.addressError = '';
  renderPro();
  $('addressInput')?.focus();
}

function setDetectAddressLoading(loading) {
  const btn = $('btnDetectAddress');
  const icon = $('detectAddressIcon');
  if (!btn) return;
  btn.disabled = loading;
  btn.classList.toggle('is-loading', loading);
  if (icon) icon.classList.toggle('rotating', loading);
}

function getTelegramLocation() {
  return new Promise((resolve) => {
    const tg = window.Telegram?.WebApp;
    const lm = tg?.LocationManager;
    if (!tg || !lm || typeof lm.getLocation !== 'function') return resolve(null);
    let settled = false;
    const done = (res) => { if (!settled) { settled = true; resolve(res); } };
    const timer = setTimeout(() => done(null), 10000);
    try {
      if (typeof lm.init === 'function') {
        try { lm.init(); } catch (_) {}
      }
      lm.getLocation((res) => {
        clearTimeout(timer);
        if (!res) return done(null);
        const lat = Number(res.latitude ?? res.lat);
        const lon = Number(res.longitude ?? res.lon);
        done(Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null);
      });
    } catch (_) {
      clearTimeout(timer);
      done(null);
    }
  });
}

function getBrowserLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation?.getCurrentPosition) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  });
}

async function detectAddress() {
  if (State.addressSaving) return;
  TelegramService.haptic('light');
  setDetectAddressLoading(true);

  try {
    let coords = await getTelegramLocation();
    let denied = false;
    if (!coords) {
      const browser = await getBrowserLocation();
      if (browser) {
        coords = browser;
      } else {
        denied = true;
      }
    }

    if (!coords) {
      TelegramService.haptic('error');
      showToast(denied
        ? 'Разрешите доступ к геолокации в настройках Telegram'
        : 'Не удалось определить адрес - введите вручную', 'error');
      return;
    }

    const rev = await ApiService.reverseAddress(coords.lat, coords.lon);
    if (!rev || !rev.display_name) {
      TelegramService.haptic('error');
      showToast('Не удалось определить адрес - введите вручную', 'error');
      return;
    }

    const input = $('addressInput');
    if (input) input.value = rev.display_name;
    await saveAddress({ lat: rev.lat, lon: rev.lon, display_name: rev.display_name }, true);
  } finally {
    setDetectAddressLoading(false);
  }
}

function goToAddress() {
  TelegramService.haptic('light');
  if (!State.user || !State.user.home_address) State.editingAddress = true;
  switchTab('pro');
  setTimeout(() => $('addressInput')?.focus(), 80);
}

function dismissAddressHint() {
  TelegramService.haptic('light');
  $('feedAddressHint')?.classList.add('hidden');
}

async function onQuietChange() {
  if (State.quietSaving) return;
  const sw = $('quietSwitch');
  const startSel = $('quietStart');
  const endSel = $('quietEnd');
  if (!sw || !startSel || !endSel) return;
  TelegramService.haptic('selection');

  const enabled = sw.checked;
  const start = Math.max(0, Math.min(23, Math.round(Number(startSel.value))));
  const end = Math.max(0, Math.min(23, Math.round(Number(endSel.value))));

  State.quietSaving = true;
  const r = await ApiService.setQuietHours(enabled, start, end);
  State.quietSaving = false;

  if (!State.user) State.user = normalizeUser(null);
  State.user.quiet_hours = { enabled, start, end };

  if (r && r.ok) {
    TelegramService.haptic('success');
    showToast('Тихие часы обновлены', 'success');
  } else {
    showToast((r && r.message) || 'Сервер недоступен', 'error');
  }
}

function exportLotsCsv() {
  TelegramService.haptic('medium');
  if (!isPro()) {
    TelegramService.haptic('warning');
    showToast('Экспорт доступен в PRO', 'info');
    switchTab('pro');
    return;
  }
  const uid = getCurrentUserId();
  const url = `${API_BASE_URL}/api/export/lots.csv?user_id=${encodeURIComponent(uid)}`;
  if (tg?.openLink) TelegramService.openLink(url);
  else window.open(url, '_blank', 'noopener,noreferrer');
}

async function startTrial() {
  TelegramService.haptic('medium');
  const r = await ApiService.activateTrial();
  if (r && (r.ok || r.pro_expires_at)) {
    if (!State.user) State.user = normalizeUser(null);
    State.user.plan = 'pro';
    State.user.pro_expires_at = r.pro_expires_at || State.user.pro_expires_at;
    State.user.trial_available = false;
    State.user.radars_limit = 15;
    TelegramService.haptic('success');
    showToast('Пробный PRO активирован на 24 часа', 'success');
  } else {
    TelegramService.haptic('error');
    showToast('Пробный период недоступен', 'error');
  }
  renderHeader();
  renderPro();
}

async function payWithStars(planId) {
  TelegramService.haptic('medium');
  const r = await ApiService.payStars(planId);
  if (!r || !r.invoice_link) {
    TelegramService.haptic('error');
    showToast('Не удалось создать счет на оплату', 'error');
    return;
  }

  const opened = TelegramService.openInvoice(r.invoice_link, async (status) => {
    if (status === 'paid') {
      TelegramService.haptic('success');
      showToast('Оплата прошла - PRO активирован', 'success');
      await refreshUser();
      renderPro();
      renderRadars();
    } else if (status === 'cancelled') {
      showToast('Оплата отменена', 'info');
    } else if (status === 'failed') {
      TelegramService.haptic('error');
      showToast('Оплата не прошла', 'error');
    }
  });

  if (!opened) TelegramService.openLink(r.invoice_link);
}

async function payWithCard(planId) {
  TelegramService.haptic('medium');
  const r = await ApiService.payYookassa(planId);
  if (r && r.notAvailable) {
    State.yookassaUnavailable = true;
    renderPro();
    showToast('Оплата картой временно недоступна', 'info');
    return;
  }
  if (r && r.payment_url) {
    TelegramService.openLink(r.payment_url);
    showToast('После оплаты PRO активируется автоматически', 'info');
    setTimeout(refreshUser, 15000);
    return;
  }
  TelegramService.haptic('error');
  showToast('Не удалось создать платеж', 'error');
}

function shareReferral() {
  const u = State.user;
  if (!u || !u.referral_url) return;
  TelegramService.haptic('medium');
  const text = 'AvitoRadar ловит объявления ниже рынка на Авито. Залетай по моей ссылке:';
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(u.referral_url)}&text=${encodeURIComponent(text)}`;
  TelegramService.openTelegramLink(shareUrl);
}

async function copyReferral() {
  const u = State.user;
  if (!u || !u.referral_url) return;
  const ok = await copyTextToClipboard(u.referral_url);
  if (ok) {
    TelegramService.haptic('success');
    showToast('Ссылка скопирована', 'success');
  } else {
    showToast('Не удалось скопировать', 'error');
  }
}

// ==========================================================================
// 34. Refresh
// ==========================================================================
async function refreshAll() {
  await loadData();
  if (!ApiService.networkFailed) showToast('Данные синхронизированы', 'success');
}

// ==========================================================================
// 35. Event listeners & bootstrap
// ==========================================================================
function setupEventListeners() {
  $('btnRefresh')?.addEventListener('click', async () => {
    const btn = $('btnRefresh');
    if (!btn || btn.disabled) return;
    TelegramService.haptic('medium');
    btn.disabled = true;
    const svg = btn.querySelector('svg');
    if (svg) svg.classList.add('rotating');
    try {
      if (State.activeTab === 'feed' && State.currentSearchId && State.currentSearchId !== 'all') {
        await scanSearch(State.currentSearchId);
      } else {
        showToast('Синхронизация с сервером...', 'info');
        await refreshAll();
      }
    } finally {
      btn.disabled = false;
      if (svg) svg.classList.remove('rotating');
    }
  });

  $('formNewSearch')?.addEventListener('submit', handleNewSearchSubmit);
  $('btnConfirmDelete')?.addEventListener('click', handleConfirmDelete);
  $('formAnalysis')?.addEventListener('submit', submitAnalysis);
  $('analysisQuery')?.addEventListener('input', syncMainButton);

  $('feedSearchSelect')?.addEventListener('change', (e) => {
    TelegramService.haptic('light');
    State.currentSearchId = e.target.value || 'all';
    renderFeed();
  });

  $('feedSortSelect')?.addEventListener('change', (e) => {
    TelegramService.haptic('light');
    State.sortMode = e.target.value;
    renderFeed();
  });

  $('feedFilterInput')?.addEventListener('input', (e) => {
    State.searchQuery = e.target.value.trim().toLowerCase();
    renderFeed();
  });

  // SL UI mounts: accessories toggle + min price slider in the create sheet
  const accToggleRoot = $('excludeAccessoriesToggle');
  if (accToggleRoot) {
    try {
      SLUI.mountToggle(accToggleRoot, { onChange: () => TelegramService.haptic('selection') });
    } catch (err) {
      console.warn('[SLUI] toggle mount failed:', err);
    }
  }

  const priceSliderRoot = document.querySelector('#sheetRadar .sl-slider');
  if (priceSliderRoot) {
    try {
      let lastSliderHaptic = 0;
      SLUI.mountSlider(priceSliderRoot, {
        formatValue: v => (v <= 0 ? 'без порога' : v.toLocaleString('ru-RU') + ' ₽'),
        onChange: () => {
          const now = Date.now();
          if (now - lastSliderHaptic > 200) {
            lastSliderHaptic = now;
            TelegramService.haptic('selection');
          }
        }
      });
    } catch (err) {
      console.warn('[SLUI] slider mount failed:', err);
    }
  }

  // Sheet drag-to-close
  SHEET_IDS.forEach(id => attachSheetDrag($(id)));

  // Smart autocomplete
  const newQueryInput = $('newQueryInput');
  const queryDropdown = $('querySuggestionsDropdown');
  if (newQueryInput && queryDropdown && window.Suggestions) {
    window.Suggestions.init(newQueryInput, queryDropdown, {
      limit: 7,
      onSelect: (item) => showToast(`Выбрано: ${item.title}`, 'info')
    });
  }

  const feedInput = $('feedFilterInput');
  const feedDropdown = $('feedFilterDropdown');
  if (feedInput && feedDropdown && window.Suggestions) {
    window.Suggestions.init(feedInput, feedDropdown, {
      limit: 6,
      onSelect: (item) => applyFeedFilter(item.query)
    });
  }

  // Telegram MainButton / BackButton
  if (tg) {
    try {
      if (tg.MainButton) {
        tg.MainButton.onClick(() => {
          if (State.activeTab === 'analysis' && !State.sheet) submitAnalysis();
        });
      }
      if (tg.BackButton) {
        tg.BackButton.onClick(() => {
          if (State.sheet) closeSheets();
          else if (State.activeTab !== 'radars') switchTab('radars');
        });
      }
    } catch (_) {}
  }
}

// ==========================================================================
// 36. window.app exports
// ==========================================================================
Object.assign(window.app, {
  switchTab,
  openRadarSheet,
  closeSheets,
  setQueryPreset,
  promptDelete,
  scanSearch,
  selectRadar,
  toggleRadarActive,
  vanishLot,
  restoreLot,
  toggleFav,
  openLotModal,
  openAvito,
  copyTradeTemplate,
  setFeedChip,
  applyFeedFilter,
  startTrial,
  payWithStars,
  payWithCard,
  shareReferral,
  copyReferral,
  saveAddress,
  clearAddress,
  editAddress,
  detectAddress,
  goToAddress,
  dismissAddressHint,
  onQuietChange,
  exportLotsCsv,
  refreshAll,
  toggleFullscreen: () => TelegramService.toggleFullscreen()
});

// ==========================================================================
// 37. Bootstrap
// ==========================================================================
async function startApp() {
  TelegramService.init();
  await SafeStorage.initCloudSync();
  setupEventListeners();
  renderHeader();
  await loadData();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startApp);
} else {
  startApp();
}
