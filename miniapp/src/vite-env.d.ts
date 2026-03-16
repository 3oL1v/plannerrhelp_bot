/// <reference types="vite/client" />

interface TelegramWebAppUser {
  id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
}

interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  close: () => void;
  colorScheme?: "light" | "dark";
  initDataUnsafe?: {
    user?: TelegramWebAppUser;
  };
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
