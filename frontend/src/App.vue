<script setup>
import { onMounted } from 'vue'
import { useMediaStore } from './stores/mediaStore'
import { useThemeStore } from './stores/themeStore'
import { usePlayerStore } from './stores/playerStore'
import { t } from './i18n'
import Navbar from './components/Navbar.vue'
import StreamFeed from './components/StreamFeed.vue'
import Workplace from './components/Workplace.vue'
import VideoPlayerModal from './components/VideoPlayerModal.vue'
import ImageViewerModal from './components/ImageViewerModal.vue'
import FloatingMiniPlayer from './components/FloatingMiniPlayer.vue'
import AudioImmersiveModal from './components/AudioImmersiveModal.vue'
import ScanModal from './components/ScanModal.vue'
import PhysicalOrganizerModal from './components/PhysicalOrganizerModal.vue'
import BackgroundQueueDrawer from './components/BackgroundQueueDrawer.vue'

const mediaStore = useMediaStore()
const themeStore = useThemeStore()
const playerStore = usePlayerStore()

onMounted(() => {
  themeStore.initTheme()
  mediaStore.init()
})
</script>

<template>
  <div
    class="min-h-screen flex flex-col font-sans transition-colors duration-200"
    style="background-color: var(--bg-app); color: var(--text-primary);"
  >
    <!-- Top Navigation Bar -->
    <Navbar />

    <!-- Global Maintenance Warning Banner -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="mediaStore.maintenanceLocks.length > 0"
        class="border-b px-4 py-2.5 flex items-center justify-between text-xs sticky top-14 z-30"
        style="background-color: var(--bg-surface-elevated); border-color: var(--border-hover); color: var(--text-primary);"
      >
        <div class="flex items-center gap-2 max-w-5xl mx-auto w-full">
          <span class="w-2 h-2 rounded-full shrink-0" style="background-color: var(--accent-color);" />
          <span class="font-semibold tracking-wide">{{ t('app.maintenanceTitle') }}</span>
          <span class="truncate" style="color: var(--text-secondary);">
            {{ mediaStore.maintenanceLocks.map(l => l.reason || l.folder_path).join('；') }}
          </span>
          <span class="ml-2 hidden sm:inline" style="color: var(--text-muted);">{{ t('app.maintenanceHint') }}</span>
        </div>
      </div>
    </Transition>

    <!-- Main Content Area -->
    <main class="flex-grow pb-24">
      <StreamFeed v-if="mediaStore.currentMode === 'stream'" />
      <Workplace v-else-if="mediaStore.currentMode === 'workplace'" />
    </main>

    <!-- Modals & Overlays -->
    <VideoPlayerModal />
    <ImageViewerModal />
    <FloatingMiniPlayer />
    <AudioImmersiveModal />
    <ScanModal />
    <PhysicalOrganizerModal />
    <BackgroundQueueDrawer />

    <!-- Global Floating Toast Notification -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-3 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 translate-y-3 scale-95"
    >
      <div
        v-if="playerStore.toast.visible"
        class="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl shadow-xl border text-xs font-medium flex items-center gap-2.5 pointer-events-none select-none"
        style="background-color: var(--bg-surface-elevated); border-color: var(--border-hover); color: var(--text-primary);"
      >
        <span class="w-2 h-2 rounded-full shrink-0" style="background-color: var(--accent-color);" />
        <span class="tracking-wide">{{ playerStore.toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>
