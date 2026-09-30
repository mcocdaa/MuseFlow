<script setup>
import { computed } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { useThemeStore } from '../stores/themeStore'
import {
  Compass,
  FolderOpen,
  Sparkles,
  Image as ImageIcon,
  Video,
  Music,
  LayoutGrid,
  RefreshCw,
  FolderSearch,
  BrainCircuit,
  Palette
} from 'lucide-vue-next'

const mediaStore = useMediaStore()
const themeStore = useThemeStore()

const categories = [
  { id: 'all', name: '全部', icon: LayoutGrid },
  { id: 'image', name: '图片', icon: ImageIcon },
  { id: 'video', name: '视频 / 复合包', icon: Video },
  { id: 'audio', name: '音乐', icon: Music },
]

const handleCategoryChange = (catId) => {
  mediaStore.activeCategory = catId
  if (mediaStore.currentMode === 'stream') {
    mediaStore.loadFeed()
  } else {
    mediaStore.loadWorkplaceItems()
  }
}

const handleAlgorithmChange = (e) => {
  mediaStore.selectedAlgorithm = e.target.value
  mediaStore.loadFeed()
}

const handleRefresh = () => {
  if (mediaStore.currentMode === 'stream') {
    mediaStore.loadFeed()
  } else {
    mediaStore.loadWorkplaceItems()
  }
}
</script>

<template>
  <header
    class="sticky top-0 z-30 backdrop-blur-md border-b px-4 lg:px-8 py-3 transition-colors"
    style="background-color: var(--bg-surface); border-color: var(--border-color);"
  >
    <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
      <!-- Brand & Mode Switch -->
      <div class="flex items-center gap-6 w-full md:w-auto justify-between md:justify-start">
        <div class="flex items-center gap-2 cursor-pointer" @click="mediaStore.currentMode = 'stream'">
          <div
            class="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg text-white"
            style="background-color: var(--accent-color);"
          >
            <Compass class="w-5 h-5 text-white" />
          </div>
          <div>
            <div class="font-bold text-lg tracking-wide text-white">
              MuseFlow
            </div>
            <div class="text-[10px] text-gray-400 -mt-1 font-medium tracking-wider">灵眸流 · 记忆中枢</div>
          </div>
        </div>

        <!-- Mode Toggle Tabs -->
        <div class="flex items-center p-1 bg-white/5 rounded-xl border border-white/10">
          <button
            @click="mediaStore.currentMode = 'stream'"
            :class="[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              mediaStore.currentMode === 'stream'
                ? 'text-white shadow-md'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            :style="mediaStore.currentMode === 'stream' ? { backgroundColor: 'var(--accent-color)' } : {}"
          >
            <Sparkles class="w-3.5 h-3.5" />
            <span>沉浸流 (Stream)</span>
          </button>
          <button
            @click="mediaStore.currentMode = 'workplace'; mediaStore.loadWorkplaceItems()"
            :class="[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              mediaStore.currentMode === 'workplace'
                ? 'text-white shadow-md'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            :style="mediaStore.currentMode === 'workplace' ? { backgroundColor: 'var(--accent-color)' } : {}"
          >
            <FolderOpen class="w-3.5 h-3.5" />
            <span>工作台 (Workplace)</span>
          </button>
        </div>
      </div>

      <!-- Categories & Filtering -->
      <div class="flex items-center gap-2 overflow-x-auto max-w-full pb-1 md:pb-0">
        <button
          v-for="cat in categories"
          :key="cat.id"
          @click="handleCategoryChange(cat.id)"
          :class="[
            'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all border shrink-0',
            mediaStore.activeCategory === cat.id
              ? 'shadow-sm text-white'
              : 'bg-white/5 border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/10'
          ]"
          :style="mediaStore.activeCategory === cat.id ? { backgroundColor: 'var(--accent-color)', borderColor: 'var(--accent-border)' } : {}"
        >
          <component :is="cat.icon" class="w-3.5 h-3.5" />
          <span>{{ cat.name }}</span>
        </button>
      </div>

      <!-- Actions & Algorithm Dropdown -->
      <div class="flex items-center gap-2.5 w-full md:w-auto justify-end">
        <!-- Recommender selector (only in stream mode) -->
        <div v-if="mediaStore.currentMode === 'stream'" class="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1">
          <Sparkles class="w-3.5 h-3.5" style="color: var(--accent-color);" />
          <select
            :value="mediaStore.selectedAlgorithm"
            @change="handleAlgorithmChange"
            class="bg-transparent text-xs text-gray-200 focus:outline-none cursor-pointer"
          >
            <option
              v-for="algo in mediaStore.algorithms"
              :key="algo.name"
              :value="algo.name"
              class="bg-gray-900 text-white"
            >
              {{ algo.display_name }}
            </option>
          </select>
        </div>

        <!-- AI Memory Recap -->
        <button
          @click="mediaStore.recapModalOpen = true"
          title="AI 记忆唤醒与待整理建议"
          class="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/10 text-gray-200 hover:text-white text-xs px-2.5 py-1.5 rounded-lg transition-all"
        >
          <BrainCircuit class="w-3.5 h-3.5 text-pink-400" />
          <span class="hidden sm:inline">AI 记忆</span>
        </button>

        <!-- Theme Picker Button -->
        <button
          @click="themeStore.themePickerOpen = true"
          class="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 text-white text-xs px-2.5 py-1.5 rounded-lg transition-all border border-white/10 shadow-sm"
          title="切换主题配色 (7种精选主题)"
        >
          <Palette class="w-3.5 h-3.5" style="color: var(--accent-color);" />
          <span class="hidden sm:inline text-xs font-medium">{{ themeStore.currentTheme.name }}</span>
        </button>

        <!-- Scan Directory Button -->
        <button
          @click="mediaStore.scanModalOpen = true"
          class="flex items-center gap-1.5 bg-white/10 hover:bg-white/15 text-white text-xs px-3 py-1.5 rounded-lg transition-all border border-white/10"
        >
          <FolderSearch class="w-3.5 h-3.5 text-indigo-400" />
          <span>纳管目录</span>
        </button>

        <!-- Refresh Button -->
        <button
          @click="handleRefresh"
          title="刷新内容"
          class="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
        >
          <RefreshCw :class="['w-4 h-4', mediaStore.loading ? 'animate-spin' : '']" />
        </button>
      </div>
    </div>
  </header>
</template>
