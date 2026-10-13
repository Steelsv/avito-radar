/**
 * Telegram WebApp Integration helper.
 */

const tg = window.Telegram?.WebApp;

export const TelegramService = {
  init() {
    if (!tg) {
      console.log('[TelegramService] Running in standalone web browser mode');
      return;
    }

    try {
      tg.ready();
      tg.expand();
      tg.headerColor = '#0A0A0B';
      tg.backgroundColor = '#0A0A0B';

      // Set viewport settings if supported
      if (tg.isVerticalSwipesEnabled !== undefined) {
        tg.isVerticalSwipesEnabled = true;
      }
    } catch (e) {
      console.warn('[TelegramService] Init error:', e);
    }
  },

  haptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    try {
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
      else if (type === 'heavy') tg.HapticFeedback.impactOccurred('heavy');
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
