<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { useThemeStore } from '../stores/themeStore'
import { usePlayerStore } from '../stores/playerStore'
import {
  Compass,
  FolderOpen,
  Sparkles,
  RefreshCw,
  FolderSearch,
  BrainCircuit,
  Palette,
  Search,
  X,
  Play,
  Pause,
  SkipForward,
  Music,
  Tv,
  ListMusic,
  Power
} from 'lucide-vue-next'

const mediaStore = useMediaStore()
const themeStore = useThemeStore()
const playerStore = usePlayerStore()

const isSearchOpen = ref(false)
const searchInputRef = ref(null)

const toggleSearch = () => {
  isSearchOpen.value = !isSearchOpen.value
  if (isSearchOpen.value) {
    nextTick(() => searchInputRef.value?.focus())
  }
}

const handleGlobalSlashKey = (e) => {
  if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
    e.preventDefault()
    isSearchOpen.value = true
    nextTick(() => searchInputRef.value?.focus())
  }
}

const onSearchBlur = () => {
  if (!mediaStore.searchQuery.trim()) {
    isSearchOpen.value = false
  }
}

const onSearchEsc = () => {
  mediaStore.searchQuery = ''
  isSearchOpen.value = false
  searchInputRef.value?.blur()
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalSlashKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalSlashKey)
})

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
    class="sticky top-0 z-30 backdrop-blur-md border-b px-4 lg:px-8 py-2.5 transition-colors"
    style="background-color: var(--bg-surface); border-color: var(--border-color);"
  >
    <div class="max-w-7xl mx-auto flex items-center justify-between gap-4">
      <!-- Left: Brand & Mode Pill -->
      <div class="flex items-center gap-4 shrink-0">
        <!-- Logo -->
        <div
          class="flex items-center gap-2.5 cursor-pointer select-none group"
          @click="mediaStore.currentMode = 'stream'"
          title="MuseFlow 灵眸流"
        >
          <div
            class="w-8 h-8 rounded-xl flex items-center justify-center shadow-md text-white transition-transform group-hover:scale-105 active:scale-95"
            style="background-color: var(--accent-color);"
          >
            <Compass class="w-4 h-4 text-white" />
          </div>
          <span class="font-bold text-base tracking-wide text-white">MuseFlow</span>
        </div>

        <!-- Mode Toggle Segmented Control (Icon only with tooltips) -->
        <div class="flex items-center p-0.5 bg-white/5 rounded-xl border border-white/10">
          <button
            @click="mediaStore.currentMode = 'stream'"
            :class="[
              'p-1.5 rounded-lg transition-all duration-200',
              mediaStore.currentMode === 'stream'
                ? 'text-white shadow-md'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            :style="mediaStore.currentMode === 'stream' ? { backgroundColor: 'var(--accent-color)' } : {}"
            title="沉浸流"
          >
            <Sparkles class="w-4 h-4" />
          </button>
          <button
            @click="mediaStore.currentMode = 'workplace'; mediaStore.loadWorkplaceItems()"
            :class="[
              'p-1.5 rounded-lg transition-all duration-200',
              mediaStore.currentMode === 'workplace'
                ? 'text-white shadow-md'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            :style="mediaStore.currentMode === 'workplace' ? { backgroundColor: 'var(--accent-color)' } : {}"
            title="工作台"
          >
            <FolderOpen class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Center: Dual-Track Master Console Status Capsule -->
      <div
        v-if="playerStore.activeBgUnit || playerStore.bgQueue.length > 0 || (playerStore.fgViewerOpen && playerStore.fgAutoPlay)"
        class="hidden md:flex items-center gap-2.5 px-3 py-1 rounded-full bg-white/5 border border-white/10 backdrop-blur-md shadow-sm select-none max-w-sm sm:max-w-md truncate"
      >
        <!-- Background Audio Track Pill (when active track is loaded) -->
        <div
          v-if="playerStore.activeBgUnit"
          class="flex items-center gap-2 min-w-0"
        >
          <!-- Spinning Vinyl / Music Icon (Clicking brings up player) -->
          <button
            @click="playerStore.setBgViewMode(playerStore.bgViewMode === 'mini' ? 'disc' : 'mini')"
            class="relative flex items-center justify-center w-6 h-6 rounded-full bg-purple-600/30 border border-purple-400/40 text-purple-200 shrink-0 hover:scale-110 transition-transform"
            :title="`背景伴音: ${playerStore.activeBgUnit.title} (点击切换小窗/唱片模式)`"
          >
            <Music
              class="w-3 h-3 text-purple-300"
              :class="{ 'animate-pulse': playerStore.isBgPlaying }"
            />
          </button>

          <!-- Track Title (truncated) -->
          <span
            @click="playerStore.setBgViewMode('mini')"
            class="text-xs text-gray-200 truncate cursor-pointer hover:text-purple-300 transition-colors font-medium max-w-[100px] sm:max-w-[130px]"
            :title="playerStore.activeBgUnit.title"
          >
            {{ playerStore.activeBgUnit.title }}
          </span>

          <!-- Inline Transport Controls -->
          <div class="flex items-center gap-0.5">
            <button
              @click.stop="playerStore.togglePlayAudio"
              class="p-1 hover:text-white text-gray-400 transition-colors"
              :title="playerStore.isBgPlaying ? '暂停背景音乐' : '播放背景音乐'"
            >
              <Pause v-if="playerStore.isBgPlaying" class="w-3.5 h-3.5 fill-current" />
              <Play v-else class="w-3.5 h-3.5 fill-current" />
            </button>
            <button
              @click.stop="playerStore.nextAudio"
              class="p-1 hover:text-white text-gray-400 transition-colors"
              title="下一首"
            >
              <SkipForward class="w-3 h-3" />
            </button>
          </div>

          <!-- Queue Drawer Toggle Button -->
          <button
            @click.stop="playerStore.toggleQueueDrawer()"
            class="p-1 hover:text-purple-300 text-gray-400 transition-colors relative"
            :class="playerStore.queueDrawerOpen ? 'text-purple-300 bg-white/10 rounded' : ''"
            :title="`打开背景播放队列 (${playerStore.bgQueue.length} 首)`"
          >
            <ListMusic class="w-3.5 h-3.5" />
            <span
              v-if="playerStore.bgQueue.length > 0"
              class="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-purple-400"
            />
          </button>

          <!-- Stop & Exit Background Playback Button -->
          <button
            @click.stop="playerStore.stopAndExitBgPlayback()"
            class="p-1 hover:text-amber-400 text-gray-400 transition-colors"
            title="停止并退出背景播放"
          >
            <Power class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Background Queue Pill (when not playing, but queue has items) -->
        <div
          v-else-if="playerStore.bgQueue.length > 0"
          @click="playerStore.toggleQueueDrawer()"
          class="flex items-center gap-1.5 cursor-pointer hover:text-purple-300 text-gray-300 text-xs px-1.5 py-0.5 rounded-lg hover:bg-white/5 transition-colors"
          :title="`打开背景播放队列 (共 ${playerStore.bgQueue.length} 项)`"
        >
          <ListMusic class="w-3.5 h-3.5 text-purple-400" />
          <span class="font-mono text-[11px]">队列 ({{ playerStore.bgQueue.length }})</span>
          <button
            @click.stop="playerStore.playAudio(playerStore.bgQueue[0], playerStore.bgQueue, 'disc')"
            class="p-1 hover:text-white text-purple-300 rounded ml-0.5"
            title="开始播放队列"
          >
            <Play class="w-3 h-3 fill-current" />
          </button>
        </div>

        <!-- Foreground Slideshow Capsule (if active) -->
        <div
          v-if="playerStore.fgViewerOpen && playerStore.fgAutoPlay"
          class="flex items-center gap-1.5 pl-2 border-l border-white/10 shrink-0 text-pink-300 text-xs font-medium"
        >
          <Tv class="w-3.5 h-3.5 text-pink-400" />
          <span class="font-mono text-[11px]">连播 {{ playerStore.fgTimeRemaining }}s</span>
        </div>
      </div>

      <!-- Right: Minimalist Icon Actions with Tooltips -->
      <div class="flex items-center gap-1.5">
        <!-- Expandable Search -->
        <div class="relative flex items-center">
          <div
            v-if="isSearchOpen || mediaStore.searchQuery"
            class="flex items-center bg-white/5 border border-white/10 rounded-xl px-2.5 py-1 transition-all duration-300 w-44 sm:w-60 shadow-sm"
          >
            <Search class="w-3.5 h-3.5 text-gray-400 shrink-0 mr-1.5" />
            <input
              ref="searchInputRef"
              v-model="mediaStore.searchQuery"
              type="text"
              placeholder="搜索资产..."
              class="bg-transparent w-full text-xs text-white placeholder-gray-500 focus:outline-none"
              @blur="onSearchBlur"
              @keydown.esc="onSearchEsc"
            />
            <button
              v-if="mediaStore.searchQuery"
              @click="mediaStore.searchQuery = ''"
              class="text-gray-400 hover:text-white shrink-0 ml-1 p-0.5"
              title="清空"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
          <button
            v-else
            @click="toggleSearch"
            class="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-xl transition-all border border-transparent hover:border-white/10"
            title="搜索 (快捷键 /)"
          >
            <Search class="w-4 h-4" />
          </button>
        </div>

        <!-- AI Memory Recap -->
        <button
          @click="mediaStore.recapModalOpen = true"
          title="AI 记忆唤醒"
          class="p-2 text-pink-400 hover:text-pink-300 hover:bg-white/10 rounded-xl transition-all border border-transparent hover:border-white/10"
        >
          <BrainCircuit class="w-4 h-4" />
        </button>

        <!-- Theme Picker Button -->
        <button
          @click="themeStore.themePickerOpen = true"
          class="p-2 text-gray-300 hover:text-white hover:bg-white/10 rounded-xl transition-all border border-transparent hover:border-white/10"
          :title="`切换主题 (当前: ${themeStore.currentTheme.name})`"
        >
          <Palette class="w-4 h-4" style="color: var(--accent-color);" />
        </button>

        <!-- Scan Directory Button -->
        <button
          @click="mediaStore.scanModalOpen = true"
          class="p-2 text-indigo-400 hover:text-indigo-300 hover:bg-white/10 rounded-xl transition-all border border-transparent hover:border-white/10"
          title="纳管本地目录"
        >
          <FolderSearch class="w-4 h-4" />
        </button>

        <!-- Refresh Button -->
        <button
          @click="handleRefresh"
          title="刷新"
          class="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-xl transition-all border border-transparent hover:border-white/10"
        >
          <RefreshCw :class="['w-4 h-4', mediaStore.loading ? 'animate-spin' : '']" />
        </button>
      </div>
    </div>
  </header>
</template>
