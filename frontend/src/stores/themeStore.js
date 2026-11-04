import { defineStore } from 'pinia'
import { t } from '../i18n'

export const THEMES = [
  {
    id: 'studio-dark',
    get name() { return t('theme.item.cyber-dark.name') },
    subname: 'Studio Dark',
    get desc() { return t('theme.item.cyber-dark.desc') },
    accentColor: '#2563eb',
    bgColor: '#0a0c10',
    surfaceColor: '#11141b',
    isDark: true,
  },
  {
    id: 'clean-light',
    get name() { return t('theme.item.clean-light.name') },
    subname: 'Studio Light',
    get desc() { return t('theme.item.clean-light.desc') },
    accentColor: '#2563eb',
    bgColor: '#f8fafc',
    surfaceColor: '#ffffff',
    isDark: false,
  },
]

const normalizeThemeId = (rawId) => {
  if (rawId === 'clean-light' || rawId === 'studio-light') return 'clean-light'
  return 'studio-dark'
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    currentThemeId: normalizeThemeId(localStorage.getItem('museflow-theme')),
  }),

  getters: {
    currentTheme: (state) => THEMES.find(theme => theme.id === state.currentThemeId) || THEMES[0],
    isDarkMode: (state) => (THEMES.find(theme => theme.id === state.currentThemeId) || THEMES[0]).isDark,
  },

  actions: {
    initTheme() {
      this.currentThemeId = normalizeThemeId(this.currentThemeId)
      this.applyTheme(this.currentThemeId)
    },

    toggleTheme() {
      const nextId = this.isDarkMode ? 'clean-light' : 'studio-dark'
      this.setTheme(nextId)
    },

    setTheme(themeId) {
      const normalized = normalizeThemeId(themeId)
      this.currentThemeId = normalized
      localStorage.setItem('museflow-theme', normalized)
      this.applyTheme(normalized)
    },

    applyTheme(themeId) {
      const normalized = normalizeThemeId(themeId)
      document.documentElement.setAttribute('data-theme', normalized)
      const theme = THEMES.find(item => item.id === normalized) || THEMES[0]
      if (theme.isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
  },
})
