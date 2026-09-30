<script setup>
import { onMounted } from 'vue'
import { useMediaStore } from './stores/mediaStore'
import { useThemeStore } from './stores/themeStore'
import Navbar from './components/Navbar.vue'
import StreamFeed from './components/StreamFeed.vue'
import Workplace from './components/Workplace.vue'
import VideoPlayerModal from './components/VideoPlayerModal.vue'
import ImageViewerModal from './components/ImageViewerModal.vue'
import AudioPlayerBar from './components/AudioPlayerBar.vue'
import ScanModal from './components/ScanModal.vue'
import AIRecapModal from './components/AIRecapModal.vue'
import AIOrganizerModal from './components/AIOrganizerModal.vue'
import ThemePickerModal from './components/ThemePickerModal.vue'

const mediaStore = useMediaStore()
const themeStore = useThemeStore()

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

    <!-- Main Content Area -->
    <main class="flex-grow pb-24">
      <StreamFeed v-if="mediaStore.currentMode === 'stream'" />
      <Workplace v-else-if="mediaStore.currentMode === 'workplace'" />
    </main>

    <!-- Modals & Overlays -->
    <VideoPlayerModal />
    <ImageViewerModal />
    <AudioPlayerBar />
    <ScanModal />
    <AIRecapModal />
    <AIOrganizerModal />
    <ThemePickerModal />
  </div>
</template>
