<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
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
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  Shuffle,
  Repeat,
  Repeat1,
  Timer,
  Clock,
  Layers,
  Video,
  Sparkles,
  Disc3,
  Volume2,
  VolumeX,
  SkipBack,
  SkipForward,
  Music
} from 'lucide-vue-next'
import { revealInExplorer, openWithDefaultApp } from '../api'

const playerStore = usePlayerStore()
const mediaStore = useMediaStore()

const zoomLevel = ref(1)
const showIntervalMenu = ref(false)
const fgVideoRef = ref(null)
const isIdle = ref(false)
let idleTimer = null

const onMouseMove = () => {
  isIdle.value = false
  if (idleTimer) clearTimeout(idleTimer)
  idleTimer = setTimeout(() => {
    if (playerStore.fgViewerOpen) {
      isIdle.value = true
    }
  }, 2500)
}

const currentUnit = computed(() => playerStore.activeFgUnit || playerStore.activeImageUnit)
const isVideo = computed(() => {
  if (!currentUnit.value) return false
  return currentUnit.value.unit_type === 'video' || currentUnit.value.unit_type === 'bundle'
})

const primaryFile = computed(() => {
  if (!currentUnit.value?.files?.length) return null
  return (
    currentUnit.value.files.find(f => f.role === 'primary' || f.role === 'video' || f.role === 'image') ||
    currentUnit.value.files[0]
  )
})

const mediaUrl = computed(() => {
  if (!primaryFile.value) return ''
  return `/api/stream/file/${primaryFile.value.id}`
})

const handleKeyDown = (e) => {
  if (!playerStore.fgViewerOpen) return
  if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return

  if (e.key === 'Escape') {
    playerStore.closeImage()
  } else if (e.key === ' ' || e.code === 'Space') {
    e.preventDefault()
    if (isVideo.value && fgVideoRef.value) {
      if (fgVideoRef.value.paused) fgVideoRef.value.play().catch(() => {})
      else fgVideoRef.value.pause()
    } else {
      playerStore.toggleFgAutoPlay()
    }
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    playerStore.prevFg()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
  } else if (e.key === 'ArrowUp' && isVideo.value) {
    e.preventDefault()
    const newVol = Math.min(1, Math.round((playerStore.videoVolume + 0.05) * 100) / 100)
    playerStore.setVideoVolume(newVol)
    syncFgVideoVolume()
    playerStore.showToast(`音量: ${Math.round(newVol * 100)}%`)
  } else if (e.key === 'ArrowDown' && isVideo.value) {
    e.preventDefault()
    const newVol = Math.max(0, Math.round((playerStore.videoVolume - 0.05) * 100) / 100)
    playerStore.setVideoVolume(newVol)
    syncFgVideoVolume()
    playerStore.showToast(`音量: ${Math.round(newVol * 100)}%`)
  } else if ((e.key === 'm' || e.key === 'M') && isVideo.value) {
    e.preventDefault()
    playerStore.toggleVideoMute()
    syncFgVideoVolume()
    playerStore.showToast(playerStore.videoVolume === 0 ? '已静音' : `音量: ${Math.round(playerStore.videoVolume * 100)}%`)
  } else if (e.key === '+' || e.key === '=') {
    e.preventDefault()
    zoomIn()
  } else if (e.key === '-' || e.key === '_') {
    e.preventDefault()
    zoomOut()
  } else if (e.key === '0') {
    e.preventDefault()
    resetZoom()
  }
}

const onVideoEnded = () => {
  // Continuous playback: when video finishes, roll to next item!
  playerStore.nextFg()
}

const syncFgVideoVolume = () => {
  if (isVideo.value && fgVideoRef.value) {
    fgVideoRef.value.volume = playerStore.videoVolume
    fgVideoRef.value.muted = (playerStore.videoVolume === 0)
  }
}

watch(() => playerStore.videoVolume, (vol) => {
  if (isVideo.value && fgVideoRef.value) {
    fgVideoRef.value.volume = vol
    fgVideoRef.value.muted = (vol === 0)
  }
})

watch(currentUnit, () => {
  zoomLevel.value = 1
  if (isVideo.value && fgVideoRef.value) {
    fgVideoRef.value.currentTime = 0
    syncFgVideoVolume()
    fgVideoRef.value.play().catch(() => {})
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('mousemove', onMouseMove)
  syncFgVideoVolume()
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('mousemove', onMouseMove)
  if (idleTimer) clearTimeout(idleTimer)
})

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

const selectInterval = (secs) => {
  playerStore.setFgInterval(secs)
  showIntervalMenu.value = false
}

const promptSaveFgSuperset = async () => {
  const name = window.prompt('请输入超集名称：', `${currentUnit.value?.title || '精选'} 连播集`)
  if (name && name.trim()) {
    try {
      await playerStore.saveFgQueueAsSuperset(name.trim())
      await mediaStore.loadSupersets()
    } catch (e) {
      console.error(e)
    }
  }
}
</script>

<template>
  <div
    v-if="playerStore.fgViewerOpen && currentUnit"
    class="fixed inset-0 z-50 bg-black/95 flex items-center justify-center backdrop-blur-xl animate-fade-in select-none overflow-hidden"
  >
    <!-- Ambient Backlight Ethereal Glow -->
    <div
      class="absolute inset-0 pointer-events-none opacity-25 blur-3xl scale-125 transition-all duration-700 bg-center bg-cover"
      :style="{ backgroundImage: `url(${mediaUrl})` }"
    />

    <!-- Top Bar Controls (Auto-hides on mouse idle) -->
    <div
      class="absolute top-5 inset-x-5 flex items-center justify-between z-30 transition-opacity duration-500"
      :class="{ 'opacity-0 pointer-events-none': isIdle }"
    >
      <!-- Title & Technical Resolution -->
      <div class="flex items-center gap-3">
        <h3 class="text-sm font-medium text-white/90 truncate max-w-xs sm:max-w-md">
          {{ currentUnit.title }}
        </h3>
        <span v-if="currentUnit.width && currentUnit.height" class="text-xs text-gray-400 font-mono hidden sm:inline">
          {{ currentUnit.width }}x{{ currentUnit.height }}
        </span>
        <span
          v-if="isVideo"
          class="flex items-center gap-1 bg-blue-600/80 text-[10px] text-white px-2 py-0.5 rounded-full"
        >
          <Video class="w-3 h-3" />
          <span>连播视频</span>
        </span>
      </div>

      <!-- Slideshow Autoplay Control Dock (Center) -->
      <div class="flex items-center gap-2 bg-neutral-900/80 backdrop-blur-md px-3 py-1.5 rounded-2xl border border-white/10 shadow-lg">
        <!-- Play / Pause Slideshow -->
        <button
          @click="playerStore.toggleFgAutoPlay()"
          :class="[
            'flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-semibold transition-all',
            playerStore.fgAutoPlay
              ? 'bg-purple-600 text-white shadow'
              : 'text-gray-300 hover:text-white hover:bg-white/10'
          ]"
          :title="playerStore.fgAutoPlay ? '暂停自动连播 (空格)' : '开启自动幻灯连播 (空格)'"
        >
          <Pause v-if="playerStore.fgAutoPlay" class="w-3.5 h-3.5 fill-current" />
          <Play v-else class="w-3.5 h-3.5 ml-0.5 fill-current" />
          <span>{{ playerStore.fgAutoPlay ? '连播中' : '连播' }}</span>
        </button>

        <!-- Dynamic Timer Badge & Countdown Ring (For Images) -->
        <div v-if="!isVideo" class="relative">
          <button
            @click="showIntervalMenu = !showIntervalMenu"
            class="flex items-center gap-1.5 px-2 py-1 rounded-xl text-xs text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
            title="设置每张停留秒数"
          >
            <Clock class="w-3.5 h-3.5 text-purple-400" />
            <span class="font-mono text-purple-300 font-semibold">{{ playerStore.fgTimeRemaining }}s</span>
            <span class="text-[10px] text-gray-500">/ {{ playerStore.fgIntervalSeconds }}s</span>
          </button>

          <!-- Interval Menu Popup -->
          <div
            v-if="showIntervalMenu"
            class="absolute top-full mt-2 left-1/2 -translate-x-1/2 bg-neutral-900 border border-white/15 p-1.5 rounded-xl shadow-2xl backdrop-blur-xl space-y-1 w-28 text-center text-xs z-50"
          >
            <div class="text-[10px] text-gray-500 pb-1 border-b border-white/10">切换停留时长</div>
            <button
              v-for="s in [5, 10, 15, 30, 60]"
              :key="s"
              @click="selectInterval(s)"
              :class="[
                'w-full py-1 rounded-lg transition-colors font-mono',
                playerStore.fgIntervalSeconds === s ? 'bg-purple-600 text-white font-bold' : 'text-gray-300 hover:bg-white/10'
              ]"
            >
              {{ s }} 秒 {{ s === 15 ? '(默认)' : '' }}
            </button>
          </div>
        </div>

        <!-- Video notice when video is playing in slideshow -->
        <span v-else class="text-[11px] text-emerald-400 font-medium px-1 flex items-center gap-1">
          播完自动下移
        </span>

        <!-- Loop mode toggle -->
        <button
          @click="playerStore.toggleFgPlayMode()"
          class="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          :title="`循环模式 (当前: ${playerStore.fgPlayMode})`"
        >
          <Shuffle v-if="playerStore.fgPlayMode === 'shuffle'" class="w-3.5 h-3.5 text-purple-400" />
          <Repeat1 v-else-if="playerStore.fgPlayMode === 'repeat'" class="w-3.5 h-3.5 text-purple-400" />
          <Repeat v-else class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Background Companion Audio HUD Capsule -->
      <div
        v-if="playerStore.activeBgUnit"
        class="hidden lg:flex items-center gap-2 bg-neutral-900/90 backdrop-blur-xl px-3 py-1.5 rounded-2xl border border-purple-500/30 text-xs shadow-xl select-none"
      >
        <Disc3
          class="w-4 h-4 text-purple-400 shrink-0"
          :class="{ 'animate-spin': playerStore.isBgPlaying }"
          style="animation-duration: 5s;"
        />
        <span class="truncate max-w-[110px] text-[11px] font-medium text-purple-200" :title="playerStore.activeBgUnit.title">
          {{ playerStore.activeBgUnit.title }}
        </span>

        <!-- HUD Transport -->
        <div class="flex items-center gap-0.5">
          <button
            @click="playerStore.prevAudio()"
            class="p-1 text-gray-300 hover:text-white rounded transition-colors"
            title="上一首伴奏"
          >
            <SkipBack class="w-3 h-3" />
          </button>
          <button
            @click="playerStore.togglePlayAudio()"
            class="p-1 text-white rounded bg-purple-600 hover:bg-purple-500 transition-colors"
            :title="playerStore.isBgPlaying ? '暂停伴奏' : '播放伴奏'"
          >
            <Pause v-if="playerStore.isBgPlaying" class="w-3 h-3 fill-current" />
            <Play v-else class="w-3 h-3 fill-current" />
          </button>
          <button
            @click="playerStore.nextAudio()"
            class="p-1 text-gray-300 hover:text-white rounded transition-colors"
            title="下一首伴奏"
          >
            <SkipForward class="w-3 h-3" />
          </button>
        </div>

        <!-- HUD Volume Slider -->
        <div class="flex items-center gap-1 pl-1 border-l border-white/15">
          <button
            @click="isVideo ? playerStore.toggleVideoMute() : playerStore.toggleBgMute()"
            class="p-0.5 text-gray-400 hover:text-white transition-colors"
            :title="(isVideo ? playerStore.videoVolume : playerStore.bgVolume) === 0 ? '取消静音 (M)' : '静音 (M)'"
          >
            <VolumeX v-if="(isVideo ? playerStore.videoVolume : playerStore.bgVolume) === 0" class="w-3 h-3 text-rose-400" />
            <Volume2 v-else class="w-3 h-3 text-purple-300" />
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            :value="isVideo ? playerStore.videoVolume : playerStore.bgVolume"
            @input="isVideo ? playerStore.setVideoVolume($event.target.value) : playerStore.setBgVolume($event.target.value)"
            class="w-12 md:w-16 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-400"
            :title="isVideo ? `视频音量: ${Math.round(playerStore.videoVolume * 100)}% (↑/↓)` : `伴奏音量: ${Math.round(playerStore.bgVolume * 100)}%`"
          />
        </div>
      </div>

      <!-- Right Actions (Zoom, External, Close) -->
      <div class="flex items-center gap-2">
        <!-- Zoom Controls (Only for image) -->
        <div v-if="!isVideo" class="flex items-center gap-1 bg-white/10 backdrop-blur-md rounded-xl p-1 border border-white/10">
          <button @click="zoomOut" class="p-1.5 text-gray-300 hover:text-white rounded-lg hover:bg-white/10" title="缩小 (-)">
            <ZoomOut class="w-4 h-4" />
          </button>
          <button @click="resetZoom" class="p-1.5 text-gray-300 hover:text-white rounded-lg hover:bg-white/10" title="复位 (0)">
            <RotateCcw class="w-4 h-4" />
          </button>
          <button @click="zoomIn" class="p-1.5 text-gray-300 hover:text-white rounded-lg hover:bg-white/10" title="放大 (+)">
            <ZoomIn class="w-4 h-4" />
          </button>
        </div>

        <!-- Open External -->
        <button
          @click="revealInExplorer({ unit_id: currentUnit.id })"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-blue-400 transition-colors"
          title="在资源管理器中定位"
        >
          <FolderOpen class="w-4 h-4" />
        </button>
        <button
          @click="openWithDefaultApp({ unit_id: currentUnit.id })"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-purple-400 transition-colors"
          title="系统默认程序打开"
        >
          <ExternalLink class="w-4 h-4" />
        </button>

        <!-- Close -->
        <button
          @click="playerStore.closeImage()"
          class="p-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors"
          title="关闭 (Esc)"
        >
          <X class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- Navigation Arrows (Auto-hides on mouse idle) -->
    <button
      v-if="playerStore.fgQueue.length > 1"
      @click="playerStore.prevFg()"
      class="absolute left-4 top-1/2 -translate-y-1/2 z-30 p-3 rounded-full bg-black/50 hover:bg-black/80 text-white backdrop-blur-md transition-all border border-white/10 hover:scale-110 active:scale-95 duration-500"
      :class="{ 'opacity-0 pointer-events-none': isIdle }"
      title="上一张 (←)"
    >
      <ChevronLeft class="w-6 h-6" />
    </button>

    <button
      v-if="playerStore.fgQueue.length > 1"
      @click="playerStore.nextFg()"
      class="absolute right-4 top-1/2 -translate-y-1/2 z-30 p-3 rounded-full bg-black/50 hover:bg-black/80 text-white backdrop-blur-md transition-all border border-white/10 hover:scale-110 active:scale-95 duration-500"
      :class="{ 'opacity-0 pointer-events-none': isIdle }"
      title="下一张 (→)"
    >
      <ChevronRight class="w-6 h-6" />
    </button>

    <!-- Content Viewport (Image or Video) -->
    <div class="relative z-10 w-full h-full flex items-center justify-center p-8 overflow-hidden">
      <!-- Video Element in Continuous Queue -->
      <video
        v-if="isVideo"
        ref="fgVideoRef"
        :src="mediaUrl"
        autoplay
        controls
        playsinline
        class="max-w-full max-h-full object-contain rounded-2xl shadow-2xl"
        @loadedmetadata="syncFgVideoVolume"
        @play="syncFgVideoVolume"
        @ended="onVideoEnded"
      />

      <!-- Image Element with Zoom Scale -->
      <img
        v-else
        :src="mediaUrl"
        :alt="currentUnit.title"
        :style="{ transform: `scale(${zoomLevel})` }"
        class="max-w-full max-h-full object-contain transition-transform duration-300 rounded-lg shadow-2xl"
      />
    </div>

    <!-- Bottom Metadata Bar (Auto-hides on mouse idle) -->
    <div
      class="absolute bottom-5 inset-x-5 flex items-center justify-between z-30 transition-opacity duration-500"
      :class="{ 'opacity-0 pointer-events-none': isIdle }"
    >
      <div class="flex items-center gap-2 text-xs text-gray-300 bg-black/60 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-white/10 font-mono">
        <span>{{ playerStore.fgQueueIndex + 1 }}</span>
        <span class="text-gray-500">/</span>
        <span>{{ playerStore.fgQueue.length }}</span>
        <button
          @click="promptSaveFgSuperset"
          class="ml-2 pl-2 border-l border-white/20 text-pink-300 hover:text-white flex items-center gap-1 font-sans text-xs transition-colors"
          title="将当前连播队列另存为虚拟超集"
        >
          <Sparkles class="w-3 h-3 text-pink-400" />
          <span>存为超集</span>
        </button>
      </div>

      <!-- Rating & Favorite -->
      <div class="flex items-center gap-3 bg-black/60 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-white/10">
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
                s <= (currentUnit.rating || 0) ? 'text-amber-400 fill-amber-400' : 'text-gray-500'
              ]"
            />
          </button>
        </div>

        <span class="text-gray-600">|</span>

        <button
          @click="toggleFavorite"
          class="text-gray-400 hover:text-rose-500 transition-colors"
          :title="currentUnit.is_favorite ? '取消喜欢' : '标为喜欢'"
        >
          <Heart
            :class="[
              'w-4 h-4',
              currentUnit.is_favorite ? 'text-rose-500 fill-rose-500' : ''
            ]"
          />
        </button>
      </div>
    </div>
  </div>
</template>
