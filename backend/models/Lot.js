const fs = require('fs');
const path = require('path');

const DATA_DIR = path.resolve(__dirname, '../../data');
const DISMISSED_FILE = path.join(DATA_DIR, 'dismissed.json');
const LOTS_CACHE_FILE = path.join(DATA_DIR, 'lots_cache.json');

class LotModel {
  constructor() {
    this.lots = new Map(); // id -> lot
    this.dismissedIds = new Set();
    this.loadDismissedFromDisk();
    this.loadFromDisk();
  }

  loadDismissedFromDisk() {
    if (fs.existsSync(DISMISSED_FILE)) {
      try {
        const raw = fs.readFileSync(DISMISSED_FILE, 'utf-8');
        const list = JSON.parse(raw);
        if (Array.isArray(list)) {
          list.forEach(id => this.dismissedIds.add(String(id)));
        }
      } catch (err) {
        console.error('[LotModel] Error loading dismissed.json:', err.message);
      }
    }
  }

  saveDismissedToDisk() {
    try {
      fs.writeFileSync(DISMISSED_FILE, JSON.stringify(Array.from(this.dismissedIds), null, 2), 'utf-8');
    } catch (err) {
      console.error('[LotModel] Error saving dismissed.json:', err.message);
    }
  }

  loadFromDisk() {
    // 1. Load from lots_cache.json if exists
    if (fs.existsSync(LOTS_CACHE_FILE)) {
      try {
        const raw = fs.readFileSync(LOTS_CACHE_FILE, 'utf-8');
        const items = JSON.parse(raw);
        if (Array.isArray(items)) {
          items.forEach(it => {
            const strId = String(it.id);
            it.isDismissed = this.dismissedIds.has(strId);
            this.lots.set(strId, it);
          });
        }
      } catch (err) {
        console.error('[LotModel] Error loading lots_cache.json:', err.message);
      }
    }

    // 2. Discover from python scraper listings folders: data/searches/*/listings.json
    const searchesFolder = path.join(DATA_DIR, 'searches');
    if (fs.existsSync(searchesFolder)) {
      try {
        const folders = fs.readdirSync(searchesFolder, { withFileTypes: true });
        for (const f of folders) {
          if (f.isDirectory()) {
            const listFile = path.join(searchesFolder, f.name, 'listings.json');
            if (fs.existsSync(listFile)) {
              try {
                const raws = JSON.parse(fs.readFileSync(listFile, 'utf-8'));
                for (const raw of Object.values(raws)) {
                  const lot = this.normalizeRawItem(raw, f.name);
                  if (lot && !this.lots.has(lot.id)) {
                    this.lots.set(lot.id, lot);
                  }
                }
              } catch (_) {}
            }
          }
        }
      } catch (err) {
        console.error('[LotModel] Error scanning listings folders:', err.message);
      }
    }
  }

  normalizeRawItem(raw, searchId) {
    if (!raw || !raw.id) return null;
    const strId = String(raw.id);
    const price = Number(raw.price) || 0;
    const isDismissed = this.dismissedIds.has(strId);

    // Parse images
    let images = [];
    if (raw.images && Array.isArray(raw.images)) {
      images = raw.images.map(img => (typeof img === 'string' ? img : img.url || '')).filter(Boolean);
    }

    return {
      id: strId,
      searchId: searchId || raw.searchId || 'general',
      avitoUrl: raw.url || `https://www.avito.ru/${raw.id}`,
      title: raw.title || 'Объявление на Авито',
      price: price,
      marketPrice: Number(raw.market_price || raw.marketPrice) || 0,
      discount: Number(raw.market_diff_percent || raw.discount) || 0,
      seller: {
        name: raw.seller_name || raw.seller?.name || 'Частное лицо',
        type: (raw.seller_type || raw.seller?.type || '').toLowerCase().includes('компан') || (raw.tags && raw.tags.some(t => t.includes('Магазин'))) ? 'business' : 'private',
        rating: Number(raw.seller_rating || raw.seller?.rating) || null,
        location: raw.address || raw.city || raw.seller?.location || 'Челябинск'
      },
      postedAt: Date.now() - (Math.floor(Math.random() * 3600000) * 4),
      publishedText: raw.published_text || raw.publishedText || 'сегодня',
      isDismissed: isDismissed,
      notifiedAt: null,
      images: images.slice(0, 4),
      description: raw.description || '',
      tags: raw.tags || [],
      badges: raw.badges || [],
      isComboListing: Boolean(raw.is_combo_listing || raw.isComboListing),
      isAccessory: Boolean(raw.is_accessory || raw.isAccessory || (raw.tags && raw.tags.some(t => t.includes('Аксессуар') || t.includes('Велозапчасть') || t.includes('Автоаксессуар')))),
      realPriceInDesc: Number(raw.real_price_in_desc || raw.realPriceInDesc) || null
    };
  }

  saveToDisk() {
    try {
      const list = Array.from(this.lots.values());
      fs.writeFileSync(LOTS_CACHE_FILE, JSON.stringify(list, null, 2), 'utf-8');
    } catch (err) {
      console.error('[LotModel] Error saving lots_cache.json:', err.message);
    }
  }

  getAll(filters = {}) {
    let result = Array.from(this.lots.values());

    // By default, exclude dismissed lots unless explicitly requested
    if (!filters.includeDismissed) {
      result = result.filter(l => !l.isDismissed);
    }

    // Filter by searchId
    if (filters.searchId && filters.searchId !== 'all') {
      result = result.filter(l => l.searchId === filters.searchId);
    }

    // Filter: only profit
    if (filters.onlyProfit) {
      result = result.filter(l => l.discount <= -12 && !l.isComboListing && !l.isAccessory);
    }

    // Filter: private sellers only
    if (filters.privateSellers) {
      result = result.filter(l => l.seller.type === 'private');
    }

    // Filter: with delivery
    if (filters.withDelivery) {
      result = result.filter(l => (l.badges || []).some(b => b.toLowerCase().includes('доставка')));
    }

    // Filter: no accessories
    if (filters.noAccessories) {
      result = result.filter(l => !l.isAccessory && !(l.tags || []).some(t => t.includes('Аксессуар') || t.includes('Велозапчасть') || t.includes('Автоаксессуар')));
    }

    // Filter: no defects
    if (filters.noDefects) {
      result = result.filter(l => !(l.tags || []).some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное')));
    }

    // Keyword search
    if (filters.q) {
      const qLower = filters.q.toLowerCase().trim();
      result = result.filter(l =>
        l.title.toLowerCase().includes(qLower) ||
        (l.description && l.description.toLowerCase().includes(qLower)) ||
        (l.seller.name && l.seller.name.toLowerCase().includes(qLower)) ||
        (l.seller.location && l.seller.location.toLowerCase().includes(qLower))
      );
    }

    // Sort: by default by discount (top profit deals first) or date
    if (filters.sort === 'cheap') {
      result.sort((a, b) => a.price - b.price);
    } else if (filters.sort === 'expensive') {
      result.sort((a, b) => b.price - a.price);
    } else if (filters.sort === 'date') {
      result.sort((a, b) => b.postedAt - a.postedAt);
    } else {
      // 'deal' (profit)
      result.sort((a, b) => (a.discount || 999) - (b.discount || 999));
    }

    return result;
  }

  getById(id) {
    return this.lots.get(String(id)) || null;
  }

  dismiss(id) {
    const strId = String(id);
    this.dismissedIds.add(strId);
    this.saveDismissedToDisk();

    const lot = this.lots.get(strId);
    if (lot) {
      lot.isDismissed = true;
    }
    return true;
  }

  restore(id) {
    const strId = String(id);
    this.dismissedIds.delete(strId);
    this.saveDismissedToDisk();

    const lot = this.lots.get(strId);
    if (lot) {
      lot.isDismissed = false;
    }
    return true;
  }

  upsert(lot) {
    if (!lot || !lot.id) return;
    const strId = String(lot.id);
    lot.isDismissed = this.dismissedIds.has(strId);
    this.lots.set(strId, lot);
  }
}

module.exports = new LotModel();
