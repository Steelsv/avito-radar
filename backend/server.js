require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const cron = require('node-cron');

const searchesRouter = require('./routes/searches');
const lotsRouter = require('./routes/lots');
const { initTelegramBot } = require('./services/telegram-bot');
const { runPeriodicWatch } = require('./services/avito-scraper');
const LotModel = require('./models/Lot');
const SearchModel = require('./models/Search');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve frontend static files
const frontendDir = path.resolve(__dirname, '../frontend');
app.use(express.static(frontendDir));

// Also serve web/ or root static files for fallback
app.use(express.static(path.resolve(__dirname, '../')));

// Health check endpoint (Required by Render & monitoring)
app.get(['/health', '/api/health', '/healthz'], (req, res) => {
  res.json({
    status: 'ok',
    service: 'avitoradar-backend',
    timestamp: Date.now(),
    uptime: process.uptime()
  });
});

// API Routes
app.use('/api/searches', searchesRouter);
app.use('/api/lots', lotsRouter);

// Compatibility route: GET /api/bundle (compiles searches & lots for legacy / quick loads)
app.get('/api/bundle', (req, res) => {
  try {
    const searches = SearchModel.getAll();
    const bundle = {};

    searches.forEach(s => {
      const items = LotModel.getAll({ searchId: s.id });
      bundle[s.id] = {
        name: s.id,
        title: s.query,
        city: s.city,
        min_price: s.minPrice,
        category_type: 'goods',
        items: items.map(it => ({
          id: it.id,
          title: it.title,
          price: it.price,
          price_formatted: `${it.price.toLocaleString('ru-RU')} ₽`,
          market_price: it.marketPrice,
          market_diff_percent: it.discount,
          real_price_in_desc: it.realPriceInDesc,
          is_combo_listing: it.isComboListing,
          url: it.avitoUrl,
          address: it.seller.location,
          city: s.city,
          published_text: it.publishedText || 'сегодня',
          seller_name: it.seller.name,
          seller_type: it.seller.type === 'private' ? 'частное лицо' : 'Компания',
          seller_rating: it.seller.rating,
          images: it.images,
          description: it.description,
          tags: it.tags,
          badges: it.badges
        }))
      };
    });

    res.json(bundle);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Fallback HTML router: send frontend/index.html
app.get('*', (req, res, next) => {
  if (req.path.startsWith('/api')) return next();
  const indexHtml = path.join(frontendDir, 'index.html');
  if (require('fs').existsSync(indexHtml)) {
    return res.sendFile(indexHtml);
  }
  res.sendFile(path.resolve(__dirname, '../index.html'));
});

// Initialize services
initTelegramBot();

// Schedule automated watchdog (runs every 3 minutes)
cron.schedule('*/3 * * * *', async () => {
  console.log('[Cron] Running scheduled watch check for deals...');
  try {
    await runPeriodicWatch();
  } catch (err) {
    console.error('[Cron] Periodic watch error:', err.message);
  }
});

// Start Server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`===============================================`);
  console.log(`⚡ AvitoRadar Backend running on port ${PORT}`);
  console.log(`📡 Healthcheck: http://localhost:${PORT}/health`);
  console.log(`🎯 API Searches: http://localhost:${PORT}/api/searches`);
  console.log(`📦 API Lots: http://localhost:${PORT}/api/lots`);
  console.log(`===============================================`);
});
