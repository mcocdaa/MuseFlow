<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { usePlayerStore } from '../stores/playerStore'
import { useMediaStore } from '../stores/mediaStore'
import {
  X,
  Heart,
  Star,
  ChevronUp,
  ChevronDown,
  FolderOpen,
  ExternalLink,
  Layers,
  Subtitles
} from 'lucide-vue-next'
import { revealInExplorer, openWithDefaultApp } from '../api'

const playerStore = usePlayerStore()
const mediaStore = useMediaStore()
const videoRef = ref(null)

const currentUnit = computed(() => playerStore.activeVideoUnit)

const primaryFile = computed(() => {
  if (!currentUnit.value?.files) return null
  return currentUnit.value.files.find(f => f.role === 'primary' || f.role === 'video') || currentUnit.value.files[0]
})

const subtitleFile = computed(() => {
  if (!currentUnit.value?.files) return null
  return currentUnit.value.files.find(f => f.role === 'subtitle')
})

const videoStreamUrl = computed(() => {
  if (!primaryFile.value) return ''
  return `/api/stream/file/${primaryFile.value.id}`
})

const subtitleStreamUrl = computed(() => {
  if (!subtitleFile.value) return ''
  return `/api/stream/subtitle/${subtitleFile.value.id}`
})

const handleKeyDown = (e) => {
  if (!playerStore.videoModalOpen) return
  if (e.key === 'Escape') {
    playerStore.closeVideo()
  } else if (e.key === 'ArrowDown') {
    playerStore.nextVideo()
  } else if (e.key === 'ArrowUp') {
    playerStore.prevVideo()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

watch(currentUnit, () => {
  if (videoRef.value) {
    videoRef.value.currentTime = 0
    videoRef.value.play().catch(() => {})
  }
})

const toggleFavorite = () => {
  if (currentUnit.value) {
    mediaStore.toggleFavorite(currentUnit.value.id)
  }
}

const setRating = (stars) => {
  if (currentUnit.value) {
    mediaStore.updateRating(currentUnit.value.id, stars)
  }
}
</script>

<template>
  <div
    v-if="playerStore.videoModalOpen && currentUnit"
    class="fixed inset-0 z-50 bg-black/95 flex items-center justify-center backdrop-blur-xl animate-fade-in select-none"
  >
    <!-- Close button -->
    <button
      @click="playerStore.closeVideo()"
      class="absolute top-5 right-5 z-20 p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
      title="关闭 (Esc)"
    >
      <X class="w-6 h-6" />
    </button>

    <!-- Main Container -->
    <div class="relative w-full h-full max-w-5xl max-h-[90vh] flex flex-col items-center justify-center p-4">
      <!-- Video Element -->
      <div class="relative w-full h-full flex items-center justify-center overflow-hidden rounded-2xl bg-black shadow-2xl">
        <video
          ref="videoRef"
          :src="videoStreamUrl"
          controls
          autoplay
          playsinline
          class="max-w-full max-h-full object-contain"
        >
          <!-- Automatic WebVTT Subtitle Loading -->
          <track
            v-if="subtitleFile"
            :src="subtitleStreamUrl"
            kind="subtitles"
            srclang="zh"
            label="中文/默认字幕"
            default
          />
        </video>

        <!-- Video Info Overlay (Bottom Left) -->
        <div class="absolute bottom-6 left-6 max-w-lg pointer-events-none drop-shadow-md">
          <div class="flex items-center gap-2 mb-1.5">
            <span
              v-if="currentUnit.unit_type === 'bundle'"
              class="flex items-center gap-1 bg-purple-600/90 text-white text-[11px] font-semibold px-2 py-0.5 rounded-md"
            >
              <Layers class="w-3 h-3" />
              <span>复合包</span>
            </span>
            <span
              v-if="subtitleFile"
              class="flex items-center gap-1 bg-emerald-600/90 text-white text-[11px] font-semibold px-2 py-0.5 rounded-md"
            >
              <Subtitles class="w-3 h-3" />
              <span>挂载字幕</span>
            </span>
            <span class="text-xs text-gray-300 font-medium">
              {{ currentUnit.collection_name || '未归类' }}
            </span>
          </div>
          <h2 class="text-lg font-bold text-white leading-tight">
            {{ currentUnit.title }}
          </h2>
        </div>
      </div>

      <!-- TikTok-style Vertical Side Actions (Right Side) -->
      <div class="absolute right-4 md:right-8 bottom-20 flex flex-col items-center gap-5 z-20">
        <!-- Next Video button -->
        <button
          @click="playerStore.prevVideo()"
          :disabled="playerStore.videoQueueIndex <= 0"
          :class="[
            'p-3 rounded-full bg-white/10 text-white backdrop-blur-md transition-all',
            playerStore.videoQueueIndex <= 0 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/20 active:scale-95'
          ]"
          title="上一个 (↑)"
        >
          <ChevronUp class="w-5 h-5" />
        </button>

        <button
          @click="playerStore.nextVideo()"
          :disabled="playerStore.videoQueueIndex >= playerStore.videoQueue.length - 1"
          :class="[
            'p-3 rounded-full bg-white/10 text-white backdrop-blur-md transition-all',
            playerStore.videoQueueIndex >= playerStore.videoQueue.length - 1 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/20 active:scale-95'
          ]"
          title="下一个 (↓)"
        >
          <ChevronDown class="w-5 h-5" />
        </button>

        <!-- Favorite -->
        <button
          @click="toggleFavorite"
          class="flex flex-col items-center gap-1 text-white"
        >
          <div class="p-3 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md transition-all active:scale-125">
            <Heart
              :class="[
                'w-6 h-6',
                currentUnit.is_favorite ? 'text-rose-500 fill-rose-500' : 'text-white'
              ]"
            />
          </div>
          <span class="text-[10px] text-gray-300">喜欢</span>
        </button>

        <!-- Star Rating -->
        <div class="flex flex-col items-center gap-1 text-white">
          <div class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md transition-all flex flex-col items-center gap-1">
            <button
              v-for="s in [5, 4, 3, 2, 1]"
              :key="s"
              @click="setRating(s)"
              class="p-0.5 hover:scale-125 transition-transform"
            >
              <Star
                :class="[
                  'w-3.5 h-3.5',
                  s <= currentUnit.rating ? 'text-amber-400 fill-amber-400' : 'text-gray-500'
                ]"
              />
            </button>
          </div>
          <span class="text-[10px] text-gray-300">评分</span>
        </div>

        <!-- Open in Explorer -->
        <button
          @click="revealInExplorer({ unit_id: currentUnit.id })"
          class="p-3 rounded-full bg-white/10 hover:bg-white/20 text-white backdrop-blur-md transition-all"
          title="在资源管理器中定位"
        >
          <FolderOpen class="w-5 h-5 text-blue-400" />
        </button>

        <!-- Open in Default App -->
        <button
          @click="openWithDefaultApp({ unit_id: currentUnit.id })"
          class="p-3 rounded-full bg-white/10 hover:bg-white/20 text-white backdrop-blur-md transition-all"
          title="系统默认播放器打开"
        >
          <ExternalLink class="w-5 h-5 text-purple-400" />
        </button>
      </div>
    </div>
  </div>
</template>
