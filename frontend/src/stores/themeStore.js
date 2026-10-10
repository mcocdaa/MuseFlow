import { defineStore } from 'pinia'

export const THEMES = [
  {
    id: 'cyber-dark',
    name: '幻紫流光',
    subname: 'Cyber Dark',
    desc: '经典暗黑基调搭配霓光紫与极光靛',
    accentColor: '#a855f7',
    bgColor: '#0f1117',
    surfaceColor: '#171923',
    gradient: 'from-purple-600 via-indigo-500 to-pink-500',
    isDark: true,
  },
  {
    id: 'oled-black',
    name: '黑曜深空',
    subname: 'OLED Pure Black',
    desc: '纯黑极致省电，影院级高对比视效',
    accentColor: '#8b5cf6',
    bgColor: '#000000',
    surfaceColor: '#0a0a0c',
    gradient: 'from-violet-500 via-purple-500 to-zinc-400',
    isDark: true,
  },
  {
    id: 'sakura-pink',
    name: '粉黛微光',
    subname: 'Sakura & Bilibili',
    desc: '元气桃粉与玫瑰金，浪漫次元感',
    accentColor: '#f43f5e',
    bgColor: '#130d16',
    surfaceColor: '#1c1322',
    gradient: 'from-pink-500 via-rose-500 to-purple-500',
    isDark: true,
  },
  {
    id: 'cyberpunk-neon',
    name: '赛博电青',
    subname: 'Cyberpunk Neon',
    desc: '冷冽深海蓝与高饱和电光青',
    accentColor: '#06b6d4',
    bgColor: '#081119',
    surfaceColor: '#0e1c28',
    gradient: 'from-cyan-500 via-teal-500 to-blue-500',
    isDark: true,
  },
  {
    id: 'forest-emerald',
    name: '苍翠松隐',
    subname: 'Forest Emerald',
    desc: '北欧森林静谧墨绿与薄荷青翠',
    accentColor: '#10b981',
    bgColor: '#081410',
    surfaceColor: '#10221c',
    gradient: 'from-emerald-500 via-teal-500 to-green-500',
    isDark: true,
  },
  {
    id: 'sunset-amber',
    name: '落日熔金',
    subname: 'Sunset Amber',
    desc: '暖调落日熔金与暖暮晚霞',
    accentColor: '#f59e0b',
    bgColor: '#17110c',
    surfaceColor: '#241a14',
    gradient: 'from-amber-500 via-orange-500 to-rose-500',
    isDark: true,
  },
  {
    id: 'clean-light',
    name: '摄影工坊',
    subname: 'Studio Light',
    desc: '极简柔光素白，自然通透白天模式',
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
