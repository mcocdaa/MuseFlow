<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { usePlayerStore } from '../stores/playerStore'
import { useMediaStore } from '../stores/mediaStore'
import {
  X,
  Heart,
  Star,
  FolderOpen,
  ExternalLink,
  ZoomIn,
  ZoomOut,
  RotateCcw
} from 'lucide-vue-next'
import { revealInExplorer, openWithDefaultApp } from '../api'

const playerStore = usePlayerStore()
const mediaStore = useMediaStore()

const zoomLevel = ref(1)

const currentUnit = computed(() => playerStore.activeImageUnit)
const primaryFile = computed(() => {
  if (!currentUnit.value?.files) return null
  return currentUnit.value.files[0]
})

const imageUrl = computed(() => {
  if (!primaryFile.value) return ''
  return `/api/stream/file/${primaryFile.value.id}`
})

const handleKeyDown = (e) => {
  if (!playerStore.imageModalOpen) return
  if (e.key === 'Escape') {
    playerStore.closeImage()
  }
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown))

const zoomIn = () => { zoomLevel.value = Math.min(zoomLevel.value + 0.25, 3) }
const zoomOut = () => { zoomLevel.value = Math.max(zoomLevel.value - 0.25, 0.5) }
const resetZoom = () => { zoomLevel.value = 1 }

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
    v-if="playerStore.imageModalOpen && currentUnit"
    class="fixed inset-0 z-50 bg-black/95 flex items-center justify-center backdrop-blur-xl animate-fade-in select-none"
  >
    <!-- Top Bar Controls -->
    <div class="absolute top-5 inset-x-5 flex items-center justify-between z-20">
      <div class="flex items-center gap-3">
        <h3 class="text-sm font-medium text-white/90 truncate max-w-md">
          {{ currentUnit.title }}
        </h3>
        <span class="text-xs text-gray-400">
          {{ currentUnit.width }}x{{ currentUnit.height }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <!-- Zoom Controls -->
        <div class="flex items-center gap-1 bg-white/10 backdrop-blur-md rounded-xl p-1 border border-white/10">
          <button @click="zoomOut" class="p-1.5 text-gray-300 hover:text-white rounded-lg hover:bg-white/10" title="缩小">
            <ZoomOut class="w-4 h-4" />
          </button>
          <button @click="resetZoom" class="p-1.5 text-gray-300 hover:text-white rounded-lg hover:bg-white/10" title="复位">
            <RotateCcw class="w-4 h-4" />
          </button>
          <button @click="zoomIn" class="p-1.5 text-gray-300 hover:text-white rounded-lg hover:bg-white/10" title="放大">
            <ZoomIn class="w-4 h-4" />
          </button>
        </div>

        <!-- Open External -->
        <button
          @click="revealInExplorer({ unit_id: currentUnit.id })"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-blue-400"
          title="在资源管理器中定位"
        >
          <FolderOpen class="w-5 h-5" />
        </button>
        <button
          @click="openWithDefaultApp({ unit_id: currentUnit.id })"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-purple-400"
          title="使用系统默认看图软件打开"
        >
          <ExternalLink class="w-5 h-5" />
        </button>

        <!-- Close -->
        <button
          @click="playerStore.closeImage()"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white"
          title="关闭 (Esc)"
        >
          <X class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- Image Display -->
    <div class="w-full h-full flex items-center justify-center p-8 overflow-hidden">
      <img
        :src="imageUrl"
        :alt="currentUnit.title"
        :style="{ transform: `scale(${zoomLevel})` }"
        class="max-w-full max-h-full object-contain transition-transform duration-200 shadow-2xl rounded-lg"
      />
    </div>

    <!-- Bottom Rating & Favorite Bar -->
    <div class="absolute bottom-6 inset-x-0 flex items-center justify-center z-20">
      <div class="flex items-center gap-4 bg-white/10 backdrop-blur-md px-5 py-2 rounded-full border border-white/10">
        <!-- 5-Star Rating -->
        <div class="flex items-center gap-1">
          <button
            v-for="s in 5"
            :key="s"
            @click="setRating(s)"
            class="p-0.5 hover:scale-125 transition-transform"
          >
            <Star
              :class="[
                'w-4 h-4',
                s <= currentUnit.rating ? 'text-amber-400 fill-amber-400' : 'text-gray-500'
              ]"
            />
          </button>
        </div>

        <div class="w-px h-4 bg-white/20"></div>

        <!-- Favorite -->
        <button @click="toggleFavorite" class="flex items-center gap-1 text-xs text-white">
          <Heart
            :class="[
              'w-5 h-5 transition-transform active:scale-125',
              currentUnit.is_favorite ? 'text-rose-500 fill-rose-500' : 'text-gray-300'
            ]"
          />
          <span>{{ currentUnit.is_favorite ? '已收藏' : '收藏' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
