const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const { formatPrice } = require('../utils/helpers');

let botInstance = null;
let targetChatId = process.env.TELEGRAM_CHAT_ID || null;

function getBotToken() {
  if (process.env.TELEGRAM_BOT_TOKEN) return process.env.TELEGRAM_BOT_TOKEN;

  // Try loading from config.json or data/config.json
  const paths = [
    path.resolve(__dirname, '../../data/config.json'),
    path.resolve(__dirname, '../../config.json')
  ];
  for (const p of paths) {
    if (fs.existsSync(p)) {
      try {
        const data = JSON.parse(fs.readFileSync(p, 'utf-8'));
        if (data.telegram?.token) {
          if (data.telegram?.chat_id && !targetChatId) targetChatId = data.telegram.chat_id;
          return data.telegram.token;
        }
      } catch (_) {}
    }
  }
  // Default fallback token
  return '5928342984:AAHRFliTSZwTaRYcp4m6Tkl0SCDtWnvN2mA';
}

function initTelegramBot() {
  const token = getBotToken();
  if (!token) {
    console.warn('[TelegramBot] No bot token provided. Bot notifications disabled.');
    return null;
  }

  if (botInstance) return botInstance;

  try {
    // In production or when polling disabled, use webhook or send-only mode to prevent conflict
    const isPolling = process.env.ENABLE_TG_POLLING === 'true';
    botInstance = new TelegramBot(token, { polling: isPolling });

    console.log(`[TelegramBot] Initialized with token prefix: ${token.substring(0, 10)}... (polling=${isPolling})`);

    const miniappUrl = process.env.MINI_APP_URL || 'https://steelsv.github.io/avito-radar/';

    if (isPolling) {
      botInstance.onText(/\/start/, (msg) => {
        const chatId = msg.chat.id;
        const welcomeText = 
          `👁️ <b>СМОТРЯЩИЙ ЗА АВИТО // RADAR TERMINAL</b>\n\n` +
          `⚡ <b>Интерактивный терминал готов к работе:</b>\n` +
          `• 🎯 Менеджер поисков: создание и удаление любых радаров\n` +
          `• 👁️ Функция <b>Vanish</b>: скрытие нерелевантных объявлений в 1 тап\n` +
          `• 🎴 Карточки с фильтрацией дефектов и байт-цен\n` +
          `• 📊 Встроенная таблица (замена Excel на iPhone)\n\n` +
          `<i>В этот чат приходят только мгновенные алерты о супер-ценах.</i>\n\n` +
          `Нажмите кнопку ниже, чтобы открыть терминал 👇`;

        botInstance.sendMessage(chatId, welcomeText, {
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [
                { text: '⚡ ОТКРЫТЬ ТЕРМИНАЛ (MINI APP)', web_app: { url: miniappUrl } }
              ]
            ]
          }
        });
      });
    }

    return botInstance;
  } catch (err) {
    console.error('[TelegramBot] Initialization error:', err.message);
    return null;
  }
}

async function sendDealAlert(chatId, lot) {
  const token = getBotToken();
  if (!token) return false;

  const targetId = chatId || targetChatId || '1492667315';
  const miniappUrl = process.env.MINI_APP_URL || 'https://steelsv.github.io/avito-radar/';

  const sellerRatingText = lot.seller?.rating ? `★ ${lot.seller.rating}` : '';
  const sellerTypeText = lot.seller?.type === 'private' ? '👤 Частник' : '🏬 Магазин';
  const locationText = lot.seller?.location || 'Челябинск';
  const marketText = lot.marketPrice ? `${formatPrice(lot.marketPrice)}` : 'определяется';
  const diffSign = lot.discount <= 0 ? '' : '+';

  const caption = 
    `🔥 <b>Новое выгодное предложение!</b>\n\n` +
    `<b>${escapeHtml(lot.title)}</b>\n` +
    `💰 <b>${formatPrice(lot.price)}</b> (рынок: ${marketText})\n` +
    `📉 Выгода: <b>${diffSign}${lot.discount}%</b>\n\n` +
    `${sellerTypeText} ${sellerRatingText}\n` +
    `📍 ${escapeHtml(locationText)}`;

  const keyboard = {
    inline_keyboard: [
      [
        { text: '⚡ Открыть в терминале', web_app: { url: miniappUrl } },
        { text: '👉 На Авито', url: lot.avitoUrl }
      ]
    ]
  };

  try {
    const url = `https://api.telegram.org/bot${token}`;
    const axios = require('axios');

    if (lot.images && lot.images.length > 0) {
      await axios.post(`${url}/sendPhoto`, {
        chat_id: targetId,
        photo: lot.images[0],
        caption: caption,
        parse_mode: 'HTML',
        reply_markup: keyboard
      }, { timeout: 15000 });
    } else {
      await axios.post(`${url}/sendMessage`, {
        chat_id: targetId,
        text: caption,
        parse_mode: 'HTML',
        reply_markup: keyboard
      }, { timeout: 15000 });
    }
    return true;
  } catch (err) {
    console.error('[TelegramBot] Error sending alert:', err.response?.data || err.message);
    return false;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

module.exports = {
  initTelegramBot,
  sendDealAlert
};
