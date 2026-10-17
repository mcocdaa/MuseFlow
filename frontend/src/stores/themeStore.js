import { defineStore } from 'pinia'
import { t } from '../i18n'

export const THEMES = [
  {
    id: 'cyber-dark',
    get name() { return t('theme.item.cyber-dark.name') },
    subname: 'Cyber Dark',
    get desc() { return t('theme.item.cyber-dark.desc') },
    accentColor: '#a855f7',
    bgColor: '#0f1117',
    surfaceColor: '#171923',
    gradient: 'from-purple-600 via-indigo-500 to-pink-500',
    isDark: true,
  },
  {
    id: 'oled-black',
    get name() { return t('theme.item.oled-black.name') },
    subname: 'OLED Pure Black',
    get desc() { return t('theme.item.oled-black.desc') },
    accentColor: '#8b5cf6',
    bgColor: '#000000',
    surfaceColor: '#0a0a0c',
    gradient: 'from-violet-500 via-purple-500 to-zinc-400',
    isDark: true,
  },
  {
    id: 'sakura-pink',
    get name() { return t('theme.item.sakura-pink.name') },
    subname: 'Sakura & Bilibili',
    get desc() { return t('theme.item.sakura-pink.desc') },
    accentColor: '#f43f5e',
    bgColor: '#130d16',
    surfaceColor: '#1c1322',
    gradient: 'from-pink-500 via-rose-500 to-purple-500',
    isDark: true,
  },
  {
    id: 'cyberpunk-neon',
    get name() { return t('theme.item.cyberpunk-neon.name') },
    subname: 'Cyberpunk Neon',
    get desc() { return t('theme.item.cyberpunk-neon.desc') },
    accentColor: '#06b6d4',
    bgColor: '#081119',
    surfaceColor: '#0e1c28',
    gradient: 'from-cyan-500 via-teal-500 to-blue-500',
    isDark: true,
  },
  {
    id: 'forest-emerald',
    get name() { return t('theme.item.forest-emerald.name') },
    subname: 'Forest Emerald',
    get desc() { return t('theme.item.forest-emerald.desc') },
    accentColor: '#10b981',
    bgColor: '#081410',
    surfaceColor: '#10221c',
    gradient: 'from-emerald-500 via-teal-500 to-green-500',
    isDark: true,
  },
  {
    id: 'sunset-amber',
    get name() { return t('theme.item.sunset-amber.name') },
    subname: 'Sunset Amber',
    get desc() { return t('theme.item.sunset-amber.desc') },
    accentColor: '#f59e0b',
    bgColor: '#17110c',
    surfaceColor: '#241a14',
    gradient: 'from-amber-500 via-orange-500 to-rose-500',
    isDark: true,
  },
  {
    id: 'clean-light',
    get name() { return t('theme.item.clean-light.name') },
    subname: 'Studio Light',
    get desc() { return t('theme.item.clean-light.desc') },
    accentColor: '#7c3aed',
    bgColor: '#f8fafc',
    surfaceColor: '#ffffff',
    gradient: 'from-violet-600 to-indigo-600',
    isDark: false,
  }
]

export const useThemeStore = defineStore('theme', {
  state: () => ({
    currentThemeId: localStorage.getItem('museflow-theme') || 'cyber-dark',
    themePickerOpen: false,
  }),

  getters: {
    currentTheme: (state) => THEMES.find(t => t.id === state.currentThemeId) || THEMES[0],
    isDarkMode: (state) => (THEMES.find(t => t.id === state.currentThemeId) || THEMES[0]).isDark,
  },

  actions: {
    initTheme() {
      this.applyTheme(this.currentThemeId)
    },

    setTheme(themeId) {
      if (THEMES.some(t => t.id === themeId)) {
        this.currentThemeId = themeId
        localStorage.setItem('museflow-theme', themeId)
        this.applyTheme(themeId)
      }
    },

    applyTheme(themeId) {
      document.documentElement.setAttribute('data-theme', themeId)
      const theme = THEMES.find(t => t.id === themeId) || THEMES[0]
      if (theme.isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  }
})
