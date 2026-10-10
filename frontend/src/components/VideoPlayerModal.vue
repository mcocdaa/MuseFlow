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
  Subtitles,
  Maximize,
  PictureInPicture2,
  Sliders,
  Type,
  MoveVertical,
  ListVideo,
  Plus,
  Video,
  Volume2,
  VolumeX,
  Volume1
} from 'lucide-vue-next'
import { revealInExplorer, openWithDefaultApp } from '../api'

const playerStore = usePlayerStore()
const mediaStore = useMediaStore()
const videoRef = ref(null)
const containerRef = ref(null)

const activeCueText = ref('')
const showSubtitleSettings = ref(false)
const isDraggingSubtitle = ref(false)

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

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    if (containerRef.value?.requestFullscreen) {
      containerRef.value.requestFullscreen().catch(() => {})
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(() => {})
    }
  }
}

const togglePlayPause = () => {
  if (!videoRef.value) return
  if (videoRef.value.paused) {
    videoRef.value.play().catch(() => {})
  } else {
    videoRef.value.pause()
  }
}

const handleKeyDown = (e) => {
  if (!playerStore.videoModalOpen) return
  if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return

  if (e.key === 'Escape') {
    playerStore.closeVideo()
  } else if (e.key === ' ' || e.code === 'Space') {
    e.preventDefault()
    togglePlayPause()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    if (videoRef.value) {
      videoRef.value.currentTime = Math.max(0, videoRef.value.currentTime - 5)
    }
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    if (videoRef.value) {
      videoRef.value.currentTime = Math.min(videoRef.value.duration || 99999, videoRef.value.currentTime + 5)
    }
  } else if (e.key === 'f' || e.key === 'F') {
    e.preventDefault()
    toggleFullscreen()
  } else if (e.key === 'p' || e.key === 'P') {
    e.preventDefault()
    playerStore.minimizeVideoToPiP()
  } else if (e.key === 'm' || e.key === 'M') {
    e.preventDefault()
    playerStore.toggleVideoMute()
    syncVideoVolume()
    playerStore.showToast(playerStore.videoVolume === 0 ? '已静音' : `音量: ${Math.round(playerStore.videoVolume * 100)}%`)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    const newVol = Math.min(1, Math.round((playerStore.videoVolume + 0.05) * 100) / 100)
    playerStore.setVideoVolume(newVol)
    syncVideoVolume()
    playerStore.showToast(`音量: ${Math.round(newVol * 100)}%`)
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    const newVol = Math.max(0, Math.round((playerStore.videoVolume - 0.05) * 100) / 100)
    playerStore.setVideoVolume(newVol)
    syncVideoVolume()
    playerStore.showToast(`音量: ${Math.round(newVol * 100)}%`)
  } else if (e.key === ']' || e.key === 'PageDown') {
    e.preventDefault()
    playerStore.nextVideo()
  } else if (e.key === '[' || e.key === 'PageUp') {
    e.preventDefault()
    playerStore.prevVideo()
  }
}

const syncVideoVolume = () => {
  if (videoRef.value) {
    videoRef.value.volume = playerStore.videoVolume
    videoRef.value.muted = (playerStore.videoVolume === 0)
  }
}

watch(() => playerStore.videoVolume, (vol) => {
  if (videoRef.value) {
    videoRef.value.volume = vol
    videoRef.value.muted = (vol === 0)
  }
})

// Subtitle cue detection
const setupSubtitleTracking = () => {
  if (!videoRef.value) return
  const trackEl = videoRef.value.querySelector('track')
  if (!trackEl) return

  trackEl.addEventListener('cuechange', (e) => {
    const track = e.target.track
    if (track && track.activeCues && track.activeCues.length > 0) {
      activeCueText.value = track.activeCues[0].text
    } else {
      activeCueText.value = ''
    }
  })
}

// Subtitle drag handling
const startSubtitleDrag = (e) => {
  isDraggingSubtitle.value = true
  window.addEventListener('mousemove', onSubtitleDrag)
  window.addEventListener('mouseup', stopSubtitleDrag)
}

const onSubtitleDrag = (e) => {
  if (!isDraggingSubtitle.value || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const distFromBottom = rect.bottom - e.clientY
  const pct = Math.round((distFromBottom / rect.height) * 100)
  playerStore.setSubtitleVerticalPercent(pct)
}

const stopSubtitleDrag = () => {
  isDraggingSubtitle.value = false
  window.removeEventListener('mousemove', onSubtitleDrag)
  window.removeEventListener('mouseup', stopSubtitleDrag)
}

const onVideoEnded = () => {
  if (playerStore.videoQueueIndex < playerStore.videoQueue.length - 1) {
    playerStore.nextVideo()
  }
}

const onVideoError = (e) => {
  console.warn('Video playback error:', e)
  playerStore.showToast('视频加载失败：NAS 存储网络连接超时或设备休眠中')
}

watch(currentUnit, (newVal, oldVal) => {
  activeCueText.value = ''
  if (videoRef.value) {
    videoRef.value.currentTime = 0
    syncVideoVolume()
    if (oldVal) {
      videoRef.value.play().catch(() => {})
    }
    setTimeout(setupSubtitleTracking, 300)
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  syncVideoVolume()
  setTimeout(setupSubtitleTracking, 500)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('mousemove', onSubtitleDrag)
  window.removeEventListener('mouseup', stopSubtitleDrag)
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
    <!-- Close & Controls button -->
    <div class="absolute top-5 right-5 z-40 flex items-center gap-2">
      <!-- Subtitle Styling & Config Popover -->
      <div v-if="subtitleFile" class="relative">
        <button
          @click="showSubtitleSettings = !showSubtitleSettings"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
          title="字幕显示与拖拽设置"
        >
          <Sliders class="w-5 h-5" />
        </button>

        <div
          v-if="showSubtitleSettings"
          class="absolute right-0 top-full mt-2 w-64 p-3 bg-neutral-900 border border-white/15 rounded-2xl shadow-2xl backdrop-blur-xl text-xs space-y-3 z-50"
        >
          <div class="font-semibold text-white flex items-center justify-between pb-1.5 border-b border-white/10">
            <span>字幕样式与位置</span>
            <button @click="showSubtitleSettings = false" class="text-gray-400 hover:text-white">
              <X class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Vertical drag hint -->
          <div class="flex items-center justify-between text-gray-300">
            <span class="flex items-center gap-1.5">
              <MoveVertical class="w-3.5 h-3.5 text-purple-400" />
              <span>垂直高度 (可直接拖动字幕):</span>
            </span>
            <span class="font-mono text-purple-300 font-semibold">{{ playerStore.subtitleConfig.verticalPercent }}%</span>
          </div>

          <!-- Font Size Selector -->
          <div>
            <div class="text-[11px] text-gray-400 mb-1.5 flex items-center gap-1">
              <Type class="w-3.5 h-3.5" />
              <span>字体大小:</span>
            </div>
            <div class="grid grid-cols-4 gap-1">
              <button
                v-for="size in [
                  { id: 'sm', label: '小' },
                  { id: 'md', label: '中' },
                  { id: 'lg', label: '大' },
                  { id: 'xl', label: '特大' }
                ]"
                :key="size.id"
                @click="playerStore.setSubtitleFontSize(size.id)"
                :class="[
                  'py-1 rounded-lg text-center transition-colors',
                  playerStore.subtitleConfig.fontSize === size.id
                    ? 'bg-purple-600 text-white font-semibold'
                    : 'bg-white/5 text-gray-300 hover:bg-white/10'
                ]"
              >
                {{ size.label }}
              </button>
            </div>
          </div>

          <!-- Background Style Selector -->
          <div>
            <div class="text-[11px] text-gray-400 mb-1.5">背景模式:</div>
            <div class="grid grid-cols-2 gap-1.5">
              <button
                @click="playerStore.setSubtitleStyle('shadow')"
                :class="[
                  'py-1 px-2 rounded-lg text-center transition-colors',
                  playerStore.subtitleConfig.style === 'shadow'
                    ? 'bg-purple-600 text-white font-semibold'
                    : 'bg-white/5 text-gray-300 hover:bg-white/10'
                ]"
              >
                文字描边
              </button>
              <button
                @click="playerStore.setSubtitleStyle('glass')"
                :class="[
                  'py-1 px-2 rounded-lg text-center transition-colors',
                  playerStore.subtitleConfig.style === 'glass'
                    ? 'bg-purple-600 text-white font-semibold'
                    : 'bg-white/5 text-gray-300 hover:bg-white/10'
                ]"
              >
                半透明底框
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Series Episode Drawer Toggle -->
      <button
        v-if="playerStore.videoQueue.length > 1"
        @click="playerStore.toggleVideoDrawer()"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition-colors"
        :class="playerStore.videoDrawerOpen ? 'bg-purple-600 text-white font-medium shadow-md' : 'bg-white/10 hover:bg-white/20 text-white/90'"
        title="查看本系列选集列表"
      >
        <ListVideo class="w-4 h-4" />
        <span>选集 ({{ playerStore.videoQueue.length }})</span>
      </button>

      <!-- Interactive Volume Control Slider -->
      <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/10 backdrop-blur-md border border-white/10 hover:bg-white/15 transition-all group/vol">
        <button
          @click="playerStore.toggleVideoMute()"
          class="p-1 rounded-full text-white/80 hover:text-white transition-colors"
          :title="playerStore.videoVolume === 0 ? '取消静音 (M)' : '静音 (M)'"
        >
          <VolumeX v-if="playerStore.videoVolume === 0" class="w-4 h-4 text-rose-400" />
          <Volume1 v-else-if="playerStore.videoVolume < 0.5" class="w-4 h-4 text-purple-300" />
          <Volume2 v-else class="w-4 h-4 text-purple-300" />
        </button>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          :value="playerStore.videoVolume"
          @input="playerStore.setVideoVolume($event.target.value)"
          class="w-16 md:w-24 h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-400 hover:accent-purple-300"
          :title="`音量: ${Math.round(playerStore.videoVolume * 100)}% (↑/↓ 键)`"
        />
        <span class="text-[11px] font-mono text-gray-300 w-8 text-right select-none">
          {{ Math.round(playerStore.videoVolume * 100) }}%
        </span>
      </div>

      <!-- Picture-in-Picture / Minimize to Mini-window button -->
      <button
        @click="playerStore.minimizeVideoToPiP()"
        class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
        title="小窗化悬浮播放 (P) — 可继续浏览相册/网页"
      >
        <PictureInPicture2 class="w-5 h-5 text-indigo-400" />
      </button>

      <!-- Fullscreen button -->
      <button
        @click="toggleFullscreen"
        class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
        title="全屏 (F)"
      >
        <Maximize class="w-5 h-5" />
      </button>

      <!-- Close button -->
      <button
        @click="playerStore.closeVideo()"
        class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
        title="关闭 (Esc)"
      >
        <X class="w-6 h-6" />
      </button>
    </div>

    <!-- Keyboard Shortcut Hint Badge (Top Left) -->
    <div class="absolute top-5 left-5 z-20 hidden md:flex items-center gap-2 bg-black/60 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-white/10 text-[11px] text-gray-300">
      <span class="text-purple-400 font-semibold">快捷键:</span>
      <span>[空格] 播放/暂停</span>
      <span class="text-gray-500">·</span>
      <span>[↑/↓] 音量调节</span>
      <span class="text-gray-500">·</span>
      <span>[M] 静音</span>
      <span class="text-gray-500">·</span>
      <span>[←/→] 5s快进退</span>
      <span class="text-gray-500">·</span>
      <span>[P] 小窗化</span>
      <span class="text-gray-500">·</span>
      <span>[F] 全屏</span>
    </div>

    <!-- Main Container -->
    <div ref="containerRef" class="relative w-full h-full max-w-5xl max-h-[90vh] flex flex-col items-center justify-center p-4">
      <!-- Video Element -->
      <div class="relative w-full h-full flex items-center justify-center overflow-hidden rounded-2xl bg-black shadow-2xl">
        <video
          ref="videoRef"
          :src="videoStreamUrl"
          controls
          playsinline
          class="max-w-full max-h-full object-contain"
          @loadedmetadata="syncVideoVolume"
          @play="syncVideoVolume"
          @ended="onVideoEnded"
          @error="onVideoError"
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

        <!-- Custom Interactive Draggable Subtitle Display -->
        <div
          v-if="subtitleFile && activeCueText"
          @mousedown.prevent="startSubtitleDrag"
          class="absolute inset-x-0 flex justify-center z-30 select-none cursor-ns-resize group/sub"
          :style="{ bottom: `${playerStore.subtitleConfig.verticalPercent}%` }"
          title="按住鼠标上下拖拽调整字幕位置"
        >
          <div
            class="transition-all duration-100 px-4 py-1.5 rounded-xl max-w-2xl text-center leading-relaxed font-sans"
            :class="[
              playerStore.subtitleConfig.style === 'glass'
                ? 'bg-black/80 backdrop-blur-md border border-white/20 text-white shadow-2xl'
                : 'text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] [text-shadow:_0_2px_8px_rgb(0_0_0_/_95%),_0_0_3px_rgb(0_0_0_/_95%)]',
              playerStore.subtitleConfig.fontSize === 'sm' ? 'text-sm' :
              playerStore.subtitleConfig.fontSize === 'lg' ? 'text-2xl font-semibold' :
              playerStore.subtitleConfig.fontSize === 'xl' ? 'text-3xl font-bold' : 'text-lg font-medium',
              isDraggingSubtitle ? 'ring-2 ring-purple-500 scale-105' : 'group-hover/sub:ring-1 group-hover/sub:ring-white/30'
            ]"
          >
            {{ activeCueText }}
          </div>
        </div>

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
              <span>智能挂载字幕</span>
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

    <!-- Series Episode Drawer Slide-over -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="translate-x-0"
      leave-to-class="translate-x-full"
    >
      <div
        v-if="playerStore.videoDrawerOpen"
        class="fixed right-0 top-0 bottom-0 w-80 sm:w-96 z-50 p-6 flex flex-col shadow-2xl border-l border-white/10 backdrop-blur-2xl"
        style="background-color: var(--bg-surface-elevated);"
      >
        <!-- Drawer Header -->
        <div class="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <div class="flex items-center gap-2">
              <ListVideo class="w-4 h-4 text-purple-400" />
              <span class="text-sm font-semibold text-white">系列选集列表</span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-white/10 text-purple-300 font-mono">
                {{ playerStore.videoQueue.length }}
              </span>
            </div>
            <p class="text-[11px] text-gray-400 mt-1 truncate max-w-[240px]">
              {{ currentUnit.collection_name || '当前系列' }}
            </p>
          </div>
          <button
            @click="playerStore.toggleVideoDrawer()"
            class="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Toolbar: Add series to background -->
        <div class="py-2.5 border-b border-white/10 flex items-center justify-between">
          <button
            @click="playerStore.addMultipleToBgQueue(playerStore.videoQueue)"
            class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium text-purple-200 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 transition-all"
            title="将整个系列的视频追加到背景队列"
          >
            <Plus class="w-3.5 h-3.5 text-purple-400" />
            <span>全系列加入背景队列</span>
          </button>
        </div>

        <!-- Episode List -->
        <div class="flex-grow overflow-y-auto pr-1 py-3 space-y-1.5">
          <div
            v-for="(unit, idx) in playerStore.videoQueue"
            :key="unit.id"
            @click="playerStore.selectVideoIndex(idx)"
            :class="[
              'group p-2.5 rounded-xl border flex items-center justify-between gap-2 cursor-pointer transition-all select-none',
              idx === playerStore.videoQueueIndex
                ? 'bg-purple-600/25 border-purple-500/40 text-purple-200 shadow-sm'
                : 'bg-white/5 border-transparent text-gray-300 hover:bg-white/10 hover:border-white/10'
            ]"
          >
            <div class="flex items-center gap-2 truncate">
              <span class="text-[11px] font-mono text-gray-500 w-5 text-center shrink-0">
                {{ (idx + 1).toString().padStart(2, '0') }}
              </span>
              <span class="text-xs font-medium truncate" :title="unit.title">
                {{ unit.title }}
              </span>
            </div>

            <div class="flex items-center gap-1 shrink-0">
              <Video
                v-if="idx === playerStore.videoQueueIndex"
                class="w-3.5 h-3.5 text-purple-400 mr-1 animate-pulse"
              />
              <span v-if="unit.duration_seconds" class="text-[10px] font-mono text-gray-500">
                {{ Math.floor(unit.duration_seconds / 60) }}:{{ Math.floor(unit.duration_seconds % 60).toString().padStart(2, '0') }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Hide native default browser cue text so our custom draggable subtitle takes over cleanly */
video::cue {
  display: none !important;
  color: transparent !important;
}
</style>
