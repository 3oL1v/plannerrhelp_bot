export function getTelegramWebApp() {
  return window.Telegram?.WebApp;
}

export function getBootstrapPayload() {
  const webApp = getTelegramWebApp();
  webApp?.ready();
  webApp?.expand();
  const unsafeUser = webApp?.initDataUnsafe?.user;

  return {
    init_data: webApp?.initData || null,
    telegram_id: unsafeUser?.id ?? null,
    username: unsafeUser?.username ?? null,
    first_name: unsafeUser?.first_name ?? null,
    last_name: unsafeUser?.last_name ?? null
  };
}
