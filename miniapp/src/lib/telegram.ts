const TELEGRAM_SDK_URL = "https://telegram.org/js/telegram-web-app.js";
const TELEGRAM_SDK_ID = "telegram-webapp-sdk";

export function getTelegramWebApp() {
  return window.Telegram?.WebApp;
}

async function ensureTelegramSdk() {
  if (getTelegramWebApp()) {
    return;
  }

  const existingScript = document.getElementById(TELEGRAM_SDK_ID) as HTMLScriptElement | null;
  if (existingScript) {
    await new Promise<void>((resolve, reject) => {
      if (getTelegramWebApp()) {
        resolve();
        return;
      }
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Telegram SDK")), { once: true });
    });
    return;
  }

  await new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.id = TELEGRAM_SDK_ID;
    script.src = TELEGRAM_SDK_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Telegram SDK"));
    document.head.appendChild(script);
  });
}

function buildPayload() {
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

export async function getBootstrapPayload() {
  await ensureTelegramSdk().catch(() => undefined);
  const startedAt = Date.now();
  const timeoutMs = 1500;

  while (Date.now() - startedAt < timeoutMs) {
    const payload = buildPayload();
    if (payload.init_data) {
      return payload;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 100));
  }

  return buildPayload();
}
