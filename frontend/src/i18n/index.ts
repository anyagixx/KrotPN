// FILE: frontend/src/i18n/index.ts
// VERSION: 1.3.0
// ROLE: UTILITY
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: i18next configuration with Russian default translation resources and legacy English fallback resources
//   SCOPE: Translation dictionary (ru/en), Russian-only i18next initialization for the user frontend, no visible language switch persistence, and Phase-73 truthful config/QR copy
//   DEPENDS: M-009 (frontend-user)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   resources - Translation dictionary with ru and en namespaces
//   i18n - Initialized Russian-default i18next instance (default export)
//   BLOCK_RESOURCES - Translation resources object (~200 lines)
//   BLOCK_I18N_INIT - i18next initialization and export (~15 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.3.0 - Added Phase-77 active-until subscription copy.
//   LAST_CHANGE: v1.2.0 - Added Phase-73 KPN config copy, AmneziaVPN .conf guidance, and tariff-aware device-limit text.
//   LAST_CHANGE: v1.1.0 - Locked user frontend initialization to Russian after removing visible language settings in Phase-72.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_RESOURCES
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

const resources = {
  ru: {
    translation: {
      // Common
      appName: 'KrotPN',
      loading: 'Загрузка...',
      error: 'Ошибка',
      success: 'Успешно',
      save: 'Сохранить',
      cancel: 'Отмена',
      delete: 'Удалить',
      edit: 'Редактировать',
      close: 'Закрыть',
      back: 'Назад',
      next: 'Далее',
      submit: 'Отправить',

      // Auth
      login: 'Войти',
      register: 'Регистрация',
      logout: 'Выйти',
      email: 'Email',
      password: 'Пароль',
      confirmPassword: 'Подтвердите пароль',
      forgotPassword: 'Забыли пароль?',
      noAccount: 'Нет аккаунта?',
      hasAccount: 'Уже есть аккаунт?',
      loginTitle: 'Вход в аккаунт',
      registerTitle: 'Создать аккаунт',
      loginButton: 'Войти',
      registerButton: 'Зарегистрироваться',
      invalidCredentials: 'Неверный логин или пароль',
      registrationSuccess: 'Регистрация успешна!',

      // Navigation
      dashboard: 'Главная',
      config: 'Конфигурация',
      subscription: 'Подписка',
      referrals: 'Рефералы',
      settings: 'Настройки',

      // Dashboard
      welcome: 'Добро пожаловать',
      status: 'Статус',
      connected: 'Подключено',
      disconnected: 'Отключено',
      traffic: 'Трафик',
      upload: 'Отправлено',
      download: 'Получено',
      lastConnection: 'Последнее подключение',
      daysLeft: 'дней осталось',
      subscriptionActive: 'Подписка активна',
      subscriptionExpired: 'Подписка истекла',

      // Config
      vpnConfig: 'KPN Конфигурация',
      downloadConfig: 'Скачать .conf',
      scanQR: 'Сканировать QR',
      qrInstructionsWG: 'Отсканируйте QR-код приложением AmneziaWG',
      qrInstructionsVPN: 'Для AmneziaVPN скачайте .conf и импортируйте его в приложение.',
      configInstructions: 'Импортируйте файл конфигурации в VPN клиент',
      copyConfig: 'Копировать конфиг',
      copied: 'Скопировано!',
      devicesTitle: 'Список ваших устройств',
      devicesListTitle: 'Список ваших устройств',
      devicesListHint: 'Выберите устройство, чтобы скачать именно его конфигурацию.',
      configMasterDetailHint: 'Выберите устройство и нужное действие.',
      devicesActive: 'Активные',
      devicesUsed: 'Занято',
      devicesLimit: 'Лимит',
      devicesEmpty: 'Устройств пока нет',
      devicesEmptyHint: 'Создайте первый конфиг для телефона, ноутбука или домашнего компьютера.',
      selectedDevice: 'Выбранное устройство',
      platformNotSet: 'платформа не указана',
      configLoading: 'Загружаем конфигурацию выбранного устройства.',
      configReady: 'Конфигурация выбранного устройства готова.',
      configUnavailable: 'Конфигурация пока недоступна',
      configLoadFailed: 'Не удалось загрузить конфигурацию',
      tryRefreshLater: 'Попробуйте обновить страницу чуть позже.',
      configDownloaded: 'Конфиг скачан',
      deviceSelectActive: 'Выберите активное устройство',
      deviceSelectPrompt: 'Выберите устройство',
      deviceSelectPromptHint: 'После выбора здесь появятся QR, .conf и Copy.',
      deviceStatusActive: 'active',
      deviceStatusBlocked: 'blocked',
      deviceStatusRevoked: 'revoked',
      deviceSecondaryActions: 'Действия устройства',
      rotateConfig: 'Обновить ключи',
      deleteDevice: 'Удалить',
      newDeviceConfig: 'Новый конфиг для вашего устройства',
      newDeviceHint: 'Создайте отдельный peer под телефон, ноутбук или планшет.',
      deviceNamePlaceholder: 'Например: iPhone 16 Pro',
      deviceNameRequired: 'Введите название устройства',
      deviceLimitReached: 'Лимит устройств исчерпан',
      deviceLimitReachedWithTariff: 'Лимит устройств исчерпан согласно вашему Тарифу - {{tariff}}',
      createDevice: 'Создать устройство',
      deviceCreated: 'Устройство создано и конфиг готов',
      deviceCreateFailed: 'Не удалось создать устройство',
      deviceRotated: 'Ключи устройства обновлены',
      deviceRotateFailed: 'Не удалось обновить ключи',
      deviceRevoked: 'Устройство отозвано',
      deviceRevokeFailed: 'Не удалось отозвать устройство',
      deviceRotateConfirm: 'Обновить ключи этого устройства?',
      deviceRevokeConfirm: 'Удалить это устройство?',
      qrServerUnavailable: 'QR временно недоступен. Попробуйте скачать .conf.',
      name: 'Имя',
      platform: 'Платформа',

      // Subscription
      currentPlan: 'Текущий план',
      choosePlan: 'Выбрать план',
      plans: 'Тарифные планы',
      days: 'дней',
      month: 'месяц',
      months: 'месяцев',
      year: 'год',
      buy: 'Купить',
      extend: 'Продлить',
      trial: 'Пробный период',
      trialDays: '{{days}} дней бесплатно',
      subscriptionDescriptionNone: 'Выберите тариф, оплатите и сразу откройте конфиг.',
      subscriptionDescriptionReferral: 'Бонусные {{days}} дней уже доступны. Таймер стартует после первого подключения.',
      subscriptionDescriptionTrialReferral: 'Конфиг уже доступен. {{days}} дней trial и бонуса стартуют после первого подключения.',
      subscriptionDescriptionPending: 'Конфиг уже доступен. Таймер на 4 дня стартует после первого подключения.',
      subscriptionDescriptionActive: 'Доступ активен до: {{date}}',
      subscriptionDescriptionExpired: 'Продлите подписку, чтобы снова открыть VPN доступ.',
      subscriptionCalendar: 'Календарь подписки',
      subscriptionCalendarPending: 'Даты подсветятся после первого подключения.',
      subscriptionCalendarEmpty: 'Нет активного диапазона подписки.',
      noActiveAccess: 'Нет активного доступа',
      accessExpired: 'Доступ закончился',
      waitingForConnection: 'Ожидает подключения',
      bonusWaitingConnection: 'Бонус ожидает подключения',
      trialBonusWaitingConnection: 'Trial + бонус ожидают',
      activePlansNotPublished: 'Активные планы пока не опубликованы',
      activePlansHint: 'Когда администратор добавит тарифы, они появятся здесь автоматически.',
      popular: 'Популярный',
      devicesCount: '{{count}} устройств',
      devicesOccupied: 'Занято {{used}} из {{limit}}',
      planUnavailable: 'Недоступно',
      planBlockedByDevices: 'Для этого тарифа занято слишком много устройств. Сначала отзовите лишние в разделе конфигураций.',

      // Referrals
      referralProgram: 'Реферальная программа',
      referralCode: 'Ваш реферальный код',
      referralLink: 'Реферальная ссылка',
      referralsCount: 'Приглашено пользователей',
      bonusDays: 'Бонусных дней',
      referralInstructions: 'Пригласите друзей и получите бонусные дни подписки',
      referralBonus: '+{{days}} дней за каждого приглашенного',

      // Settings
      profile: 'Профиль',
      language: 'Язык',
      changePassword: 'Сменить пароль',
      currentPassword: 'Текущий пароль',
      newPassword: 'Новый пароль',
      passwordChanged: 'Пароль изменен',
      personalCabinet: 'Личный кабинет',
      settingsSubtitle: 'Управляйте профилем и безопасностью учётной записи.',
      accountBasics: 'Основные данные аккаунта.',
      namePlaceholder: 'Ваше имя',
      languageSubtitle: 'Переключение языка интерфейса в один клик.',
      passwordSecurityHint: 'Используйте длинный уникальный пароль для защиты аккаунта.',
      passwordTooWeak: 'Пароль слишком простой: {{issues}}',
      russian: 'Русский',
      english: 'English',

      // Errors
      somethingWentWrong: 'Что-то пошло не так',
      networkError: 'Ошибка сети',
      unauthorized: 'Не авторизован',
    },
  },
  en: {
    translation: {
      // Common
      appName: 'KrotPN',
      loading: 'Loading...',
      error: 'Error',
      success: 'Success',
      save: 'Save',
      cancel: 'Cancel',
      delete: 'Delete',
      edit: 'Edit',
      close: 'Close',
      back: 'Back',
      next: 'Next',
      submit: 'Submit',

      // Auth
      login: 'Login',
      register: 'Register',
      logout: 'Logout',
      email: 'Email',
      password: 'Password',
      confirmPassword: 'Confirm password',
      forgotPassword: 'Forgot password?',
      noAccount: "Don't have an account?",
      hasAccount: 'Already have an account?',
      loginTitle: 'Sign in',
      registerTitle: 'Create account',
      loginButton: 'Sign in',
      registerButton: 'Sign up',
      invalidCredentials: 'Invalid email or password',
      registrationSuccess: 'Registration successful!',

      // Navigation
      dashboard: 'Dashboard',
      config: 'Configuration',
      subscription: 'Subscription',
      referrals: 'Referrals',
      settings: 'Settings',

      // Dashboard
      welcome: 'Welcome',
      status: 'Status',
      connected: 'Connected',
      disconnected: 'Disconnected',
      traffic: 'Traffic',
      upload: 'Upload',
      download: 'Download',
      lastConnection: 'Last connection',
      daysLeft: 'days left',
      subscriptionActive: 'Subscription active',
      subscriptionExpired: 'Subscription expired',

      // Config
      vpnConfig: 'KPN Configuration',
      downloadConfig: 'Download .conf',
      scanQR: 'Scan QR',
      qrInstructionsWG: 'Scan QR code with AmneziaWG app',
      qrInstructionsVPN: 'Use .conf import in AmneziaVPN.',
      configInstructions: 'Import configuration file to VPN client',
      copyConfig: 'Copy config',
      copied: 'Copied!',
      devicesTitle: 'Your devices',
      devicesListTitle: 'Your devices',
      devicesListHint: 'Select a device to download exactly its configuration.',
      configMasterDetailHint: 'Select a device and action.',
      devicesActive: 'Active',
      devicesUsed: 'Used',
      devicesLimit: 'Limit',
      devicesEmpty: 'No devices yet',
      devicesEmptyHint: 'Create the first config for a phone, laptop, or desktop.',
      selectedDevice: 'Selected device',
      platformNotSet: 'platform not set',
      configLoading: 'Loading the selected device configuration.',
      configReady: 'Selected device configuration is ready.',
      configUnavailable: 'Configuration is not available yet',
      configLoadFailed: 'Could not load configuration',
      tryRefreshLater: 'Try refreshing the page a bit later.',
      configDownloaded: 'Config downloaded',
      deviceSelectActive: 'Select an active device',
      deviceSelectPrompt: 'Select a device',
      deviceSelectPromptHint: 'QR, .conf, and Copy will appear here after selection.',
      deviceStatusActive: 'active',
      deviceStatusBlocked: 'blocked',
      deviceStatusRevoked: 'revoked',
      deviceSecondaryActions: 'Device actions',
      rotateConfig: 'Refresh keys',
      deleteDevice: 'Delete',
      newDeviceConfig: 'New config for your device',
      newDeviceHint: 'Create a separate peer for a phone, laptop, or tablet.',
      deviceNamePlaceholder: 'Example: iPhone 16 Pro',
      deviceNameRequired: 'Enter a device name',
      deviceLimitReached: 'Device limit reached',
      deviceLimitReachedWithTariff: 'Device limit reached under your tariff - {{tariff}}',
      createDevice: 'Create device',
      deviceCreated: 'Device created and config is ready',
      deviceCreateFailed: 'Could not create device',
      deviceRotated: 'Device keys refreshed',
      deviceRotateFailed: 'Could not refresh keys',
      deviceRevoked: 'Device revoked',
      deviceRevokeFailed: 'Could not revoke device',
      deviceRotateConfirm: 'Refresh keys for this device?',
      deviceRevokeConfirm: 'Delete this device?',
      qrServerUnavailable: 'QR is temporarily unavailable. Try downloading .conf.',
      name: 'Name',
      platform: 'Platform',

      // Subscription
      currentPlan: 'Current plan',
      choosePlan: 'Choose plan',
      plans: 'Plans',
      days: 'days',
      month: 'month',
      months: 'months',
      year: 'year',
      buy: 'Buy',
      extend: 'Extend',
      trial: 'Trial',
      trialDays: '{{days}} days free',
      subscriptionDescriptionNone: 'Choose a plan, pay, and open config immediately.',
      subscriptionDescriptionReferral: 'Bonus {{days}} days are ready. The timer starts after the first connection.',
      subscriptionDescriptionTrialReferral: 'Config is ready. {{days}} trial and bonus days start after the first connection.',
      subscriptionDescriptionPending: 'Config is ready. The 4-day timer starts after the first connection.',
      subscriptionDescriptionActive: 'Access is active until: {{date}}',
      subscriptionDescriptionExpired: 'Extend the subscription to reopen VPN access.',
      subscriptionCalendar: 'Subscription calendar',
      subscriptionCalendarPending: 'Dates will be highlighted after the first connection.',
      subscriptionCalendarEmpty: 'No active subscription range.',
      noActiveAccess: 'No active access',
      accessExpired: 'Access expired',
      waitingForConnection: 'Waiting for connection',
      bonusWaitingConnection: 'Bonus waits for connection',
      trialBonusWaitingConnection: 'Trial + bonus wait',
      activePlansNotPublished: 'Active plans are not published yet',
      activePlansHint: 'When the administrator adds tariffs, they will appear here automatically.',
      popular: 'Popular',
      devicesCount: '{{count}} devices',
      devicesOccupied: 'Used {{used}} of {{limit}}',
      planUnavailable: 'Unavailable',
      planBlockedByDevices: 'Too many devices are used for this plan. Revoke extra devices in configuration first.',

      // Referrals
      referralProgram: 'Referral Program',
      referralCode: 'Your referral code',
      referralLink: 'Referral link',
      referralsCount: 'Referrals',
      bonusDays: 'Bonus days',
      referralInstructions: 'Invite friends and get bonus subscription days',
      referralBonus: '+{{days}} days for each referral',

      // Settings
      profile: 'Profile',
      language: 'Language',
      changePassword: 'Change password',
      currentPassword: 'Current password',
      newPassword: 'New password',
      passwordChanged: 'Password changed',
      personalCabinet: 'Personal cabinet',
      settingsSubtitle: 'Manage profile, interface language, and account security.',
      accountBasics: 'Basic account data.',
      namePlaceholder: 'Your name',
      languageSubtitle: 'Switch the interface language in one click.',
      passwordSecurityHint: 'Use a long unique password to protect the account.',
      passwordTooWeak: 'Password is too weak: {{issues}}',
      russian: 'Русский',
      english: 'English',

      // Errors
      somethingWentWrong: 'Something went wrong',
      networkError: 'Network error',
      unauthorized: 'Unauthorized',
    },
  },
}
// END_BLOCK_RESOURCES

// START_BLOCK_I18N_INIT
i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: 'ru',
    fallbackLng: 'ru',
    interpolation: {
      escapeValue: true,
    },
  })

export default i18n
// END_BLOCK_I18N_INIT
