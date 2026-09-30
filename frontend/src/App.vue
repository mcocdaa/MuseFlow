<script setup>
import { onMounted } from 'vue'
import { useMediaStore } from './stores/mediaStore'
import Navbar from './components/Navbar.vue'
import StreamFeed from './components/StreamFeed.vue'
import Workplace from './components/Workplace.vue'
import VideoPlayerModal from './components/VideoPlayerModal.vue'
import ImageViewerModal from './components/ImageViewerModal.vue'
import AudioPlayerBar from './components/AudioPlayerBar.vue'
import ScanModal from './components/ScanModal.vue'
import AIRecapModal from './components/AIRecapModal.vue'

const mediaStore = useMediaStore()

onMounted(() => {
  mediaStore.init()
})
</script>

<template>
  <div class="min-h-screen bg-[#0f1117] text-gray-100 flex flex-col font-sans selection:bg-purple-500/30 selection:text-purple-200">
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
  </div>
</template>
