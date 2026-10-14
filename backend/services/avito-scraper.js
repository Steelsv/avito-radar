const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const LotModel = require('../models/Lot');
const SearchModel = require('../models/Search');
const { annotateLotsWithMarket } = require('./market-price');
const { sendDealAlert } = require('./telegram-bot');

const ROOT_DIR = path.resolve(__dirname, '../../');
const DATA_DIR = path.join(ROOT_DIR, 'data');

/**
 * Executes a single search scan with strict timeout and crash protection.
 * @param {Object} search Search model object
 * @returns {Promise<number>} Number of parsed/updated lots
 */
async function scanSearch(search) {
  if (!search || !search.id) return 0;
  console.log(`[AvitoScraper] Scanning search: «${search.query}» (${search.city || 'rossiya'})...`);

  return new Promise((resolve) => {
    // 1. Run Python scanner with 45s hard timeout and SIGTERM
    const cmd = `python -u run.py scan "${search.id}" --pages 1`;
    const execOptions = {
      cwd: ROOT_DIR,
      timeout: 45000,
      killSignal: 'SIGTERM',
      maxBuffer: 1024 * 1024 * 4
    };

    exec(cmd, execOptions, (error, stdout, stderr) => {
      if (error) {
        if (error.killed) {
          console.warn(`[AvitoScraper] Scan for «${search.id}» timed out after 45s (process terminated gracefully)`);
        } else {
          console.warn(`[AvitoScraper] Python scanner notice for «${search.id}»: ${error.message}`);
        }
      } else {
        console.log(`[AvitoScraper] Python scan completed successfully for «${search.id}»`);
      }

      // 2. Safely read back updated listings
      const listFile = path.join(DATA_DIR, 'searches', search.id, 'listings.json');
      if (fs.existsSync(listFile)) {
        try {
          const rawContent = fs.readFileSync(listFile, 'utf-8');
          if (!rawContent || !rawContent.trim()) {
            resolve(0);
            return;
          }

          const rawItems = JSON.parse(rawContent);
          const freshLots = [];

          for (const raw of Object.values(rawItems)) {
            try {
              const lot = LotModel.normalizeRawItem(raw, search.id);
              if (lot) {
                LotModel.upsert(lot);
                freshLots.push(lot);
              }
            } catch (itemErr) {
              console.warn(`[AvitoScraper] Skipped malformed item in ${search.id}:`, itemErr.message);
            }
          }

          // Annotate with market prices
          try {
            annotateLotsWithMarket(freshLots);
            LotModel.saveToDisk();
          } catch (marketErr) {
            console.warn(`[AvitoScraper] Market price annotation notice:`, marketErr.message);
          }

          // Check for top deals to alert
          for (const lot of freshLots) {
            try {
              if (lot.discount <= -15 && !lot.isComboListing && !lot.isDismissed && !lot.notifiedAt) {
                sendDealAlert(null, lot);
                lot.notifiedAt = Date.now();
              }
            } catch (alertErr) {
              console.warn(`[AvitoScraper] Alert dispatch notice:`, alertErr.message);
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

/**
 * Periodic watch loop running every 3 minutes. Never throws uncaught exceptions.
 */
async function runPeriodicWatch() {
  try {
    const searches = SearchModel.getAll().filter(s => s.isActive);
    console.log(`[AvitoScraper] Periodic check: ${searches.length} active searches`);

    for (const s of searches) {
      try {
        await scanSearch(s);
      } catch (err) {
        console.warn(`[AvitoScraper] Handled error in watch for ${s.id}:`, err.message);
      }
    }
  } catch (globalErr) {
    console.error('[AvitoScraper] Fatal guard caught error in runPeriodicWatch:', globalErr.message);
  }
}

module.exports = {
  scanSearch,
  runPeriodicWatch
};
