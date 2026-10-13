# 🛰️ AvitoRadar — Telegram Mini App & Automated Deals Watchdog

Премиальный инструмент для мониторинга выгодных предложений на Авито с автоотслеживанием 24/7, встроенной аналитикой рынка и интеграцией с Telegram Bot API.

Дизайн разработан в стиле **Linear, Vercel, Stripe** (темная тема `#0A0A0B`, акценты Indigo `#6366F1` и Emerald `#10B981`, шрифты Inter + JetBrains Mono).

---

## 📸 Возможности

* 🎯 **Автоотслеживание 24/7**: создавайте любые поисковые запросы по товарам и городам. Бот в фоне парсит Авито и отправляет мгновенные карточки в Telegram только при появлении выгодных лотов.
* 👁️ **Функция "Vanish" (Скрыть шлак)**: скрытие нерелевантных объявлений и байт-цен в один тап с плавной анимацией и запоминанием на сервере.
* 📊 **Честный расчет медианы рынка**: алгоритм отсекает дефектные товары, запчасти, чехлы и сборные лоты, высчитывая реальную скидку (например, `🔥 ВЫГОДА -35%`).
* 📱 **Telegram Mini App (iOS & Android)**: запускается прямо внутри Telegram через кнопку меню (`⚡ Радар`) или команду `/start`.
* ⚡ **Таблица и Карточки**: встроенная таблица лотов как замена Excel прямо на экране смартфона.
* 🚀 **Production-Ready деплой на Render**: автоматическая сборка и деплой при каждом push в ветку `main`.

---

## 📁 Структура проекта

```
avitoradar/
├── frontend/                     # Статический фронтенд Mini App
│   ├── index.html                # Семантическая разметка (Inter + JetBrains Mono)
│   ├── css/
│   │   └── styles.css            # Дизайн-система (Linear / Vercel dark theme)
│   ├── js/
│   │   ├── app.js                # Контроллер приложения и логика Vanish
│   │   ├── api.js                # REST API клиент + LocalStorage offline-first
│   │   └── telegram.js           # Telegram WebApp SDK интеграция и Haptic Feedback
│   └── assets/                   # Иконки и графические материалы
├── backend/                      # Node.js + Express API сервер
│   ├── server.js                 # Главный сервер, health check, cron job
│   ├── routes/
│   │   ├── searches.js           # Эндпоинты /api/searches
│   │   └── lots.js               # Эндпоинты /api/lots и /api/lots/:id/dismiss
│   ├── services/
│   │   ├── avito-scraper.js      # Сканер Авито и фоновый watchdog
│   │   ├── market-price.js       # Очищенный расчет рыночной медианы
│   │   └── telegram-bot.js       # Интеграция с Telegram Bot API
│   ├── models/
│   │   ├── Search.js             # Модель поисковых запросов с дисковым кешем
│   │   └── Lot.js                # Модель объявлений с поддержкой флага Vanish
│   └── utils/
│       └── helpers.js            # Транслитерация, слаги и форматирование
├── package.json                  # Зависимости Node.js
├── render.yaml                   # Конфигурация Blueprint для деплоя на Render
├── index.html                    # Root копия для деплоя на GitHub Pages
└── README.md
```

---

## 🛠️ API Reference

### 1. Поисковые запросы (Searches)
* `GET /api/searches` — получить список активных радаров.
* `POST /api/searches` — создать новый радар:
  ```json
  {
    "query": "RX 6700 XT",
    "city": "chelyabinsk",
    "minPrice": 20000,
    "filters": {
      "noDefects": true,
      "privateSellers": false,
      "withDelivery": false
    }
  }
  ```
* `DELETE /api/searches/:id` — удалить радар из базы и остановить мониторинг.
* `POST /api/searches/:id/scan` — запустить немедленное сканирование Авито.

### 2. Объявления (Lots)
* `GET /api/lots` — получить список объявлений с фильтрами:
  * `searchId` — ID радара (или `all`)
  * `onlyProfit=true` — только выгодные предложения (ниже рынка)
  * `privateSellers=true` — только частные продавцы
  * `withDelivery=true` — с Авито Доставкой
  * `noDefects=true` — без дефектов и запчастей
  * `includeDismissed=true` — показать скрытые объявления (Vanish)
  * `q` — поиск по ключевым словам
  * `sort` — `deal` (по выгоде), `cheap` (дешевле), `expensive` (дороже), `date` (новые)
* `POST /api/lots/:id/dismiss` — скрыть объявление (Vanish).
* `POST /api/lots/:id/restore` — восстановить скрытое объявление.

### 3. Мониторинг и Health Check
* `GET /health` — проверка работоспособности сервера:
  ```json
  { "status": "ok", "service": "avitoradar-backend", "timestamp": 1728867200000 }
  ```

---

## 🚀 Пошаговое руководство по деплою на Render

### Вариант А: Быстрый деплой через Render Blueprint (рекомендуется)

1. Зайдите в [Render Dashboard](https://dashboard.render.com/).
2. Нажмите **New +** в правом верхнем углу → выберите **Blueprint**.
3. Подключите ваш репозиторий GitHub `Steelsv/avito-radar`.
4. Render автоматически прочитает файл `render.yaml` и создаст два сервиса:
   * **`avitoradar-backend`** (Web Service, Node.js)
   * **`avitoradar-frontend`** (Static Site)
5. В разделе Environment Variables укажите:
   * `TELEGRAM_BOT_TOKEN` — токен вашего Telegram-бота (от `@BotFather`)
   * `TELEGRAM_CHAT_ID` — ваш ID чата в Telegram (куда отправлять алерты)
   * `MINI_APP_URL` — ссылка на фронтенд (например: `https://steelsv.github.io/avito-radar/` или URL на Render)
6. Нажмите **Apply** — проект автоматически соберется и запустится!

---

### Вариант Б: Ручной деплой Web Service

1. В Render Dashboard нажмите **New +** → **Web Service**.
2. Выберите репозиторий `Steelsv/avito-radar`.
3. Заполните параметры:
   * **Name:** `avitoradar-backend`
   * **Runtime:** `Node`
   * **Branch:** `main`
   * **Build Command:** `npm install`
   * **Start Command:** `node backend/server.js`
   * **Instance Type:** `Free`
4. Добавьте Environment Variables:
   * `NODE_ENV` = `production`
   * `TELEGRAM_BOT_TOKEN` = `ваш_токен_бота`
   * `TELEGRAM_CHAT_ID` = `ваш_chat_id`
   * `MINI_APP_URL` = `https://steelsv.github.io/avito-radar/`
5. В разделе **Health Check Path** укажите `/health`.
6. Включите **Auto-Deploy on Commit**: при каждом `git push` Render будет автоматически обновлять сервис.

---

## 📱 Настройка Telegram Mini App

1. Откройте диалог с `@BotFather` в Telegram.
2. Отправьте команду `/mybots` и выберите вашего бота.
3. Перейдите в **Bot Settings** → **Menu Button** → **Configure menu button**.
4. Укажите URL: `https://steelsv.github.io/avito-radar/` (или домен на Render).
5. Текст кнопки: `⚡ Радар`.
6. Теперь при открытии бота у всех пользователей в левом нижнем углу будет кнопка запуска терминала!

---

## 💻 Локальный запуск (для разработки)

```bash
# Установка зависимостей
npm install

# Запуск сервера в режиме разработки
npm run dev

# Приложение будет доступно по адресу: http://localhost:3000
```
