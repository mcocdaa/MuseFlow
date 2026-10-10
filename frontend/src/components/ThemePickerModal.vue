<script setup>
import { useThemeStore, THEMES } from '../stores/themeStore'
import { X, Palette, Check, Sparkles, Moon, Sun } from 'lucide-vue-next'

const themeStore = useThemeStore()

const selectTheme = (themeId) => {
  themeStore.setTheme(themeId)
}
</script>

<template>
  <div
    v-if="themeStore.themePickerOpen"
    class="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-md animate-fade-in"
  >
    <div
      class="border rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative transition-all"
      style="background-color: var(--bg-surface); border-color: var(--border-color);"
    >
      <!-- Close Button -->
      <button
        @click="themeStore.themePickerOpen = false"
        class="absolute top-4 right-4 p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
      >
        <X class="w-5 h-5" />
      </button>

      <!-- Header -->
      <div class="flex items-center gap-3 mb-6">
        <div
          class="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg"
          style="background: var(--accent-color); color: white;"
        >
          <Palette class="w-5 h-5" />
        </div>
        <div>
          <h3 class="text-base font-bold text-white flex items-center gap-2">
            <span>个性化主题配色</span>
            <span class="text-xs px-2 py-0.5 rounded-full font-normal border" style="border-color: var(--accent-border); color: var(--accent-text);">
              共 {{ THEMES.length }} 款
            </span>
          </h3>
          <p class="text-xs text-gray-400 mt-0.5">
            为 MuseFlow 定制专属氛围，即点即生效，随时随地沉浸欣赏
          </p>
        </div>
      </div>

      <!-- Theme Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5 max-h-[60vh] overflow-y-auto pr-1">
        <div
          v-for="theme in THEMES"
          :key="theme.id"
          @click="selectTheme(theme.id)"
          class="group relative p-3.5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between gap-3"
          :style="{
            backgroundColor: themeStore.currentThemeId === theme.id ? 'var(--accent-light)' : 'rgba(255,255,255,0.03)',
            borderColor: themeStore.currentThemeId === theme.id ? 'var(--accent-color)' : 'rgba(255,255,255,0.08)'
          }"
        >
          <!-- Top: Info and Active Check -->
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="text-sm font-bold text-white flex items-center gap-1.5">
                <span>{{ theme.name }}</span>
                <span class="text-[10px] text-gray-400 font-mono font-normal">({{ theme.subname }})</span>
              </div>
              <p class="text-[11px] text-gray-400 mt-0.5 leading-relaxed">
                {{ theme.desc }}
              </p>
            </div>

            <!-- Active checkmark badge -->
            <div
              v-if="themeStore.currentThemeId === theme.id"
              class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 shadow-md text-white"
              style="background-color: var(--accent-color);"
            >
              <Check class="w-3.5 h-3.5 stroke-[3]" />
            </div>
          </div>

          <!-- Bottom: Color Swatches Preview -->
          <div class="flex items-center justify-between pt-2 border-t border-white/5">
            <div class="flex items-center gap-2">
              <!-- Bg Color Swatch -->
              <div
                class="w-5 h-5 rounded-lg border border-white/20 shadow-inner"
                :style="{ backgroundColor: theme.bgColor }"
                title="主背景色"
              ></div>
              <!-- Surface Swatch -->
              <div
                class="w-5 h-5 rounded-lg border border-white/20 shadow-inner"
                :style="{ backgroundColor: theme.surfaceColor }"
                title="卡片/面板色"
              ></div>
              <!-- Accent Gradient Pill -->
              <div
                class="h-5 px-3 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow-sm"
                :style="{ backgroundColor: theme.accentColor }"
              >
                主基调
              </div>
            </div>

            <!-- Mode Badge -->
            <span class="text-[10px] text-gray-500 font-mono flex items-center gap-1">
              <Moon v-if="theme.isDark" class="w-3 h-3 text-purple-400" />
              <Sun v-else class="w-3 h-3 text-amber-400" />
              <span>{{ theme.isDark ? '暗色' : '浅色' }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Footer Info -->
      <div class="mt-5 pt-4 border-t flex items-center justify-between text-xs text-gray-400" style="border-color: var(--border-color);">
        <span class="flex items-center gap-1.5">
          <Sparkles class="w-3.5 h-3.5" style="color: var(--accent-color);" />
          <span>配色方案会自动同步保存至本地浏览器缓存</span>
        </span>
        <button
          @click="themeStore.themePickerOpen = false"
          class="px-4 py-1.5 rounded-xl font-medium text-white shadow-md transition-all text-xs"
          style="background-color: var(--accent-color);"
        >
          完成
        </button>
      </div>
    </div>
  </div>
</template>
