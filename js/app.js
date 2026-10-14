/**
 * AvitoRadar — Unified Terminal Client
 * Standalone bundle with zero external module dependencies.
 * Works seamlessly in Telegram WebApp (iOS / Android / Desktop) and standalone browsers.
 */

// ==========================================================================
// 0. Immediate Global App Object (Ensures inline onclick never fails)
// ==========================================================================
window.app = window.app || {};

// ==========================================================================
// 1. Safe Storage Layer (Guards against iOS WebKit / iframe SecurityError)
// ==========================================================================
const SafeStorage = {
  _mem: new Map(),

  getItem(key) {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const val = window.localStorage.getItem(key);
        if (val !== null) return val;
      }
    } catch (_) {}
    return this._mem.get(key) || null;
  },

  setItem(key, val) {
    const strVal = String(val);
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, strVal);
      }
    } catch (_) {}
    this._mem.set(key, strVal);

    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.CloudStorage) {
        window.Telegram.WebApp.CloudStorage.setItem(key, strVal, () => {});
      }
    } catch (_) {}
  },

  removeItem(key) {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem(key);
      }
    } catch (_) {}
    this._mem.delete(key);

    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.CloudStorage) {
        window.Telegram.WebApp.CloudStorage.removeItem(key, () => {});
      }
    } catch (_) {}
  },

  async initCloudSync() {
    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.CloudStorage) {
        const searchKey = getUserStorageKey('searches');
        const favKey = getUserStorageKey('favorites');
        return new Promise((resolve) => {
          window.Telegram.WebApp.CloudStorage.getItems([searchKey, favKey], (err, values) => {
            if (!err && values) {
              if (values[searchKey] && !window.localStorage?.getItem(searchKey)) {
                SafeStorage.setItem(searchKey, values[searchKey]);
              }
              if (values[favKey] && !window.localStorage?.getItem(favKey)) {
                SafeStorage.setItem(favKey, values[favKey]);
              }
            }
            resolve();
          });
        });
      }
    } catch (_) {}
  }
};

// ==========================================================================
// 1.1 Multi-User Identity & Storage Key Scope
// ==========================================================================
function getCurrentUserId() {
  let uid = null;
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
    uid = String(window.Telegram.WebApp.initDataUnsafe.user.id).trim();
  }
  if (!uid) {
    try {
      if (typeof window !== 'undefined' && window.location) {
        const params = new URLSearchParams(window.location.search);
        const qUid = params.get('user_id');
        if (qUid && qUid.trim()) uid = qUid.trim();
      }
    } catch (_) {}
  }
  if (!uid) {
    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
        const params = new URLSearchParams(window.Telegram.WebApp.initData);
        const userStr = params.get('user');
        if (userStr) {
          const userObj = JSON.parse(userStr);
          if (userObj?.id) uid = String(userObj.id).trim();
        }
      }
    } catch (_) {}
  }
  if (!uid) {
    try {
      if (typeof window !== 'undefined' && window.location?.hash) {
        const hashParams = new URLSearchParams(window.location.hash.substring(1));
        const tgData = hashParams.get('tgWebAppData');
        if (tgData) {
          const parsed = new URLSearchParams(tgData);
          const userStr = parsed.get('user');
          if (userStr) {
            const userObj = JSON.parse(userStr);
            if (userObj?.id) uid = String(userObj.id).trim();
          }
        }
      }
    } catch (_) {}
  }

  if (uid) {
    SafeStorage.setItem('avitoradar_client_uid', uid);
    return uid;
  }

  let guestId = SafeStorage.getItem('avitoradar_client_uid');
  if (!guestId) {
    guestId = 'guest_' + Math.random().toString(36).substring(2, 10);
    SafeStorage.setItem('avitoradar_client_uid', guestId);
  }
  return guestId;
}

function getUserStorageKey(suffix) {
  const uid = getCurrentUserId();
  return `avitoradar_${suffix}_${uid}`;
}

function getApiHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const uid = getCurrentUserId();
  if (uid) headers['X-Telegram-User-Id'] = uid;
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
    headers['X-Telegram-Init-Data'] = window.Telegram.WebApp.initData;
  }
  return headers;
}

// ==========================================================================
// 2. City Abbreviation Mapping & Formatting Helpers
// ==========================================================================
const CITY_ABBR = {
  'челябинск': 'ЧЛБ',
  'chelyabinsk': 'ЧЛБ',
  'москва': 'МСК',
  'moskva': 'МСК',
  'санкт-петербург': 'СПБ',
  'sankt-peterburg': 'СПБ',
  'питер': 'СПБ',
  'екатеринбург': 'ЕКБ',
  'ekaterinburg': 'ЕКБ',
  'казань': 'КЗН',
  'kazan': 'КЗН',
  'новосибирск': 'НСК',
  'novosibirsk': 'НСК',
  'уфа': 'УФА',
  'ufa': 'УФА',
  'россия': 'РФ',
  'вся россия': 'РФ',
  'rossiya': 'РФ',
  'сочи': 'СОЧ',
  'sochi': 'СОЧ',
  'краснодар': 'КРД',
  'krasnodar': 'КРД',
  'тюмень': 'ТМН',
  'tyumen': 'ТМН',
  'самара': 'СМР',
  'samara': 'СМР',
  'нижний новгород': 'НН',
  'nizhniy_novgorod': 'НН',
  'пермь': 'ПРМ',
  'perm': 'ПРМ',
  'ростов-на-дону': 'РНД',
  'rostov': 'РНД',
  'волгоград': 'ВЛГ',
  'volgograd': 'ВЛГ',
  'воронеж': 'ВРЖ',
  'voronezh': 'ВРЖ',
  'омск': 'ОМС',
  'omsk': 'ОМС',
  'красноярск': 'КРС',
  'krasnoyarsk': 'КРС'
};

function getCityAbbr(cityName) {
  if (!cityName) return 'РФ';
  const key = String(cityName).trim().toLowerCase();
  if (CITY_ABBR[key]) return CITY_ABBR[key];
  for (const [k, abbr] of Object.entries(CITY_ABBR)) {
    if (key.includes(k) || k.includes(key)) return abbr;
  }
  return cityName.replace(/[^a-zA-Zа-яА-Я]/g, '').slice(0, 3).toUpperCase() || 'РФ';
}

function cleanQueryTitle(query) {
  if (!query) return '';
  let q = String(query).trim();
  const m = q.match(/«([^»]+)»/);
  if (m) {
    q = m[1];
  } else {
    q = q.replace(/:?\s*объявления\s+(для|в)\s+.*$/i, '')
         .replace(/объявления\s+в\s+.*$/i, '')
         .trim();
  }
  return q || String(query);
}

function formatSearchDisplay(search) {
  if (!search) return '';
  const abbr = getCityAbbr(search.city);
  const title = cleanQueryTitle(search.query || search.title || search.id);
  return `[${abbr}] ${title}`;
}

// ==========================================================================
// 3. Telegram WebApp Service
// ==========================================================================
const tg = window.Telegram?.WebApp;

const TelegramService = {
  init() {
    if (!tg) {
      console.log('[TelegramService] Running in web browser mode');
      return;
    }
    try {
      tg.ready();
      tg.expand();
      if (typeof tg.exitFullscreen === 'function') {
        try { tg.exitFullscreen(); } catch (_) {}
      }
      tg.headerColor = '#0E0F12';
      tg.backgroundColor = '#0E0F12';
      if (tg.isVerticalSwipesEnabled !== undefined) {
        tg.isVerticalSwipesEnabled = true;
      }

      const updateSafeAreas = () => {
        let top = 0;
        if (tg.safeAreaInset?.top) top = Math.max(top, tg.safeAreaInset.top);
        if (tg.contentSafeAreaInset?.top) top = Math.max(top, tg.contentSafeAreaInset.top);

        if (top > 0) {
          document.documentElement.style.setProperty('--safe-area-top', `${top}px`);
        } else {
          document.documentElement.style.setProperty('--safe-area-top', 'max(env(safe-area-inset-top, 0px), 24px)');
        }

        let bottom = 0;
        if (tg.safeAreaInset?.bottom) bottom = Math.max(bottom, tg.safeAreaInset.bottom);
        if (tg.contentSafeAreaInset?.bottom) bottom = Math.max(bottom, tg.contentSafeAreaInset.bottom);
        if (bottom > 0) {
          document.documentElement.style.setProperty('--safe-area-bottom', `${bottom}px`);
        }
      };

      updateSafeAreas();
      if (typeof tg.onEvent === 'function') {
        tg.onEvent('safeAreaChanged', updateSafeAreas);
        tg.onEvent('contentSafeAreaChanged', updateSafeAreas);
        tg.onEvent('viewportChanged', updateSafeAreas);
      }
    } catch (e) {
      console.warn('[TelegramService] Init warning:', e);
    }
  },

  haptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    try {
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
      else if (type === 'heavy') tg.HapticFeedback.impactOccurred('heavy');
      else if (type === 'selection') tg.HapticFeedback.selectionChanged();
      else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
      else if (type === 'warning') tg.HapticFeedback.notificationOccurred('warning');
      else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
    } catch (_) {}
  },

  openLink(url) {
    this.haptic('medium');
    if (tg?.openLink) {
      tg.openLink(url);
    } else {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  },

  getUser() {
    return tg?.initDataUnsafe?.user || null;
  }
};

// ==========================================================================
// 4. API Service & Offline Cache (Multi-Tenant Per User)
// ==========================================================================
const API_BASE_URL = (typeof window !== 'undefined' && (window.location.hostname.includes('github.io') || (window.location.hostname === 'localhost' && window.location.port !== '7860')))
  ? 'https://avito-radar.onrender.com'
  : (typeof window !== 'undefined' && window.location.origin ? window.location.origin : 'https://avito-radar.onrender.com');

const ApiService = {
  async getSearches() {
    const key = getUserStorageKey('searches');
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/searches?user_id=${encodeURIComponent(uid)}`, {
        headers: getApiHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.searches && Array.isArray(data.searches)) {
          SafeStorage.setItem(key, JSON.stringify(data.searches));
          return data.searches;
        }
      }
    } catch (err) {
      console.warn('[API] getSearches network call failed, falling back to cache:', err.message);
    }

    const cached = SafeStorage.getItem(key);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed)) return parsed;
      } catch (_) {}
    }

    return [];
  },

  async createSearch(payload) {
    const key = getUserStorageKey('searches');
    const uid = getCurrentUserId();
    const bodyPayload = { ...payload, user_id: uid };
    try {
      const res = await fetch(`${API_BASE_URL}/api/searches?user_id=${encodeURIComponent(uid)}`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify(bodyPayload)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.search) {
          const existing = await this.getSearches();
          const filtered = existing.filter(s => s.id !== data.search.id);
          filtered.unshift(data.search);
          SafeStorage.setItem(key, JSON.stringify(filtered));
          return data.search;
        }
        if (data.name) {
          const s = {
            id: data.name,
            query: payload.query,
            city: payload.city || 'Челябинск',
            minPrice: Number(payload.minPrice) || 0,
            isActive: true
          };
          const existing = await this.getSearches();
          const filtered = existing.filter(x => x.id !== s.id);
          filtered.unshift(s);
          SafeStorage.setItem(key, JSON.stringify(filtered));
          return s;
        }
      }
    } catch (err) {
      console.warn('[API] createSearch API offline, persisting locally:', err.message);
    }

    const id = `u${uid}_${payload.query.toLowerCase().replace(/[^a-z0-9а-яё]+/gi, '_')}_${payload.city || 'chelyabinsk'}`.replace(/^_+|_+$/g, '');
    const newSearch = {
      id: id,
      query: payload.query,
      city: payload.city || 'chelyabinsk',
      minPrice: Number(payload.minPrice) || 0,
      filters: payload.filters || {},
      isActive: true,
      createdAt: Date.now()
    };

    const existing = await this.getSearches();
    existing.unshift(newSearch);
    SafeStorage.setItem(key, JSON.stringify(existing));
    return newSearch;
  },

  async deleteSearch(id) {
    const key = getUserStorageKey('searches');
    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/searches/${encodeURIComponent(id)}?user_id=${encodeURIComponent(uid)}`, {
        method: 'DELETE',
        headers: getApiHeaders()
      });
    } catch (_) {}
    try {
      await fetch(`${API_BASE_URL}/api/searches/delete`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ name: id, id: id, user_id: uid })
      });
    } catch (_) {}

    const existing = await this.getSearches();
    const updated = existing.filter(s => s.id !== id);
    SafeStorage.setItem(key, JSON.stringify(updated));
    return true;
  },

  async triggerScan(id) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/searches/scan`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ name: id, id: id, user_id: uid })
      });
      return res.ok;
    } catch (_) {
      return false;
    }
  },

  async getLots(filters = {}) {
    const key = getUserStorageKey('lots');
    const uid = getCurrentUserId();
    try {
      const params = new URLSearchParams();
      params.append('user_id', uid);
      if (filters.searchId && filters.searchId !== 'all') {
        params.append('searchId', filters.searchId);
      }
      const res = await fetch(`${API_BASE_URL}/api/lots?${params.toString()}`, {
        headers: getApiHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.lots && Array.isArray(data.lots)) {
          const dismissedSet = this.getDismissedIds();
          data.lots.forEach(l => {
            if (dismissedSet.has(String(l.id))) l.isDismissed = true;
          });
          SafeStorage.setItem(key, JSON.stringify(data.lots));
          return data.lots;
        }
      }
    } catch (err) {
      console.warn('[API] getLots fetch failed, using offline fallback:', err.message);
    }

    const cached = SafeStorage.getItem(key);
    if (cached) {
      try {
        let lots = JSON.parse(cached);
        const dismissedSet = this.getDismissedIds();
        lots.forEach(l => {
          if (dismissedSet.has(String(l.id))) l.isDismissed = true;
        });
        return lots;
      } catch (_) {}
    }

    return [];
  },

  async dismissLot(id) {
    const strId = String(id);
    const dismissed = this.getDismissedIds();
    dismissed.add(strId);
    SafeStorage.setItem(getUserStorageKey('dismissed'), JSON.stringify(Array.from(dismissed)));

    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/lots/${strId}/dismiss?user_id=${encodeURIComponent(uid)}`, {
        method: 'POST',
        headers: getApiHeaders()
      });
    } catch (_) {}
    return true;
  },

  async restoreLot(id) {
    const strId = String(id);
    const dismissed = this.getDismissedIds();
    dismissed.delete(strId);
    SafeStorage.setItem(getUserStorageKey('dismissed'), JSON.stringify(Array.from(dismissed)));

    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/lots/${strId}/restore?user_id=${encodeURIComponent(uid)}`, {
        method: 'POST',
        headers: getApiHeaders()
      });
    } catch (_) {}
    return true;
  },

  getDismissedIds() {
    try {
      const raw = SafeStorage.getItem(getUserStorageKey('dismissed'));
      if (raw) return new Set(JSON.parse(raw));
    } catch (_) {}
    return new Set();
  }
};

// ==========================================================================
// 5. Application State
// ==========================================================================
const State = {
  searches: [],
  currentSearchId: 'all',
  lots: [],
  activeFilter: 'all', // 'all', 'noaccessories', 'deals', 'private', 'delivery', 'nodefects', 'dismissed'
  searchQuery: '',
  sortMode: 'deal', // 'deal', 'cheap', 'expensive', 'date'
  viewMode: 'cards', // 'cards', 'table', 'fav', 'searches'
  excludeAccessories: true,
  favorites: [],
  modalLot: null,
  pendingDeleteId: null
};

// Load saved favorites and accessories preference safely
try {
  const savedFavs = SafeStorage.getItem(getUserStorageKey('favorites'));
  if (savedFavs) State.favorites = JSON.parse(savedFavs);
  const savedAcc = SafeStorage.getItem(getUserStorageKey('exclude_accessories'));
  if (savedAcc !== null) State.excludeAccessories = savedAcc === 'true';
} catch (_) {}

// ==========================================================================
// 5.1 Accessory & Parts Intelligent Classifier (Prevents median breakage)
// ==========================================================================
const BIKE_ACC_RE = /\b(?:покрышк\w*|покрышка|покрышки|велопокрышк\w*|шины\s+для\s+вело\w*|велокамер\w*|бескамерк\w*|герметик\s+для\s+шин|сидушк\w*|сидень\w*\s+для|седл\w*|седло|подседел\w*|подседельный|педал\w*|педали|контактн\w*\s+педал\w*|топталк\w*|дропбар\w*|вынос\s+руля|вынос\w*|грипс\w*|обмотк\w*\s+руля|манетк\w*|шифтер\w*|рулев\w*\s+колонк\w*|велоцепь\w*|цепь\s+для\s+вело\w*|кассет\w*\s+(?:shimano|sram|для)|трещотк\w*|ротор\w*\s+(?:тормозной|shimano|sram|160|180)|калипер\w*|тормозн\w*\s+колодк\w*|байкпакинг\w*|велосумк\w*|подседельн\w*\s+сумк\w*|сумк\w*\s+(?:на\s+раму|на\s+руль|под\s+раму)|багажник\s+(?:для\s+вело|на\s+вело|велосипедн)|велокрыл\w*|крылья\s+(?:для\s+вело|на\s+вело)|флягодержател\w*|велокомпьютер\w*|велофара\w*|велофонар\w*|велошлем\w*|велотуфл\w*|велоформ\w*|джерси\s+(?:вело|для)|велоперчатк\w*|велозамок\w*|велонасос\w*|насос\s+(?:высокого\s+давления|для\s+вело)|велостанок\w*|подножк\w*\s+для\s+вело|фреймсет\w*|веловилк\w*)\b/i;

const ELEC_ACC_RE = /\b(?:чехол\w*|чехлы|чехольчик\w*|бампер\s+(?:на|для)|стекл\w*\s+(?:на|для|защитн\w*)|защитн\w*\s+стекл\w*|пленк\w*\s+(?:на|для|защитн\w*)|гидрогелев\w*|ремешок\w*|браслет\s+(?:для|на)|стилус\w*|s-pen|spen|apple\s+pencil|наконечник\w*|амбушюр\w*|кейс\s+(?:для|от)|коробк\w*\s+от|коробка\s+(?:от|для)|док-станци\w*|подставк\w*\s+(?:для|под)|держатель\s+(?:для|в\s+авто)|magsafe|зарядк\w*|зарядн\w*\s+устройств\w*|блок\w*\s+питания|сетев\w*\s+адаптер|кабел\w*|провод\w*|шнур\w*|переходник\w*|кулер\w*|вентилятор\w*|радиатор\w*|термопаст\w*|термопрокладк\w*|райзер\w*|бэкплейт\w*|кронштейн\w*|болтик\w*|винтик\w*|винты|шлейф\w*|заглушк\w*|кейкап\w*|свитч\w*|коврик\s+для\s+мыши)\b/i;

const AUTO_ACC_RE = /\b(?:коврик\w*|автоковрик\w*|авточехл\w*|накидк\w*\s+на\s+сидень\w*|брызговик\w*|дворник\w*|щетк\w*\s+стеклоочистител\w*|дефлектор\w*|ветровик\w*|колпак\w*\s+на\s+колес\w*|подлокотник\w*|видеорегистратор\w*|радар-детектор\w*|ароматизатор\w*|пахучк\w*|шильдик\w*|спойлер\w*|оплетк\w*\s+на\s+руль|органайзер\s+в\s+багажник|фаркоп\w*|автобокс\w*)\b/i;

const GEN_ACC_RE = /\b(?:аксессуар\w*|запчаст\w*|комплектующ\w*|детал\w*|расходник\w*|креплени\w*|крепеж\w*|ремкомплект\w*|насадк\w*|сменн\w*)\b/i;

function isAccessoryLot(lot, searchQuery = '') {
  if (!lot) return false;
  if (lot.isAccessory) return true;
  if (Array.isArray(lot.tags) && lot.tags.some(t => t.includes('Аксессуар') || t.includes('Велозапчасть') || t.includes('Автоаксессуар'))) {
    return true;
  }
  const t = (lot.title || '').toLowerCase();
  const q = (searchQuery || '').toLowerCase();
  const queryMentions = (term) => q && term && term.length >= 3 && q.includes(term.toLowerCase());

  const mBike = BIKE_ACC_RE.exec(t);
  if (mBike && !queryMentions(mBike[0].substring(0, 4))) return true;

  if (/\bруль\b/i.test(t) && !/\bруль\b/i.test(q)) {
    if (/гравел|велосипед|шоссе|mtb|баран|дропбар/i.test(t + ' ' + q)) return true;
  }

  if (/\bкамер[аыеу]\b/i.test(t) && !/\bкамер/i.test(q)) {
    if (/вело|700|28|29|26|27\.5|schwalbe|continental|maxxis|gravel|гравел/i.test(t)) return true;
  }

  const mElec = ELEC_ACC_RE.exec(t);
  if (mElec && !queryMentions(mElec[0].substring(0, 4))) return true;

  const mAuto = AUTO_ACC_RE.exec(t);
  if (mAuto && !queryMentions(mAuto[0].substring(0, 4))) return true;

  const mGen = GEN_ACC_RE.exec(t);
  if (mGen && !queryMentions(mGen[0].substring(0, 4))) return true;

  if (/^(?:для|на|к|под)\s+/i.test(t) && !/^(?:для|на|к|под)\s+/i.test(q)) return true;

  return false;
}

// ==========================================================================
// 6. DOM Elements Cache
// ==========================================================================
let DOM = {};

function initDOM() {
  DOM = {
    searchSelector: document.getElementById('searchSelector'),
    btnDeleteCurrentSearch: document.getElementById('btnDeleteCurrentSearch'),
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
    deleteSearchTitle: document.getElementById('deleteSearchTitle'),
    btnConfirmDelete: document.getElementById('btnConfirmDelete'),
    toastContainer: document.getElementById('toastContainer'),
    btnRefresh: document.getElementById('btnRefresh'),
    statMedianPrice: document.getElementById('statMedianPrice'),
    statDealsCount: document.getElementById('statDealsCount'),
    statTopDiscount: document.getElementById('statTopDiscount'),
    statActiveRadars: document.getElementById('statActiveRadars'),
    querySuggestionsDropdown: document.getElementById('querySuggestionsDropdown'),
    filterSuggestionsDropdown: document.getElementById('filterSuggestionsDropdown'),
    scanProgressModal: document.getElementById('scanProgressModal'),
    scanModalTitle: document.getElementById('scanModalTitle'),
    scanModalSub: document.getElementById('scanModalSub'),
    scanProgressBar: document.getElementById('scanProgressBar'),
    scanStatusStepText: document.getElementById('scanStatusStepText'),
    scanStatusPercent: document.getElementById('scanStatusPercent')
  };
}

// ==========================================================================
// Scan Progress Controller (Live 60fps Search Progress Bar)
// ==========================================================================
const ScanProgress = {
  timer: null,
  percent: 15,

  start(query, city) {
    if (!DOM.scanProgressModal) initDOM();
    if (!DOM.scanProgressModal) return;

    if (this.timer) clearInterval(this.timer);
    this.percent = 15;

    const cityAbbr = getCityAbbr(city);
    const cityLabel = (city && city.toLowerCase() === 'rossiya') ? 'Вся Россия' : `[${cityAbbr}]`;

    if (DOM.scanModalTitle) DOM.scanModalTitle.textContent = `Сканирование «${query}»`;
    if (DOM.scanModalSub) DOM.scanModalSub.textContent = `Регион: ${cityLabel} • Мониторинг Авито 24/7`;

    this.setProgress(15, 'Подключение к каталогу Avito...', 1);
    DOM.scanProgressModal.classList.remove('hidden');

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
    if (DOM.scanProgressBar) DOM.scanProgressBar.style.width = `${Math.min(100, pct)}%`;
    if (DOM.scanStatusPercent) DOM.scanStatusPercent.textContent = `${Math.min(100, Math.round(pct))}%`;
    if (DOM.scanStatusStepText && text) DOM.scanStatusStepText.textContent = text;

    for (let i = 1; i <= 4; i++) {
      const pill = document.getElementById(`scanPill${i}`);
      if (!pill) continue;
      if (i < activeStep) {
        pill.className = 'scan-pill done';
      } else if (i === activeStep) {
        pill.className = 'scan-pill active';
      } else {
        pill.className = 'scan-pill';
      }
    }
  },

  finish(count) {
    if (this.timer) clearInterval(this.timer);
    if (!DOM.scanProgressModal) return;

    if (count > 0) {
      this.setProgress(100, `Найдено ${count} объявлений • Готово`, 4);
    } else {
      this.setProgress(100, 'Сканирование завершено • 0 объявлений', 4);
    }

    setTimeout(() => {
      DOM.scanProgressModal?.classList.add('hidden');
    }, 600);
  }
};

// ==========================================================================
// 7. Core Controllers & View Switchers
// ==========================================================================
function setViewMode(mode) {
  TelegramService.haptic('medium');
  State.viewMode = mode;
  if (!DOM.lotsContainer) initDOM();

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
  if (!DOM.lotsContainer) initDOM();

  ['all', 'noaccessories', 'deals', 'private', 'delivery', 'nodefects', 'dismissed'].forEach(f => {
    const chip = document.getElementById(`chip-${f}`);
    if (chip) {
      if (f === filter) chip.classList.add('active');
      else chip.classList.remove('active');
    }
  });

  renderView();
}

function toggleExcludeAccessories() {
  TelegramService.haptic('selection');
  State.excludeAccessories = !State.excludeAccessories;
  SafeStorage.setItem(getUserStorageKey('exclude_accessories'), String(State.excludeAccessories));
  const statusText = State.excludeAccessories ? 'Аксессуары и запчасти скрыты' : 'Показываются все объявления (с аксессуарами)';
  showToast(statusText, 'info');
  updateStats();
  renderView();
}

function selectSearch(id) {
  TelegramService.haptic('light');
  State.currentSearchId = id;
  if (DOM.searchSelector) DOM.searchSelector.value = id;
  updateDeleteCurrentButtonVisibility();
  setViewMode('cards');
}

function updateDeleteCurrentButtonVisibility() {
  if (!DOM.btnDeleteCurrentSearch) return;
  if (State.currentSearchId && State.currentSearchId !== 'all') {
    DOM.btnDeleteCurrentSearch.classList.remove('hidden');
    const curr = State.searches.find(s => s.id === State.currentSearchId);
    if (curr) {
      DOM.btnDeleteCurrentSearch.title = `Удалить радар ${formatSearchDisplay(curr)}`;
    }
  } else {
    DOM.btnDeleteCurrentSearch.classList.add('hidden');
  }
}

function promptDeleteCurrent() {
  if (!State.currentSearchId || State.currentSearchId === 'all') {
    showToast('Выберите радар для удаления', 'info');
    return;
  }
  const curr = State.searches.find(s => s.id === State.currentSearchId);
  const title = curr ? formatSearchDisplay(curr) : State.currentSearchId;
  promptDelete(State.currentSearchId, title);
}

function promptDelete(id, title) {
  TelegramService.haptic('medium');
  State.pendingDeleteId = id;
  const titleEl = document.getElementById('deleteSearchTitle');
  if (titleEl) titleEl.textContent = title;
  DOM.modalOverlay?.classList.add('open');
  DOM.deleteModal?.classList.add('open');
}

async function handleConfirmDelete() {
  if (!State.pendingDeleteId) return;
  TelegramService.haptic('heavy');
  const id = State.pendingDeleteId;
  closeAllModals();

  await ApiService.deleteSearch(id);
  State.searches = State.searches.filter(s => s.id !== id);
  State.lots = State.lots.filter(l => l.searchId !== id);
  SafeStorage.setItem(getUserStorageKey('lots'), JSON.stringify(State.lots));

  if (State.currentSearchId === id) {
    State.currentSearchId = 'all';
  }

  populateSearchSelector();
  updateDeleteCurrentButtonVisibility();
  renderView();
  showToast('Радар удален из отслеживания', 'info');
}

async function scanSearch(id) {
  TelegramService.haptic('medium');
  const s = State.searches.find(x => x.id === id);
  const title = s ? s.query : id;
  const city = s ? s.city : 'Челябинск';
  ScanProgress.start(title, city);

  try {
    await ApiService.triggerScan(id);
    await loadData();
    const lotsCount = State.lots.filter(l => l.searchId === id && !l.isDismissed).length;
    ScanProgress.finish(lotsCount);
    TelegramService.haptic(lotsCount > 0 ? 'success' : 'medium');
    renderView();
    if (lotsCount > 0) {
      showToast(`Найдено ${lotsCount} лотов!`, 'success');
    } else {
      showToast('Новых лотов пока нет', 'info');
    }
  } catch (err) {
    ScanProgress.finish(0);
    showToast('Ошибка при сканировании', 'error');
  }
}

async function expandSearchToRussia(searchId) {
  TelegramService.haptic('medium');
  const s = State.searches.find(x => x.id === searchId);
  if (!s) return;
  showToast(`Расширяем поиск «${s.query}» на всю Россию...`, 'info');
  await ApiService.deleteSearch(searchId);
  const newS = await ApiService.createSearch({
    query: s.query,
    city: 'rossiya',
    minPrice: s.minPrice || 0
  });
  State.searches = State.searches.filter(x => x.id !== newS.id);
  State.searches.unshift(newS);
  State.currentSearchId = newS.id;
  populateSearchSelector();
  updateDeleteCurrentButtonVisibility();
  await scanSearch(newS.id);
}

async function resetMinPrice(searchId) {
  TelegramService.haptic('medium');
  const s = State.searches.find(x => x.id === searchId);
  if (!s) return;
  showToast(`Сбрасываем минимальную цену для «${s.query}»...`, 'info');
  await ApiService.deleteSearch(searchId);
  const newS = await ApiService.createSearch({
    query: s.query,
    city: s.city || 'rossiya',
    minPrice: 0
  });
  State.searches = State.searches.filter(x => x.id !== newS.id);
  State.searches.unshift(newS);
  State.currentSearchId = newS.id;
  populateSearchSelector();
  updateDeleteCurrentButtonVisibility();
  await scanSearch(newS.id);
}

function openNewSearchModal() {
  TelegramService.haptic('medium');
  DOM.modalOverlay?.classList.add('open');
  DOM.newSearchModal?.classList.add('open');
}

function closeAllModals() {
  TelegramService.haptic('light');
  DOM.modalOverlay?.classList.remove('open');
  DOM.bottomSheet?.classList.remove('open');
  DOM.newSearchModal?.classList.remove('open');
  DOM.deleteModal?.classList.remove('open');
  DOM.querySuggestionsDropdown?.classList.add('hidden');
  DOM.filterSuggestionsDropdown?.classList.add('hidden');
  State.pendingDeleteId = null;
}

// ==========================================================================
// 8. Lots, Favorites, Vanish
// ==========================================================================
function toggleFav(event, lotId) {
  if (event) event.stopPropagation();
  TelegramService.haptic('light');
  const strId = String(lotId);
  const idx = State.favorites.indexOf(strId);
  if (idx > -1) {
    State.favorites.splice(idx, 1);
  } else {
    State.favorites.push(strId);
  }
  SafeStorage.setItem(getUserStorageKey('favorites'), JSON.stringify(State.favorites));
  updateStats();
  renderView();
}

async function vanishLot(event, lotId) {
  if (event) event.stopPropagation();
  TelegramService.haptic('warning');
  const card = document.querySelector(`.lot-card[data-id="${lotId}"]`);
  if (card && !card.classList.contains('vanished-swipe')) {
    card.classList.add('vanishing');
    setTimeout(() => {
      applyVanish(lotId);
    }, 250);
  } else {
    applyVanish(lotId);
  }
}

function applyVanish(lotId) {
  const lot = State.lots.find(l => String(l.id) === String(lotId));
  if (lot) lot.isDismissed = true;
  ApiService.dismissLot(lotId);
  updateStats();
  renderView();
  showToast('Объявление скрыто', 'info');
}

async function restoreLot(event, lotId) {
  if (event) event.stopPropagation();
  TelegramService.haptic('success');
  const lot = State.lots.find(l => String(l.id) === String(lotId));
  if (lot) lot.isDismissed = false;
  await ApiService.restoreLot(lotId);
  updateStats();
  renderView();
  showToast('Объявление возвращено в поток', 'success');
}

function openDetails(event, lotId) {
  if (event) event.stopPropagation();
  const lot = State.lots.find(l => String(l.id) === String(lotId));
  if (lot) openLotModal(lot);
}

function openLotModal(lot) {
  TelegramService.haptic('medium');
  State.modalLot = lot;

  const mTitle = document.getElementById('modalTitle');
  const mPrice = document.getElementById('modalPrice');
  const mMarket = document.getElementById('modalMarketPrice');
  const mDisc = document.getElementById('modalDiscount');
  const mDesc = document.getElementById('modalDescription');
  const mSeller = document.getElementById('modalSellerName');
  const mType = document.getElementById('modalSellerType');
  const mLoc = document.getElementById('modalLocation');
  const mDate = document.getElementById('modalDate');

  if (mTitle) mTitle.textContent = lot.title;
  if (mPrice) mPrice.textContent = `${(lot.price || 0).toLocaleString('ru-RU')} ₽`;
  if (mMarket) mMarket.textContent = lot.marketPrice ? `Оценка рынка: ${lot.marketPrice.toLocaleString('ru-RU')} ₽` : '';
  if (mDisc) mDisc.textContent = lot.discount ? `${lot.discount}%` : '';
  if (mDesc) mDesc.textContent = lot.description || 'Описание отсутствует.';
  if (mSeller) mSeller.textContent = lot.seller?.name || 'Частник';
  if (mType) mType.textContent = lot.seller?.type === 'private' ? 'Частное лицо' : 'Компания / Магазин';
  if (mLoc) mLoc.textContent = lot.seller?.location || 'Челябинск';
  if (mDate) mDate.textContent = lot.publishedText || 'сегодня';

  const ratingEl = document.getElementById('modalSellerRating');
  const ratingVal = document.getElementById('modalSellerRatingVal');
  if (ratingEl && ratingVal) {
    if (lot.seller?.rating) {
      ratingVal.textContent = lot.seller.rating;
      ratingEl.style.display = 'inline-flex';
    } else {
      ratingEl.style.display = 'none';
    }
  }

  const imgEl = document.getElementById('modalMainImg');
  if (imgEl) {
    if (lot.images && lot.images.length > 0) {
      imgEl.src = lot.images[0];
      imgEl.style.display = 'block';
    } else {
      imgEl.style.display = 'none';
    }
  }

  const tagsContainer = document.getElementById('modalTags');
  if (tagsContainer) {
    tagsContainer.innerHTML = (lot.tags || []).map(t => `<span class="filter-chip" style="height: 26px; font-size: 11px;">${escapeHtml(t)}</span>`).join('');
  }

  const ctaBtn = document.getElementById('modalAvitoCta');
  if (ctaBtn) {
    ctaBtn.onclick = () => TelegramService.openLink(lot.avitoUrl);
  }

  DOM.modalOverlay?.classList.add('open');
  DOM.bottomSheet?.classList.add('open');
}

function openAvito(event, url) {
  if (event) event.stopPropagation();
  TelegramService.openLink(url);
}

function setQueryPreset(q, minP) {
  const qInput = document.getElementById('newQueryInput');
  const minInput = document.getElementById('newMinPriceInput');
  if (qInput) qInput.value = q;
  if (minInput && minP) minInput.value = minP;
}

async function quickAddPreset(query, city, minPrice) {
  TelegramService.haptic('medium');
  showToast(`Запуск радара «${query}»...`, 'info');
  try {
    const s = await ApiService.createSearch({
      query: query,
      city: city || 'chelyabinsk',
      minPrice: Number(minPrice) || 0
    });
    if (s && s.id) {
      State.currentSearchId = s.id;
    }
    await loadData();
    showToast(`Радар «${query}» успешно запущен!`, 'success');
  } catch (err) {
    console.error('Quick add preset error:', err);
    showToast('Ошибка при запуске радара', 'error');
  }
}

function applyQueryFilter(query) {
  State.searchQuery = (query || '').trim().toLowerCase();
  if (DOM.filterInput && DOM.filterInput.value !== query) {
    DOM.filterInput.value = query || '';
  }
  if (DOM.btnClearFilter) {
    if (State.searchQuery) DOM.btnClearFilter.classList.remove('hidden');
    else DOM.btnClearFilter.classList.add('hidden');
  }
  updateStats();
  renderView();
}

// ==========================================================================
// 9. Data Fetching & Sync
// ==========================================================================
async function loadData() {
  if (State.lots.length === 0) {
    renderSkeletonCards(4);
  }
  try {
    const favKey = getUserStorageKey('favorites');
    const savedFavs = SafeStorage.getItem(favKey);
    if (savedFavs) State.favorites = JSON.parse(savedFavs);
  } catch (_) {}

  State.searches = await ApiService.getSearches();
  State.lots = await ApiService.getLots({ includeDismissed: true });

  populateSearchSelector();
  updateDeleteCurrentButtonVisibility();
  renderView();
}

function populateSearchSelector() {
  if (!DOM.searchSelector) return;
  DOM.searchSelector.innerHTML = '';

  if (State.searches.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Нет активных радаров';
    DOM.searchSelector.appendChild(opt);
    return;
  }

  const allOpt = document.createElement('option');
  allOpt.value = 'all';
  allOpt.textContent = 'Все радары (общий поток)';
  DOM.searchSelector.appendChild(allOpt);

  State.searches.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id;
    const count = State.lots.filter(l => l.searchId === s.id && !l.isDismissed).length;
    const title = formatSearchDisplay(s);
    opt.textContent = `${title} (${count} шт.)`;
    if (s.id === State.currentSearchId) opt.selected = true;
    DOM.searchSelector.appendChild(opt);
  });
}

function getVisibleLots() {
  let lots = [...State.lots];

  // Radar scope filter
  if (State.currentSearchId && State.currentSearchId !== 'all') {
    lots = lots.filter(l => l.searchId === State.currentSearchId);
  }

  const currentSearch = State.searches.find(s => s.id === State.currentSearchId);
  const searchQ = currentSearch?.query || '';

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

  // Accessory exclusion: active when 'noaccessories' chip is selected,
  // or when global excludeAccessories is on (unless user specifically chose 'all' to see all items)
  const shouldFilterAcc = State.activeFilter === 'noaccessories' ||
    (State.excludeAccessories && State.activeFilter !== 'all' && State.activeFilter !== 'dismissed');

  if (shouldFilterAcc || State.activeFilter === 'noaccessories') {
    lots = lots.filter(l => !isAccessoryLot(l, searchQ));
  }

  // Chip filters
  if (State.activeFilter === 'deals') {
    lots = lots.filter(l => l.discount <= -12 && !l.isComboListing && !isAccessoryLot(l, searchQ));
  } else if (State.activeFilter === 'private') {
    lots = lots.filter(l => l.seller.type === 'private');
  } else if (State.activeFilter === 'delivery') {
    lots = lots.filter(l => (l.badges || []).some(b => b.toLowerCase().includes('доставка')));
  } else if (State.activeFilter === 'nodefects') {
    lots = lots.filter(l => !(l.tags || []).some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное')));
  }

  // Keyword query filter
  if (State.searchQuery) {
    lots = lots.filter(l => {
      const text = `${l.title} ${l.description} ${l.seller.name} ${l.seller.location}`.toLowerCase();
      return text.includes(State.searchQuery);
    });
  }

  // Sorting
  if (State.sortMode === 'cheap') {
    lots.sort((a, b) => a.price - b.price);
  } else if (State.sortMode === 'expensive') {
    lots.sort((a, b) => b.price - a.price);
  } else if (State.sortMode === 'date') {
    lots.sort((a, b) => (b.postedAt || 0) - (a.postedAt || 0));
  } else {
    // Discount percent descending (most negative first)
    lots.sort((a, b) => (a.discount || 999) - (b.discount || 999));
  }

  return lots;
}

function renderView() {
  if (!DOM.lotsContainer) initDOM();
  updateStats();

  const statsGrid = document.getElementById('statsGrid');
  const filterChipsRow = document.getElementById('filterChipsRow');
  const searchRow = document.getElementById('filterInput')?.closest('div');

  if (State.viewMode === 'searches') {
    if (statsGrid) statsGrid.style.display = 'none';
    if (filterChipsRow) filterChipsRow.style.display = 'none';
    if (searchRow) searchRow.style.display = 'none';
    if (DOM.lotsContainer) { DOM.lotsContainer.style.display = 'none'; DOM.lotsContainer.classList.add('hidden'); }
    if (DOM.tableWrapper) { DOM.tableWrapper.style.display = 'none'; DOM.tableWrapper.classList.add('hidden'); }
    if (DOM.emptyState) { DOM.emptyState.style.display = 'none'; DOM.emptyState.classList.add('hidden'); }
    if (DOM.searchesSection) { DOM.searchesSection.style.display = 'block'; DOM.searchesSection.classList.remove('hidden'); }
    renderSearchesManager();
    return;
  }

  if (statsGrid) statsGrid.style.display = '';
  if (filterChipsRow) filterChipsRow.style.display = '';
  if (searchRow) searchRow.style.display = '';

  if (DOM.searchesSection) {
    DOM.searchesSection.style.display = 'none';
    DOM.searchesSection.classList.add('hidden');
  }

  const visible = getVisibleLots();

  if (visible.length === 0) {
    if (DOM.lotsContainer) {
      DOM.lotsContainer.style.display = 'none';
      DOM.lotsContainer.classList.add('hidden');
      DOM.lotsContainer.innerHTML = '';
    }
    if (DOM.tableWrapper) {
      DOM.tableWrapper.style.display = 'none';
      DOM.tableWrapper.classList.add('hidden');
      if (DOM.tableBody) DOM.tableBody.innerHTML = '';
    }
    if (DOM.emptyState) {
      DOM.emptyState.style.display = 'block';
      DOM.emptyState.classList.remove('hidden');
    }
    renderEmptyState();
    return;
  }

  if (DOM.emptyState) {
    DOM.emptyState.style.display = 'none';
    DOM.emptyState.classList.add('hidden');
  }

  if (State.viewMode === 'table') {
    if (DOM.lotsContainer) {
      DOM.lotsContainer.style.display = 'none';
      DOM.lotsContainer.classList.add('hidden');
    }
    if (DOM.tableWrapper) {
      DOM.tableWrapper.style.display = 'block';
      DOM.tableWrapper.classList.remove('hidden');
    }
    renderTableView(visible);
  } else {
    if (DOM.tableWrapper) {
      DOM.tableWrapper.style.display = 'none';
      DOM.tableWrapper.classList.add('hidden');
    }
    if (DOM.lotsContainer) {
      DOM.lotsContainer.style.display = 'grid';
      DOM.lotsContainer.classList.remove('hidden');
    }
    renderCardsView(visible);
  }
}

function updateStats() {
  const activeLots = State.lots.filter(l => !l.isDismissed);
  const currentScoped = State.currentSearchId === 'all'
    ? activeLots
    : activeLots.filter(l => l.searchId === State.currentSearchId);

  const currentSearch = State.searches.find(s => s.id === State.currentSearchId);
  const searchQ = currentSearch?.query || '';

  // Calculate clean market median strictly excluding accessories, defects and combo bait listings
  const nonAccessoryLots = currentScoped.filter(l => !isAccessoryLot(l, searchQ) && !l.isComboListing);
  const targetLots = nonAccessoryLots.length >= 2 ? nonAccessoryLots : currentScoped;

  let medianPrice = 0;
  const validPrices = targetLots.map(l => l.price).filter(p => typeof p === 'number' && p > 0);
  if (validPrices.length > 0) {
    const sorted = [...validPrices].sort((a, b) => a - b);
    let slice = sorted;
    if (sorted.length >= 4) {
      const upperHalf = sorted.slice(Math.floor(sorted.length / 2));
      const upperMed = upperHalf[Math.floor(upperHalf.length / 2)];
      if (upperMed >= 15000) {
        const cutoff = Math.max(1000, Math.floor(upperMed * 0.25));
        const trimmed = sorted.filter(p => p >= cutoff);
        if (trimmed.length >= 2) slice = trimmed;
      }
    }
    const mid = Math.floor(slice.length / 2);
    medianPrice = slice.length % 2 === 0 ? Math.round((slice[mid - 1] + slice[mid]) / 2) : slice[mid];
  } else {
    medianPrice = targetLots.find(l => l.marketPrice)?.marketPrice || 0;
  }

  if (DOM.statMedianPrice) {
    DOM.statMedianPrice.textContent = medianPrice > 0 ? `${medianPrice.toLocaleString('ru-RU')} ₽` : '—';
  }

  // Deals Count (excluding accessories from being counted as product deals)
  const dealsCount = targetLots.filter(l => l.discount <= -12 && !l.isComboListing && !isAccessoryLot(l, searchQ)).length;
  if (DOM.statDealsCount) {
    DOM.statDealsCount.textContent = dealsCount;
  }

  // Top Discount
  const topDeal = targetLots.find(l => l.discount < 0 && !l.isComboListing && !isAccessoryLot(l, searchQ));
  if (DOM.statTopDiscount) {
    DOM.statTopDiscount.textContent = topDeal ? `${topDeal.discount}%` : '0%';
  }

  // Active Radars Count
  if (DOM.statActiveRadars) {
    DOM.statActiveRadars.textContent = State.searches.length;
  }

  // Badges
  const favCount = document.getElementById('favCount');
  if (favCount) favCount.textContent = State.favorites.length;

  const dismissedCount = document.getElementById('dismissedCount');
  const totalDismissed = State.lots.filter(l => l.isDismissed).length;
  if (dismissedCount) dismissedCount.textContent = totalDismissed;
}

function renderEmptyState() {
  if (!DOM.emptyState) return;

  if (State.searches.length === 0) {
    DOM.emptyState.innerHTML = `
      <div class="onboarding-card" style="text-align: center; padding: 28px 16px; background: var(--surface-card); border-radius: 16px; border: 1px solid var(--border-subtle); max-width: 480px; margin: 10px auto;">
        <div class="radar-logo" style="width: 52px; height: 52px; margin: 0 auto 16px; border-radius: 12px;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="9"/>
            <path d="M12 3v18M3 12h18"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </div>
        <div class="h3" style="font-size: 17px; margin-bottom: 8px;">Терминал мониторинга Avito</div>
        <p class="caption" style="font-size: 13px; line-height: 1.5; margin-bottom: 20px; color: var(--text-secondary);">
          Создайте свой первый радар для отслеживания выгодных предложений на Авито. Мы проверяем обновления 24/7 и присылаем лучшие цены.
        </p>

        <div style="margin-bottom: 20px;">
          <div style="font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 10px;">
            Популярные категории:
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;">
            <button class="filter-chip" onclick="window.app.quickAddPreset('iPhone 15', 'chelyabinsk', 40000)" style="font-size: 12px; height: 34px;">iPhone 15</button>
            <button class="filter-chip" onclick="window.app.quickAddPreset('RTX 4070', 'chelyabinsk', 35000)" style="font-size: 12px; height: 34px;">RTX 4070</button>
            <button class="filter-chip" onclick="window.app.quickAddPreset('PlayStation 5', 'chelyabinsk', 25000)" style="font-size: 12px; height: 34px;">PS5</button>
            <button class="filter-chip" onclick="window.app.quickAddPreset('DDR5 32GB', 'rossiya', 8000)" style="font-size: 12px; height: 34px;">DDR5 32GB</button>
          </div>
        </div>

        <button class="btn-cta" onclick="window.app.openNewSearchModal()" style="max-width: 260px; margin: 0 auto; height: 42px; font-size: 13px;">
          <span>+</span>
          <span>Настроить свой поиск</span>
        </button>
      </div>
    `;
    return;
  }

  if (State.searchQuery) {
    DOM.emptyState.innerHTML = `
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.6; margin-bottom: 12px; margin-inline: auto;">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>
      <div class="h3" style="margin-bottom: 6px;">Ничего не найдено</div>
      <p class="caption" style="margin-bottom: 16px;">По запросу «${escapeHtml(State.searchQuery)}» нет совпадений.</p>
      <button class="filter-chip" onclick="document.getElementById('filterInput').value=''; window.app.applyQueryFilter('');" style="margin: 0 auto; border-color: var(--primary); color: var(--primary);">
        Очистить поиск
      </button>
    `;
    return;
  }

  if (State.activeFilter !== 'all') {
    DOM.emptyState.innerHTML = `
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.6; margin-bottom: 12px; margin-inline: auto;">
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
      </svg>
      <div class="h3" style="margin-bottom: 6px;">Нет лотов под этот фильтр</div>
      <p class="caption" style="margin-bottom: 16px;">Попробуйте выбрать другой фильтр или посмотреть все предложения.</p>
      <button class="filter-chip" onclick="window.app.setFilterChip('all')" style="margin: 0 auto; border-color: var(--primary); color: var(--primary);">
        Показать все лоты
      </button>
    `;
    return;
  }

  if (State.currentSearchId && State.currentSearchId !== 'all') {
    const curr = State.searches.find(s => s.id === State.currentSearchId);
    const title = curr ? formatSearchDisplay(curr) : State.currentSearchId;
    const isRossiya = curr && (curr.city === 'Вся Россия' || curr.city === 'rossiya');
    const hasMinPrice = curr && curr.minPrice > 0;

    DOM.emptyState.innerHTML = `
      <div style="text-align: center; padding: 28px 18px; background: var(--surface-card); border-radius: 16px; border: 1px solid var(--border-subtle); max-width: 440px; margin: 12px auto;">
        <div class="radar-logo" style="width: 52px; height: 52px; margin: 0 auto 16px; border-radius: 12px;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
          </svg>
        </div>
        <div class="h3" style="font-size: 16px; margin-bottom: 6px;">Объявлений пока не найдено</div>
        <p class="caption" style="margin-bottom: 16px; line-height: 1.5; color: var(--text-secondary);">
          По запросу «<b style="color: var(--text-primary);">${escapeHtml(curr?.query || title)}</b>» в регионе <b>${escapeHtml(curr?.city || 'Вся Россия')}</b> пока нет лотов.
          ${hasMinPrice ? `<br><span style="color: var(--warning); display: inline-block; margin-top: 4px;">Фильтр цены: от ${curr.minPrice.toLocaleString('ru-RU')} ₽.</span>` : ''}
          <br>Радар работает 24/7 и пришлет уведомление при появлении свежих объявлений.
        </p>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <button class="btn-cta" onclick="window.app.scanSearch('${State.currentSearchId}')" style="height: 42px; font-size: 13px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;">
              <polyline points="23 4 23 10 17 10"></polyline>
              <polyline points="1 20 1 14 7 14"></polyline>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
            </svg>
            Просканировать Авито сейчас
          </button>
          ${!isRossiya ? `
            <button class="filter-chip" onclick="window.app.expandSearchToRussia('${State.currentSearchId}')" style="height: 38px; justify-content: center; font-size: 12px; border-color: rgba(197, 160, 89, 0.4); color: var(--primary);">
              Искать по всей России
            </button>
          ` : ''}
          ${hasMinPrice ? `
            <button class="filter-chip" onclick="window.app.resetMinPrice('${State.currentSearchId}')" style="height: 38px; justify-content: center; font-size: 12px; border-color: rgba(217, 119, 6, 0.4); color: #f59e0b;">
              Сбросить минимальную цену (${curr.minPrice.toLocaleString('ru-RU')} ₽)
            </button>
          ` : ''}
        </div>
      </div>
    `;
    return;
  }

  DOM.emptyState.innerHTML = `
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.6; margin-bottom: 12px; margin-inline: auto;">
      <circle cx="11" cy="11" r="8"></circle>
      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>
    <div class="h3" style="margin-bottom: 6px;">Нет подходящих объявлений</div>
    <p class="caption" style="margin-bottom: 16px;">Добавьте новый поисковый запрос в радар.</p>
    <button class="btn-cta" onclick="window.app.openNewSearchModal()" style="max-width: 220px; margin: 0 auto; height: 38px;">
      + Создать поиск
    </button>
  `;
}

// ==========================================================================
// 10. Card View Rendering, Skeletons & Mobile Swipes
// ==========================================================================
function renderSkeletonCards(count = 4) {
  if (!DOM.lotsContainer) initDOM();
  if (!DOM.lotsContainer) return;
  DOM.lotsContainer.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const card = document.createElement('div');
    card.className = 'skeleton-card';
    card.innerHTML = `
      <div class="skeleton-shimmer skeleton-img"></div>
      <div class="skeleton-header-row">
        <div class="skeleton-shimmer skeleton-pill"></div>
        <div class="skeleton-shimmer skeleton-pill" style="width: 24px; height: 24px; border-radius: 6px;"></div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px;">
        <div class="skeleton-shimmer skeleton-title-1"></div>
        <div class="skeleton-shimmer skeleton-title-2"></div>
      </div>
      <div class="skeleton-shimmer skeleton-price"></div>
      <div class="skeleton-shimmer skeleton-meta"></div>
      <div class="skeleton-shimmer skeleton-btn"></div>
    `;
    DOM.lotsContainer.appendChild(card);
  }
}

function attachSwipeToCard(card, lot) {
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

    // Only allow swipe left (diffX < 0)
    if (diffX < 0) {
      if (e.cancelable) e.preventDefault();
      card.style.transform = `translateX(${diffX}px)`;
      const opacity = Math.max(0.3, 1 - Math.abs(diffX) / 280);
      card.style.opacity = opacity;

      // Haptic threshold trigger
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
      setTimeout(() => {
        vanishLot(null, lot.id);
      }, 240);
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

  // Find search for city badge
  const searchObj = State.searches.find(s => s.id === lot.searchId);
  const cityAbbr = getCityAbbr(searchObj?.city || lot.seller?.location);

  // Image preview
  const photoUrl = (lot.images && lot.images.length > 0) ? lot.images[0] : '';
  const mediaHtml = photoUrl ? `
    <div class="card-media-preview">
      <img src="${photoUrl}" alt="${escapeHtml(lot.title)}" loading="lazy" class="card-media-img">
      <button class="card-fav-btn ${isFav ? 'active' : ''}" onclick="window.app.toggleFav(event, '${lot.id}')" title="В избранное">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="${isFav ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      </button>
    </div>
  ` : '';

  // Deal badge or Combo alert
  let badgeHtml = '';
  if (isDeal) {
    badgeHtml = `<div class="deal-badge"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 3px;"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg> ВЫГОДА ${lot.discount}%</div>`;
  } else if (lot.isComboListing) {
    badgeHtml = `<div class="deal-badge" style="background: rgba(245, 158, 11, 0.15); color: #F59E0B; border-color: rgba(245, 158, 11, 0.3)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 3px;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> СБОРНЫЙ ЛОТ</div>`;
  } else {
    badgeHtml = `<span class="caption font-mono">${lot.publishedText || 'сегодня'}</span>`;
  }

  // Price formatting
  const priceFormatted = `${lot.price.toLocaleString('ru-RU')} ₽`;
  const marketFormatted = lot.marketPrice ? `${lot.marketPrice.toLocaleString('ru-RU')} ₽` : '';
  const diffSign = lot.discount <= 0 ? '' : '+';

  // Vanish button: X or restore
  const vanishHtml = lot.isDismissed ? `
    <button class="btn-vanish" onclick="window.app.restoreLot(event, '${lot.id}')" title="Вернуть объявление" style="color: var(--success)">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>
    </button>
  ` : `
    <button class="btn-vanish" onclick="window.app.vanishLot(event, '${lot.id}')" title="Скрыть объявление (Vanish)">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>
  `;

  // Secondary badges
  const isAcc = isAccessoryLot(lot, searchObj?.query || '');
  let tagsList = [...(lot.tags || [])];
  if (isAcc && !tagsList.some(t => t.includes('Аксессуар') || t.includes('Велозапчасть') || t.includes('Автоаксессуар'))) {
    tagsList.unshift('🛡️ Аксессуар');
  }

  const pillsHtml = tagsList.slice(0, 2).map(tag => {
    let cls = 'badge-subtle';
    if (tag.includes('Частный')) cls += ' badge-private';
    if (tag.includes('Сборное') || tag.includes('Дефект')) cls += ' badge-warning';
    if (tag.includes('Аксессуар') || tag.includes('Велозапчасть') || tag.includes('Автоаксессуар')) cls += ' badge-acc';
    return `<span class="${cls}">${escapeHtml(tag)}</span>`;
  }).join('');

  card.innerHTML = `
    ${mediaHtml}
    <div class="card-header">
      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
        <span class="city-abbr-tag">[${cityAbbr}]</span>
        ${badgeHtml}
      </div>
      ${vanishHtml}
    </div>

    <div class="card-body">
      <h3 class="card-title">${escapeHtml(lot.title)}</h3>

      <div class="card-price-row">
        <div class="card-price">${priceFormatted}</div>
        ${marketFormatted ? `<div class="card-market font-mono">${marketFormatted} <span style="color: ${lot.discount <= -12 ? 'var(--success)' : 'inherit'};">(${diffSign}${lot.discount}%)</span></div>` : ''}
      </div>

      <div class="card-meta">
        <div class="card-seller">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          <span>${escapeHtml(lot.seller?.name || 'Частник')}</span>
          ${lot.seller?.rating ? `<span class="rating-badge font-mono">★ ${lot.seller.rating}</span>` : ''}
        </div>
        <div class="card-location">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          <span>${escapeHtml(lot.seller?.location || 'Челябинск')}</span>
        </div>
      </div>

      ${pillsHtml ? `<div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;">${pillsHtml}</div>` : ''}

      <div class="card-actions">
        <button class="btn-cta" onclick="window.app.openAvito(event, '${lot.avitoUrl}')" style="flex: 2;">
          <span>ОТКРЫТЬ НА АВИТО</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </button>
        <button class="filter-chip" onclick="window.app.openDetails(event, '${lot.id}')" style="flex: 1; justify-content: center;" title="Подробнее">
          Подробнее
        </button>
      </div>
    </div>
  `;

  card.addEventListener('click', (e) => {
    if (e.target.closest('button') || e.target.closest('a')) return;
    openLotModal(lot);
  });

  attachSwipeToCard(card, lot);

  return card;
}

// ==========================================================================
// 11. Table View Rendering
// ==========================================================================
function renderTableView(lots) {
  if (!DOM.tableBody) return;
  DOM.tableBody.innerHTML = '';

  lots.forEach(lot => {
    const tr = document.createElement('tr');
    tr.dataset.id = lot.id;
    const diffSign = (lot.discount || 0) <= 0 ? '' : '+';
    const isDeal = (lot.discount || 0) <= -12;
    const searchObj = State.searches.find(s => s.id === lot.searchId);
    const sellerLocation = lot.seller?.location || searchObj?.city || 'Челябинск';
    const sellerName = lot.seller?.name || 'Частник';
    const cityAbbr = getCityAbbr(searchObj?.city || sellerLocation);

    tr.innerHTML = `
      <td>
        <div style="font-weight: 500; display: flex; align-items: center; gap: 6px;">
          <span class="city-abbr-tag" style="padding: 1px 4px; font-size: 10px;">[${cityAbbr}]</span>
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 220px;">${escapeHtml(lot.title || '')}</span>
        </div>
        <div class="caption">${escapeHtml(sellerLocation)}</div>
      </td>
      <td class="font-mono" style="font-weight: 600; white-space: nowrap;">
        ${(lot.price || 0).toLocaleString('ru-RU')} ₽
      </td>
      <td class="font-mono" style="color: var(--text-secondary); white-space: nowrap;">
        ${lot.marketPrice ? `${lot.marketPrice.toLocaleString('ru-RU')} ₽` : '—'}
      </td>
      <td class="font-mono" style="white-space: nowrap;">
        ${lot.discount ? `<span style="color: ${isDeal ? 'var(--success)' : 'var(--text-secondary)'}; font-weight: 600;">${diffSign}${lot.discount}%</span>` : '—'}
      </td>
      <td style="color: var(--text-secondary); max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        ${escapeHtml(sellerName)}
      </td>
      <td style="text-align: right; white-space: nowrap;">
        <button class="btn-vanish" onclick="window.app.vanishLot(event, '${lot.id}')" title="Скрыть">✕</button>
        <button class="btn-vanish" onclick="window.app.openAvito(event, '${lot.avitoUrl}')" title="Открыть на Авито" style="color: var(--primary);">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
        </button>
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
// 12. Searches Manager Section (Менеджер радаров)
// ==========================================================================
function renderSearchesManager() {
  if (!DOM.searchesList) return;
  DOM.searchesList.innerHTML = '';

  if (State.searches.length === 0) {
    DOM.searchesList.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; background: var(--surface-card); border-radius: 16px; border: 1px solid var(--border-subtle);">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 12px; margin-inline: auto;">
          <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
        </svg>
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
    const cityAbbr = getCityAbbr(s.city);
    const cleanTitle = cleanQueryTitle(s.query || s.title || s.id);
    const displayLabel = formatSearchDisplay(s);

    card.className = 'stat-card';
    card.style.marginBottom = '12px';
    if (isActive) {
      card.style.borderColor = 'var(--primary)';
      card.style.boxShadow = 'var(--primary-glow)';
    }

    card.innerHTML = `
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px;">
        <div style="flex: 1;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span class="city-abbr-tag">[${cityAbbr}]</span>
            <h3 class="h3" style="font-size: 16px;">${escapeHtml(cleanTitle)}</h3>
            ${isActive ? '<span class="brand-badge" style="background: var(--success-bg); color: var(--success); border-color: rgba(16,185,129,0.3)">АКТИВЕН</span>' : ''}
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; font-size: 11px;" class="font-mono">
            <span style="padding: 2px 8px; border-radius: 6px; background: #0E0E11; border: 1px solid var(--border-subtle);">${escapeHtml(s.city || 'Челябинск')}</span>
            <span style="padding: 2px 8px; border-radius: 6px; background: #0E0E11; border: 1px solid var(--border-subtle); color: var(--primary);">${lotCount} лотов</span>
            <span style="padding: 2px 8px; border-radius: 6px; background: #0E0E11; border: 1px solid var(--border-subtle);">${minPriceText}</span>
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px;">
        <button class="btn-cta" onclick="window.app.selectSearch('${s.id}')" style="height: 38px; font-size: 12px; flex: 2; background: ${isActive ? 'var(--surface-hover)' : 'var(--primary-gradient)'};">
          ${isActive ? 'Просмотр лотов' : 'Выбрать этот радар'}
        </button>
        <button class="filter-chip" onclick="window.app.scanSearch('${s.id}')" style="height: 38px; flex: 1; justify-content: center;" title="Сканировать">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/>
          </svg>
          Скан
        </button>
        <button class="filter-chip" onclick="window.app.promptDelete('${s.id}', '${escapeHtml(displayLabel)}')" style="height: 38px; color: var(--danger); border-color: rgba(239, 68, 68, 0.3); background: var(--danger-bg); justify-content: center; padding: 0 14px;" title="Удалить радар">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;">
            <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
          </svg>
          <span>Удалить</span>
        </button>
      </div>
    `;

    DOM.searchesList.appendChild(card);
  });
}

// ==========================================================================
// 13. Form Submissions & Event Listeners
// ==========================================================================
async function handleNewSearchSubmit(e) {
  if (e) e.preventDefault();
  const qEl = document.getElementById('newQueryInput');
  const cityEl = document.getElementById('newCitySelect');
  const minPEl = document.getElementById('newMinPriceInput');

  const q = qEl ? qEl.value.trim() : '';
  const city = cityEl ? cityEl.value : 'chelyabinsk';
  const minP = minPEl ? minPEl.value.trim() : '';

  if (!q) {
    showToast('Введите название товара!', 'error');
    return;
  }

  const excludeAccEl = document.getElementById('newExcludeAccessories');
  const excludeAcc = excludeAccEl ? excludeAccEl.checked : true;

  TelegramService.haptic('success');
  closeAllModals();

  ScanProgress.start(q, city);

  try {
    const newSearch = await ApiService.createSearch({
      query: q,
      city: city,
      minPrice: minP ? Number(minP) : 0,
      filters: { noDefects: true, excludeAccessories: excludeAcc }
    });

    State.searches = State.searches.filter(s => s.id !== newSearch.id);
    State.searches.unshift(newSearch);
    State.currentSearchId = newSearch.id;

    populateSearchSelector();
    updateDeleteCurrentButtonVisibility();

    // Trigger immediate scan and load data
    await ApiService.triggerScan(newSearch.id);
    await loadData();

    let lotsCount = State.lots.filter(l => l.searchId === newSearch.id && !l.isDismissed).length;

    if (lotsCount === 0) {
      // Check 1 more time after 2s in case background crawler was processing
      await new Promise(r => setTimeout(r, 2000));
      await loadData();
      lotsCount = State.lots.filter(l => l.searchId === newSearch.id && !l.isDismissed).length;
    }

    ScanProgress.finish(lotsCount);
    TelegramService.haptic(lotsCount > 0 ? 'success' : 'medium');
    setViewMode('cards');

    if (lotsCount > 0) {
      showToast(`Найдено ${lotsCount} лотов по «${q}»!`, 'success');
    } else {
      showToast(`Радар [${getCityAbbr(city)}] запущен!`, 'info');
    }
  } catch (err) {
    console.error('Search creation/scan failed:', err);
    ScanProgress.finish(0);
    showToast('Ошибка при запуске радара', 'error');
  }
}

function showToast(message, type = 'info') {
  if (!DOM.toastContainer) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const icon = type === 'success'
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
    : type === 'error'
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
    : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>';
  toast.innerHTML = `<span style="display: inline-flex; align-items: center;">${icon}</span><span>${escapeHtml(message)}</span>`;

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

function setupEventListeners() {
  // Search selector change
  DOM.searchSelector?.addEventListener('change', (e) => {
    TelegramService.haptic('light');
    State.currentSearchId = e.target.value;
    updateDeleteCurrentButtonVisibility();
    renderView();
  });

  // Keyword input filter
  DOM.filterInput?.addEventListener('input', (e) => {
    State.searchQuery = e.target.value.trim().toLowerCase();
    if (State.searchQuery) DOM.btnClearFilter?.classList.remove('hidden');
    else DOM.btnClearFilter?.classList.add('hidden');
    renderView();
  });

  DOM.btnClearFilter?.addEventListener('click', () => {
    TelegramService.haptic('light');
    if (DOM.filterInput) DOM.filterInput.value = '';
    State.searchQuery = '';
    DOM.btnClearFilter?.classList.add('hidden');
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
    const svg = DOM.btnRefresh.querySelector('svg');
    if (svg) svg.classList.add('rotating');
    showToast('Синхронизация с сервером...', 'info');
    try {
      if (State.currentSearchId && State.currentSearchId !== 'all') {
        await scanSearch(State.currentSearchId);
      } else {
        await loadData();
        showToast('Данные синхронизированы', 'success');
      }
    } finally {
      if (svg) svg.classList.remove('rotating');
    }
  });

  // Modal Backdrop Close
  DOM.modalOverlay?.addEventListener('click', closeAllModals);

  // Forms & buttons
  document.getElementById('formNewSearch')?.addEventListener('submit', handleNewSearchSubmit);
  document.getElementById('btnConfirmDelete')?.addEventListener('click', handleConfirmDelete);

  // Segmented tab listeners (fallback for touch/click)
  ['cards', 'table', 'fav', 'searches'].forEach(mode => {
    document.getElementById(`tab-${mode}`)?.addEventListener('click', (e) => {
      e.preventDefault();
      setViewMode(mode);
    });
  });

  // Filter chip listeners
  ['all', 'deals', 'private', 'delivery', 'nodefects', 'dismissed'].forEach(chip => {
    document.getElementById(`chip-${chip}`)?.addEventListener('click', (e) => {
      e.preventDefault();
      setFilterChip(chip);
    });
  });

  // Initialize smart autocomplete on new search modal input
  const newQueryInput = document.getElementById('newQueryInput');
  const queryDropdown = document.getElementById('querySuggestionsDropdown');
  if (newQueryInput && queryDropdown && window.Suggestions) {
    window.Suggestions.init(newQueryInput, queryDropdown, {
      limit: 7,
      onSelect: (item) => {
        const minPriceInput = document.getElementById('newMinPriceInput');
        if (minPriceInput && item.minPrice && (!minPriceInput.value || minPriceInput.value === '0')) {
          minPriceInput.value = item.minPrice;
        }
        showToast(`Выбрано: ${item.title}`, 'info');
      }
    });
  }

  // Initialize smart autocomplete on feed filter input
  const filterInput = document.getElementById('filterInput');
  const filterDropdown = document.getElementById('filterSuggestionsDropdown');
  if (filterInput && filterDropdown && window.Suggestions) {
    window.Suggestions.init(filterInput, filterDropdown, {
      limit: 6,
      onSelect: (item) => {
        applyQueryFilter(item.query);
      }
    });
  }
}

// ==========================================================================
// 14. Export global window.app methods immediately
// ==========================================================================
Object.assign(window.app, {
  setViewMode,
  setFilterChip,
  toggleFav,
  vanishLot,
  restoreLot,
  openLotModal,
  openDetails,
  openAvito,
  openNewSearchModal,
  closeAllModals,
  promptDelete,
  promptDeleteCurrent,
  confirmDelete: handleConfirmDelete,
  selectSearch,
  scanSearch,
  expandSearchToRussia,
  resetMinPrice,
  setQueryPreset,
  quickAddPreset,
  toggleExcludeAccessories,
  applyQueryFilter
});

// ==========================================================================
// 15. Bootstrap
// ==========================================================================
async function startApp() {
  initDOM();
  TelegramService.init();
  await SafeStorage.initCloudSync();
  setupEventListeners();
  await loadData();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startApp);
} else {
  startApp();
}
