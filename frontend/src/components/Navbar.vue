<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { useThemeStore } from '../stores/themeStore'
import { usePlayerStore } from '../stores/playerStore'
import { locale, toggleLocale, t, tData } from '../i18n'
import {
  Compass,
  FolderOpen,
  RefreshCw,
  FolderSearch,
  Search,
  X,
  Play,
  Pause,
  SkipForward,
  Music,
  Tv,
  ListMusic,
  Power,
  Tags,
  Workflow,
  Sun,
  Moon,
  Globe
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
    class="sticky top-0 z-30 border-b px-4 lg:px-8 py-2.5 transition-colors"
    style="background-color: var(--bg-surface); border-color: var(--border-color);"
  >
    <div class="max-w-[1600px] mx-auto flex items-center justify-between gap-4">
      <!-- Left: Brand & 4-Page Task Navigation -->
      <div class="flex items-center gap-6 shrink-0">
        <!-- Brand Logo -->
        <div
          class="flex items-center gap-2.5 cursor-pointer select-none"
          :title="t('nav.brandTitle')"
          @click="mediaStore.currentMode = 'stream'"
        >
          <div
            class="w-7 h-7 rounded-lg flex items-center justify-center border"
            style="background-color: var(--accent-light); border-color: var(--accent-border); color: var(--accent-text);"
          >
            <Compass class="w-4 h-4" />
          </div>
          <span class="font-semibold text-sm tracking-tight" style="color: var(--text-primary);">MuseFlow</span>
        </div>

        <!-- 4 Labeled Top-Level Task Pages -->
        <nav
          class="flex items-center p-1 rounded-lg border gap-1"
          style="background-color: var(--bg-app); border-color: var(--border-color);"
        >
          <button
            data-testid="nav-mode-stream"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
            :style="mediaStore.currentMode === 'stream'
              ? 'background-color: var(--accent-color); color: #ffffff;'
              : 'color: var(--text-secondary);'"
            :title="t('nav.modeStream')"
            @click="mediaStore.currentMode = 'stream'"
          >
            <Compass
              class="w-3.5 h-3.5 shrink-0"
              :style="mediaStore.currentMode === 'stream' ? 'color: #ffffff;' : 'color: var(--accent-text);'"
            />
            <span>{{ t('nav.modeStream') }}</span>
          </button>

          <button
            data-testid="nav-mode-workplace"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
            :style="mediaStore.currentMode === 'workplace' && mediaStore.workplaceView === 'assets'
              ? 'background-color: var(--accent-color); color: #ffffff;'
              : 'color: var(--text-secondary);'"
            :title="t('nav.modeWorkplace')"
            @click="mediaStore.currentMode = 'workplace'; mediaStore.workplaceView = 'assets'; mediaStore.loadWorkplaceItems()"
          >
            <FolderOpen
              class="w-3.5 h-3.5 shrink-0"
              :style="mediaStore.currentMode === 'workplace' && mediaStore.workplaceView === 'assets' ? 'color: #ffffff;' : 'color: var(--accent-text);'"
            />
            <span>{{ t('nav.modeWorkplace') }}</span>
          </button>

          <button
            data-testid="nav-mode-taxonomy"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
            :style="mediaStore.currentMode === 'workplace' && mediaStore.workplaceView === 'taxonomy'
              ? 'background-color: var(--accent-color); color: #ffffff;'
              : 'color: var(--text-secondary);'"
            :title="t('nav.modeTaxonomy')"
            @click="mediaStore.openTaxonomyWorkspace()"
          >
            <Tags
              class="w-3.5 h-3.5 shrink-0"
              :style="mediaStore.currentMode === 'workplace' && mediaStore.workplaceView === 'taxonomy' ? 'color: #ffffff;' : 'color: var(--accent-text);'"
            />
            <span>{{ t('nav.modeTaxonomy') }}</span>
          </button>

          <button
            data-testid="nav-mode-organize"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
            :style="mediaStore.currentMode === 'workplace' && mediaStore.workplaceView === 'organize'
              ? 'background-color: var(--accent-color); color: #ffffff;'
              : 'color: var(--text-secondary);'"
            :title="t('nav.modeOrganize')"
            @click="mediaStore.openOrganizeWorkspace('pipeline')"
          >
            <Workflow
              class="w-3.5 h-3.5 shrink-0"
              :style="mediaStore.currentMode === 'workplace' && mediaStore.workplaceView === 'organize' ? 'color: #ffffff;' : 'color: var(--accent-text);'"
            />
            <span>{{ t('nav.modeOrganize') }}</span>
          </button>
        </nav>
      </div>

      <!-- Center: Dual-Track Master Console Status Capsule -->
      <div
        v-if="playerStore.activeBgUnit || playerStore.bgQueue.length > 0 || (playerStore.fgViewerOpen && playerStore.fgAutoPlay)"
        class="hidden md:flex items-center gap-2.5 px-3 py-1 rounded-full border select-none max-w-sm sm:max-w-md truncate"
        style="background-color: var(--bg-app); border-color: var(--border-color);"
      >
        <div
          v-if="playerStore.activeBgUnit"
          class="flex items-center gap-2 min-w-0"
        >
          <button
            class="relative flex items-center justify-center w-6 h-6 rounded-full border shrink-0 transition-transform cursor-pointer"
            style="background-color: var(--bg-surface-elevated); border-color: var(--border-hover); color: var(--text-primary);"
            :title="t('nav.bgAudioTitle', { title: tData(playerStore.activeBgUnit.title) })"
            @click="playerStore.setBgViewMode(playerStore.bgViewMode === 'mini' ? 'disc' : 'mini')"
          >
            <Music
              class="w-3 h-3"
              :class="{ 'animate-pulse': playerStore.isBgPlaying }"
            />
          </button>

          <span
            class="text-xs truncate cursor-pointer font-medium max-w-[100px] sm:max-w-[140px]"
            style="color: var(--text-primary);"
            :title="tData(playerStore.activeBgUnit.title)"
            @click="playerStore.setBgViewMode('mini')"
          >
            {{ tData(playerStore.activeBgUnit.title) }}
          </span>

          <div class="flex items-center gap-0.5">
            <button
              class="p-1 transition-colors cursor-pointer"
              style="color: var(--text-secondary);"
              :title="playerStore.isBgPlaying ? t('nav.pauseBg') : t('nav.playBg')"
              @click.stop="playerStore.togglePlayAudio"
            >
              <Pause v-if="playerStore.isBgPlaying" class="w-3.5 h-3.5" />
              <Play v-else class="w-3.5 h-3.5" />
            </button>
            <button
              class="p-1 transition-colors cursor-pointer"
              style="color: var(--text-secondary);"
              :title="t('nav.nextTrack')"
              @click.stop="playerStore.nextAudio"
            >
              <SkipForward class="w-3 h-3" />
            </button>
          </div>

          <button
            class="p-1 transition-colors relative cursor-pointer"
            style="color: var(--text-secondary);"
            :title="t('nav.openBgQueue', { count: playerStore.bgQueue.length })"
            @click.stop="playerStore.toggleQueueDrawer()"
          >
            <ListMusic class="w-3.5 h-3.5" />
          </button>

          <button
            class="p-1 transition-colors cursor-pointer"
            style="color: var(--text-secondary);"
            :title="t('nav.stopBg')"
            @click.stop="playerStore.stopAndExitBgPlayback()"
          >
            <Power class="w-3.5 h-3.5" />
          </button>
        </div>

        <div
          v-else-if="playerStore.bgQueue.length > 0"
          class="flex items-center gap-1.5 cursor-pointer text-xs px-1.5 py-0.5 rounded-lg transition-colors"
          style="color: var(--text-secondary);"
          :title="t('nav.openBgQueue', { count: playerStore.bgQueue.length })"
          @click="playerStore.toggleQueueDrawer()"
        >
          <ListMusic class="w-3.5 h-3.5" />
          <span class="font-mono text-[11px]">{{ t('nav.queuePill', { count: playerStore.bgQueue.length }) }}</span>
          <button
            class="p-1 rounded ml-0.5 cursor-pointer"
            style="color: var(--text-primary);"
            :title="t('nav.startQueue')"
            @click.stop="playerStore.playAudio(playerStore.bgQueue[0], playerStore.bgQueue, 'disc')"
          >
            <Play class="w-3 h-3" />
          </button>
        </div>

        <div
          v-if="playerStore.fgViewerOpen && playerStore.fgAutoPlay"
          class="flex items-center gap-1.5 pl-2 border-l shrink-0 text-xs font-medium"
          style="border-color: var(--border-color); color: var(--text-secondary);"
        >
          <Tv class="w-3.5 h-3.5" />
          <span class="font-mono text-[11px]">{{ t('nav.slideshowPill', { sec: playerStore.fgTimeRemaining }) }}</span>
        </div>
      </div>

      <!-- Right: Monochrome Utility Controls -->
      <div class="flex items-center gap-1.5 shrink-0">
        <!-- Search Input / Button -->
        <div class="relative flex items-center">
          <div
            v-if="isSearchOpen || mediaStore.searchQuery"
            class="flex items-center border rounded-lg px-2.5 py-1.5 transition-all duration-200 w-44 sm:w-60"
            style="background-color: var(--bg-app); border-color: var(--border-color);"
          >
            <Search class="w-3.5 h-3.5 shrink-0 mr-1.5" style="color: var(--text-muted);" />
            <input
              ref="searchInputRef"
              v-model="mediaStore.searchQuery"
              type="text"
              :placeholder="t('nav.searchPlaceholder')"
              class="bg-transparent w-full text-xs focus:outline-none"
              style="color: var(--text-primary);"
              @blur="onSearchBlur"
              @keydown.esc="onSearchEsc"
            >
            <button
              v-if="mediaStore.searchQuery"
              class="shrink-0 ml-1 p-0.5 cursor-pointer"
              style="color: var(--text-muted);"
              :title="t('nav.clearSearch')"
              @click="mediaStore.searchQuery = ''"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
          <button
            v-else
            class="p-2 rounded-lg transition-colors border border-transparent cursor-pointer"
            style="color: var(--text-secondary);"
            :title="t('nav.searchTooltip')"
            @click="toggleSearch"
          >
            <Search class="w-4 h-4" />
          </button>
        </div>

        <!-- Quick Scan Modal Trigger -->
        <button
          class="p-2 rounded-lg transition-colors border border-transparent cursor-pointer"
          style="color: var(--accent-text);"
          :title="t('nav.scanTooltip')"
          @click="mediaStore.scanModalOpen = true"
        >
          <FolderSearch class="w-4 h-4" />
        </button>

        <!-- Refresh Current View -->
        <button
          :title="t('nav.refreshTooltip')"
          class="p-2 rounded-lg transition-colors border border-transparent cursor-pointer text-emerald-400"
          @click="handleRefresh"
        >
          <RefreshCw :class="['w-4 h-4', mediaStore.loading ? 'animate-spin' : '']" />
        </button>

        <!-- Direct 1-Click Dark / Light Theme Toggle -->
        <button
          data-testid="theme-toggle-btn"
          class="p-2 rounded-lg transition-colors border border-transparent cursor-pointer"
          :title="t('nav.themeTooltip', { name: tData(themeStore.currentTheme.name) })"
          @click="themeStore.toggleTheme()"
        >
          <Sun v-if="themeStore.isDarkMode" class="w-4 h-4 text-amber-400" />
          <Moon v-else class="w-4 h-4 text-indigo-500" />
        </button>

        <!-- Bilingual Toggle Button -->
        <button
          data-testid="lang-toggle-btn"
          data-action="toggle-locale"
          :title="t('nav.langTooltip')"
          class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors border cursor-pointer select-none shrink-0"
          style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-primary);"
          @click="toggleLocale()"
        >
          <Globe class="w-3.5 h-3.5 shrink-0" style="color: var(--accent-text);" />
          <span>{{ locale === 'zh' ? 'EN' : '中文' }}</span>
        </button>
      </div>
    </div>
  </header>
</template>
