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

// Custom Telegram Emojis (Telegram iOS Icons pack: https://emoji.wivvi.net / tgiosicons)
const TG_EMOJI = {
  LIGHTNING: '5884428842780594914', // ⚡
  LINK: '6028171274939797252',      // 🔗
  RADAR: '6037397706505195857',     // 👁
  SEARCH: '6032850693348399258',    // 🔎
  PROFILE: '6035084557378654059',   // 👤
  PIN: '6042011682497106307',       // 📍
  STAR: '6034923938486684992',      // ⭐️
  CHECK: '5774022692642492953',     // ✅
  WARN: '6030563507299160824',      // ❗️
  TRASH: '6039522349517115015',     // 🗑
  GROWTH: '5938539885907415367',    // 📈
  COIN: '5890848474563352982',      // 🪙
  BOX: '5884479287171485878',       // 📦
  SHIELD: '6030445631921721471'     // 🛡
};

function tgEmoji(id, fallback) {
  return `<tg-emoji emoji-id="${id}">${fallback}</tg-emoji>`;
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
          `${tgEmoji(TG_EMOJI.RADAR, '👁')} <b>СМОТРЯЩИЙ ЗА АВИТО // RADAR TERMINAL</b>\n\n` +
          `${tgEmoji(TG_EMOJI.LIGHTNING, '⚡')} <b>Интерактивный терминал готов к работе:</b>\n` +
          `• ${tgEmoji(TG_EMOJI.SEARCH, '🔎')} Менеджер поисков: создание и удаление любых радаров\n` +
          `• ${tgEmoji(TG_EMOJI.RADAR, '👁')} Функция <b>Vanish</b>: скрытие нерелевантных объявлений в 1 тап\n` +
          `• ${tgEmoji(TG_EMOJI.SHIELD, '🛡')} Карточки с фильтрацией дефектов и байт-цен\n` +
          `• ${tgEmoji(TG_EMOJI.GROWTH, '📈')} Встроенная таблица (замена Excel на iPhone)\n\n` +
          `<i>В этот чат приходят только мгновенные алерты о супер-ценах.</i>\n\n` +
          `Нажмите кнопку ниже, чтобы открыть терминал 👇`;

        botInstance.sendMessage(chatId, welcomeText, {
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: 'ОТКРЫТЬ ТЕРМИНАЛ (MINI APP)',
                  web_app: { url: miniappUrl },
                  icon_custom_emoji_id: TG_EMOJI.LIGHTNING
                }
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

  const eGrowth = tgEmoji(TG_EMOJI.GROWTH, '📈');
  const eCoin = tgEmoji(TG_EMOJI.COIN, '🪙');
  const ePin = tgEmoji(TG_EMOJI.PIN, '📍');
  const eProfile = tgEmoji(TG_EMOJI.PROFILE, '👤');
  const eStar = tgEmoji(TG_EMOJI.STAR, '⭐️');

  const sellerRatingText = lot.seller?.rating ? `(${eStar} ${lot.seller.rating})` : '';
  const sellerTypeText = lot.seller?.type === 'private' ? `${eProfile} Частник` : `${eProfile} Магазин`;
  const locationText = lot.seller?.location || 'Челябинск';
  const marketText = lot.marketPrice ? `${formatPrice(lot.marketPrice)}` : 'определяется';
  const diffSign = lot.discount <= 0 ? '' : '+';

  const caption = 
    `${eGrowth} <b>Новое выгодное предложение!</b>\n\n` +
    `<b>${escapeHtml(lot.title)}</b>\n` +
    `${eCoin} <b>${formatPrice(lot.price)}</b> (рынок: ${marketText})\n` +
    `${eGrowth} Выгода: <b>${diffSign}${lot.discount}%</b>\n\n` +
    `${sellerTypeText} ${sellerRatingText}\n` +
    `${ePin} ${escapeHtml(locationText)}`;

  const keyboard = {
    inline_keyboard: [
      [
        {
          text: 'Открыть в терминале',
          web_app: { url: miniappUrl },
          icon_custom_emoji_id: TG_EMOJI.LIGHTNING
        },
        {
          text: 'На Авито',
          url: lot.avitoUrl,
          icon_custom_emoji_id: TG_EMOJI.LINK
        }
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
