const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const LotModel = require('../models/Lot');
const SearchModel = require('../models/Search');
const { annotateLotsWithMarket } = require('./market-price');
const { sendDealAlert } = require('./telegram-bot');

const ROOT_DIR = path.resolve(__dirname, '../../');
const DATA_DIR = path.join(ROOT_DIR, 'data');

async function scanSearch(search) {
  if (!search) return 0;
  console.log(`[AvitoScraper] Scanning search: ${search.query} (${search.city})...`);

  return new Promise((resolve) => {
    // 1. Try running Python scanner
    const cmd = `python -u run.py scan ${search.id} --pages 1`;
    exec(cmd, { cwd: ROOT_DIR, timeout: 45000 }, (error, stdout, stderr) => {
      if (error) {
        console.warn(`[AvitoScraper] Python scan notice (${search.id}): ${error.message}`);
      } else {
        console.log(`[AvitoScraper] Python scan completed for ${search.id}`);
      }

      // 2. Read back updated listings
      const listFile = path.join(DATA_DIR, 'searches', search.id, 'listings.json');
      if (fs.existsSync(listFile)) {
        try {
          const rawItems = JSON.parse(fs.readFileSync(listFile, 'utf-8'));
          const freshLots = [];
          for (const raw of Object.values(rawItems)) {
            const lot = LotModel.normalizeRawItem(raw, search.id);
            if (lot) {
              LotModel.upsert(lot);
              freshLots.push(lot);
            }
          }

          // Annotate with market prices
          annotateLotsWithMarket(freshLots);
          LotModel.saveToDisk();

          // Check for top deals to alert
          for (const lot of freshLots) {
            if (lot.discount <= -15 && !lot.isComboListing && !lot.isDismissed && !lot.notifiedAt) {
              sendDealAlert(null, lot);
              lot.notifiedAt = Date.now();
            }
          }

          SearchModel.update(search.id, { lastCheckedAt: Date.now() });
          resolve(freshLots.length);
          return;
        } catch (err) {
          console.error('[AvitoScraper] Error reading listings file:', err.message);
        }
      }

      resolve(0);
    });
  });
}

async function runPeriodicWatch() {
  const searches = SearchModel.getAll().filter(s => s.isActive);
  console.log(`[AvitoScraper] Periodic check: ${searches.length} active searches`);

  for (const s of searches) {
    try {
      await scanSearch(s);
    } catch (err) {
      console.warn(`[AvitoScraper] Error in watch for ${s.id}:`, err.message);
    }
  }
}

module.exports = {
  scanSearch,
  runPeriodicWatch
};
