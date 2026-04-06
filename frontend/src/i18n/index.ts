// FILE: frontend/src/i18n/index.ts
// VERSION: 1.0.0
// ROLE: UTILITY
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: i18next configuration with Russian and English translation resources
//   SCOPE: Translation dictionary (ru/en), i18next initialization, language persistence via localStorage
//   DEPENDS: M-009 (frontend-user)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   resources - Translation dictionary with ru and en namespaces
//   i18n - Initialized i18next instance (default export)
//   BLOCK_RESOURCES - Translation resources object (~200 lines)
//   BLOCK_I18N_INIT - i18next initialization and export (~15 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
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
      appName: 'KrotVPN',
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
      invalidCredentials: 'Неверный email или пароль',
      registrationSuccess: 'Регистрация успешна!',

      // Navigation
      dashboard: 'Главная',
      config: 'Конфигурация',
      subscription: 'Подписка',
      referrals: 'Рефералы',
      settings: 'Настройки',

      // Dashboard
      welcome: 'Добро пожаловать',
      yourVPN: 'Ваш VPN',
      status: 'Статус',
      connected: 'Подключено',
      disconnected: 'Отключено',
      server: 'Сервер',
      location: 'Локация',
      traffic: 'Трафик',
      upload: 'Отправлено',
      download: 'Получено',
      lastConnection: 'Последнее подключение',
      daysLeft: 'дней осталось',
      subscriptionActive: 'Подписка активна',
      subscriptionExpired: 'Подписка истекла',

      // Config
      vpnConfig: 'VPN Конфигурация',
      downloadConfig: 'Скачать .conf',
      scanQR: 'Сканировать QR',
      qrInstructions: 'Отсканируйте QR-код приложением AmneziaWG',
      configInstructions: 'Импортируйте файл конфигурации в VPN клиент',
      copyConfig: 'Копировать конфиг',
      copied: 'Скопировано!',

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

      // Errors
      somethingWentWrong: 'Что-то пошло не так',
      networkError: 'Ошибка сети',
      unauthorized: 'Не авторизован',
    },
  },
  en: {
    translation: {
      // Common
      appName: 'KrotVPN',
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
      yourVPN: 'Your VPN',
      status: 'Status',
      connected: 'Connected',
      disconnected: 'Disconnected',
      server: 'Server',
      location: 'Location',
      traffic: 'Traffic',
      upload: 'Upload',
      download: 'Download',
      lastConnection: 'Last connection',
      daysLeft: 'days left',
      subscriptionActive: 'Subscription active',
      subscriptionExpired: 'Subscription expired',

      // Config
      vpnConfig: 'VPN Configuration',
      downloadConfig: 'Download .conf',
      scanQR: 'Scan QR',
      qrInstructions: 'Scan QR code with AmneziaWG app',
      configInstructions: 'Import configuration file to VPN client',
      copyConfig: 'Copy config',
      copied: 'Copied!',

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
    lng: localStorage.getItem('language') || 'ru',
    fallbackLng: 'ru',
    interpolation: {
      escapeValue: true,
    },
  })

export default i18n
// END_BLOCK_I18N_INIT
