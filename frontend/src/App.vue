<script setup>
import { onMounted } from 'vue'
import { useMediaStore } from './stores/mediaStore'
import { useThemeStore } from './stores/themeStore'
import { usePlayerStore } from './stores/playerStore'
import Navbar from './components/Navbar.vue'
import StreamFeed from './components/StreamFeed.vue'
import Workplace from './components/Workplace.vue'
import VideoPlayerModal from './components/VideoPlayerModal.vue'
import ImageViewerModal from './components/ImageViewerModal.vue'
import FloatingMiniPlayer from './components/FloatingMiniPlayer.vue'
import AudioImmersiveModal from './components/AudioImmersiveModal.vue'
import ScanModal from './components/ScanModal.vue'
import AIRecapModal from './components/AIRecapModal.vue'
import AIOrganizerModal from './components/AIOrganizerModal.vue'
import PhysicalOrganizerModal from './components/PhysicalOrganizerModal.vue'
import ThemePickerModal from './components/ThemePickerModal.vue'
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
    class="min-h-screen flex flex-col font-sans transition-colors duration-300"
    style="background-color: var(--bg-app); color: var(--text-primary);"
  >
    <!-- Top Navigation Bar -->
    <Navbar />

    <!-- Global Maintenance Warning Banner -->
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="mediaStore.maintenanceLocks.length > 0"
        class="bg-amber-500/15 border-b border-amber-500/30 px-4 py-2.5 flex items-center justify-between text-xs text-amber-200 backdrop-blur-md sticky top-14 z-30"
      >
        <div class="flex items-center gap-2 max-w-5xl mx-auto w-full">
          <span class="w-2 h-2 rounded-full bg-amber-400 animate-ping shrink-0" />
          <span class="font-semibold tracking-wide">⚠️ 存储物理重组中：</span>
          <span class="truncate">
            {{ mediaStore.maintenanceLocks.map(l => l.reason || l.folder_path).join('；') }}
          </span>
          <span class="text-amber-300/70 ml-2 hidden sm:inline">（受影响目录作品展示与流媒体传输可能短暂刷新，其他区域不受影响）</span>
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
    <AIRecapModal />
    <AIOrganizerModal />
    <PhysicalOrganizerModal />
    <ThemePickerModal />
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
        class="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl shadow-2xl backdrop-blur-xl border border-white/15 text-xs font-medium text-white flex items-center gap-2.5 pointer-events-none select-none"
        style="background-color: var(--bg-surface-elevated); box-shadow: 0 10px 30px rgba(0,0,0,0.5);"
      >
        <span class="w-2 h-2 rounded-full bg-purple-400 shrink-0 animate-ping" />
        <span class="tracking-wide">{{ playerStore.toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>
