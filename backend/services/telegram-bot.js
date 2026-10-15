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

    const miniappUrl = process.env.MINI_APP_URL || 'https://avito-radar.onrender.com/';

    if (isPolling) {
      botInstance.onText(/\/start/, (msg) => {
        const chatId = msg.chat.id;
        const welcomeText = 
          `🏛 <b>AVITO RADAR // TERMINAL</b>\n\n` +
          `<i>Премиальный мониторинг выгодных предложений</i>\n\n` +
          `• Поиск товаров и авто с автодополнением\n` +
          `• Функция Vanish: скрытие объявлений в 1 тап и свайпом влево\n` +
          `• Фильтрация дефектов и байт-цен (100 ₽)\n` +
          `• Встроенная интерактивная таблица прямо в Telegram\n\n` +
          `Нажмите кнопку ниже, чтобы открыть терминал 👇`;

        botInstance.sendMessage(chatId, welcomeText, {
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: '⚡️ ТЕРМИНАЛ РАДАРА (MINI APP)',
                  web_app: { url: miniappUrl }
                }
              ]
            ]
          }
        });
      });

      botInstance.onText(/\/status/, (msg) => {
        const chatId = msg.chat.id;
        const uptimeSec = Math.floor(process.uptime());
        const days = Math.floor(uptimeSec / 86400);
        const hours = Math.floor((uptimeSec % 86400) / 3600);
        const mins = Math.floor((uptimeSec % 3600) / 60);
        const secs = uptimeSec % 60;
        const parts = [];
        if (days) parts.push(`${days}д`);
        if (hours) parts.push(`${hours}ч`);
        if (mins) parts.push(`${mins}м`);
        parts.push(`${secs}с`);
        const uptimeStr = parts.join(' ') || '1с';

        const SearchModel = require('../models/Search');
        const LotModel = require('../models/Lot');
        const searches = SearchModel.getAll();
        const lots = LotModel.getAll();

        const statusText =
          `🏛 <b>AVITO RADAR // СТАТУС СЕРВЕРА</b>\n\n` +
          `⏱ <b>Время работы (Uptime):</b> <code>${uptimeStr}</code>\n` +
          `🟢 <b>Мониторинг 24/7:</b> <code>Активен</code> (каждые 3 мин)\n` +
          `🎯 <b>Активных радаров:</b> <code>${searches.length} шт.</code>\n` +
          `📦 <b>Объявлений в базе:</b> <code>${lots.length} шт.</code>\n` +
          `📡 <b>Healthcheck:</b> <code>200 OK</code> (/health)\n\n` +
          `<i>Терминал готов к работе на iOS, Android и Desktop.</i>`;

        botInstance.sendMessage(chatId, statusText, {
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: '⚡️ ТЕРМИНАЛ РАДАРА (MINI APP)',
                  web_app: { url: miniappUrl }
                }
              ]
            ]
          }
        });
      });

      botInstance.onText(/\/avatar/, (msg) => {
        const chatId = msg.chat.id;
        const avatarPath = path.resolve(__dirname, '../../avatar.jpg');
        const caption =
          `🏛 <b>AVITO RADAR // ОФИЦИАЛЬНАЯ АВАТАРКА</b>\n\n` +
          `<i>Новый стиль Heavy Loft & Quiet Luxury</i>\n\n` +
          `• <b>Концепция:</b> Прецизионный хронометр-радар из темного титана со шкалой телеметрии цвета шампанского (#c5a059), сапфировой линзой и визиром.\n\n` +
          `⚙️ <b>Как установить аватарку боту:</b>\n` +
          `1. Откройте @BotFather\n` +
          `2. Отправьте команду <code>/setuserpic</code>\n` +
          `3. Выберите вашего бота <b>@Steelsv_bot</b>\n` +
          `4. Отправьте это изображение как фото`;

        if (fs.existsSync(avatarPath)) {
          botInstance.sendPhoto(chatId, avatarPath, {
            caption,
            parse_mode: 'HTML'
          }).catch(err => {
            console.error('[TelegramBot] Failed to send avatar photo:', err.message);
          });
        } else {
          botInstance.sendMessage(chatId, caption, { parse_mode: 'HTML' });
        }
      });

      botInstance.on('callback_query', async (query) => {
        const data = query.data || '';
        if (data.startsWith('vanish_')) {
          const lotId = data.replace('vanish_', '');
          const LotModel = require('../models/Lot');
          LotModel.dismiss(lotId);
          try {
            await botInstance.answerCallbackQuery(query.id, {
              text: 'Лот скрыт из выдачи ✅',
              show_alert: false
            });
            if (query.message) {
              const currentMarkup = query.message.reply_markup || {};
              const rows = currentMarkup.inline_keyboard || [];
              const updatedRows = rows.map(row =>
                row.map(btn => {
                  if (btn.callback_data === data) {
                    return { text: '👁️ Лот скрыт', callback_data: 'noop' };
                  }
                  return btn;
                })
              );
              await botInstance.editMessageReplyMarkup(
                { inline_keyboard: updatedRows },
                { chat_id: query.message.chat.id, message_id: query.message.message_id }
              );
            }
          } catch (e) {
            console.warn('[TelegramBot] Callback vanish error:', e.message);
          }
        } else if (data === 'noop') {
          try {
            await botInstance.answerCallbackQuery(query.id, { text: 'Лот уже скрыт', show_alert: false });
          } catch (_) {}
        }
      });
    }

    return botInstance;
  } catch (err) {
    console.error('[TelegramBot] Initialization error:', err.message);
    return null;
  }
}

async function sendDealAlert(chatId, lot) {
  if (!lot || lot.isAccessory || lot.isMismatchedModel) return false;
  const token = getBotToken();
  if (!token) return false;

  const targetId = chatId || targetChatId || '1492667315';
  const miniappUrl = process.env.MINI_APP_URL || 'https://avito-radar.onrender.com/';

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
          text: '⚡️ ТЕРМИНАЛ РАДАРА (MINI APP)',
          web_app: { url: miniappUrl }
        }
      ],
      [
        {
          text: '🔗 Открыть на Авито',
          url: lot.avitoUrl
        },
        {
          text: '👁️ Скрыть лот',
          callback_data: `vanish_${lot.id}`
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
