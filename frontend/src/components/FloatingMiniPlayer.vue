<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { usePlayerStore } from '../stores/playerStore'
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Maximize2,
  Minimize2,
  X,
  Volume2,
  VolumeX,
  Disc3,
  Music,
  Video,
  ListMusic,
  ChevronUp,
  ChevronDown,
  Trash2
} from 'lucide-vue-next'

const playerStore = usePlayerStore()

const currentUnit = computed(() => playerStore.activeBgUnit)
const isPlaying = computed(() => playerStore.isBgPlaying)
const viewMode = computed(() => playerStore.bgViewMode)

const showMiniQueue = ref(false)
const videoRef = ref(null)
const audioRef = ref(null)

// Position and dimensions for draggable mini-window
const posX = ref(window.innerWidth - 380)
const posY = ref(window.innerHeight - 260)
const width = ref(350)
const height = ref(210)

const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

const isResizing = ref(false)
const resizeStart = ref({ mouseX: 0, mouseY: 0, initW: 0, initH: 0 })

const currentTime = ref(0)
const duration = ref(0)

const primaryFile = computed(() => {
  if (!currentUnit.value?.files?.length) return null
  return (
    currentUnit.value.files.find(f => f.role === 'primary' || f.role === 'video' || f.role === 'audio') ||
    currentUnit.value.files[0]
  )
})

const subtitleFile = computed(() => {
  if (!currentUnit.value?.files?.length) return null
  return currentUnit.value.files.find(f => f.role === 'subtitle')
})

const mediaUrl = computed(() => {
  if (!primaryFile.value) return ''
  return `/api/stream/file/${primaryFile.value.id}`
})

const subtitleUrl = computed(() => {
  if (!subtitleFile.value) return ''
  return `/api/stream/subtitle/${subtitleFile.value.id}`
})

const isVideo = computed(() => {
  if (!currentUnit.value) return false
  return currentUnit.value.unit_type === 'video' || currentUnit.value.unit_type === 'bundle'
})

// Play / Pause synchronization
watch(isPlaying, (playing) => {
  const el = isVideo.value ? videoRef.value : audioRef.value
  if (!el) return
  if (playing) {
    el.play().catch(() => {})
  } else {
    el.pause()
  }
})

// Real-time volume synchronization
watch(() => playerStore.bgVolume, (vol) => {
  const el = isVideo.value ? videoRef.value : audioRef.value
  if (el) {
    el.volume = vol
  }
})

// Unit change
watch(currentUnit, () => {
  currentTime.value = 0
  const el = isVideo.value ? videoRef.value : audioRef.value
  if (el) {
    el.currentTime = 0
    if (playerStore.isBgPlaying) {
      el.play().catch(() => {})
    }
  }
})

// Drag logic
const startDrag = (e) => {
  if (e.target.closest('button') || e.target.closest('input')) return
  isDragging.value = true
  dragOffset.value = {
    x: e.clientX - posX.value,
    y: e.clientY - posY.value
  }
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

const onDrag = (e) => {
  if (!isDragging.value) return
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y

  // Clamp within viewport
  const maxX = window.innerWidth - width.value - 10
  const maxY = window.innerHeight - height.value - 10
  posX.value = Math.max(10, Math.min(maxX, newX))
  posY.value = Math.max(10, Math.min(maxY, newY))
}

const stopDrag = () => {
  isDragging.value = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

// Resize logic
const startResize = (e) => {
  isResizing.value = true
  resizeStart.value = {
    mouseX: e.clientX,
    mouseY: e.clientY,
    initW: width.value,
    initH: height.value
  }
  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', stopResize)
}

const onResize = (e) => {
  if (!isResizing.value) return
  const dx = e.clientX - resizeStart.value.mouseX
  const newW = Math.max(260, Math.min(640, resizeStart.value.initW + dx))
  width.value = newW
  height.value = Math.round(newW * 0.6) // maintain smooth proportion
}

const stopResize = () => {
  isResizing.value = false
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
}

const onTimeUpdate = (e) => {
  currentTime.value = e.target.currentTime
}

const onLoadedMetadata = (e) => {
  duration.value = e.target.duration
  e.target.volume = playerStore.bgVolume
}

const onEnded = () => {
  playerStore.nextAudio()
}

const onMediaError = (e) => {
  console.warn('Background media load error:', e)
  playerStore.showToast('存储网络连接超时或 NAS 休眠唤醒中，已保留播放进度')
}

const togglePlay = () => {
  playerStore.togglePlayAudio()
}

const expandToFull = () => {
  if (isVideo.value) {
    playerStore.openVideo(currentUnit.value, playerStore.bgQueue)
    playerStore.setBgViewMode('hidden')
  } else {
    playerStore.setBgViewMode('full')
  }
}

const minimizeToDisc = () => {
  playerStore.setBgViewMode('disc')
}

const formatTime = (secs) => {
  if (!secs || isNaN(secs)) return '00:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

onMounted(() => {
  // Center or default to bottom right
  posX.value = Math.max(20, window.innerWidth - 380)
  posY.value = Math.max(20, window.innerHeight - 250)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
})
</script>

<template>
  <div v-if="currentUnit && viewMode !== 'hidden'" class="select-none">
    <!-- Hidden HTML Media Elements for Real Streaming -->
    <video
      v-if="isVideo"
      ref="videoRef"
      :src="mediaUrl"
      class="hidden"
      crossorigin="anonymous"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoadedMetadata"
      @ended="onEnded"
      @error="onMediaError"
    >
      <track
        v-if="subtitleUrl"
        kind="subtitles"
        :src="subtitleUrl"
        default
      />
    </video>
    <audio
      v-else
      ref="audioRef"
      :src="mediaUrl"
      class="hidden"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoadedMetadata"
      @ended="onEnded"
      @error="onMediaError"
    />

    <!-- ============================================================ -->
    <!-- Mode 1: Spinning Vinyl Disc Floating Widget ('disc')         -->
    <!-- ============================================================ -->
    <div
      v-if="viewMode === 'disc'"
      @click="playerStore.setBgViewMode('mini')"
      class="fixed bottom-6 right-6 z-40 group cursor-pointer"
      title="点击展开媒体悬浮小窗"
    >
      <!-- Pulsating Audio Glow Aura -->
      <div
        v-if="isPlaying"
        class="absolute -inset-1.5 rounded-full bg-gradient-to-r from-purple-600 to-pink-600 opacity-60 blur-md animate-pulse"
      />

      <!-- Vinyl Disc Body -->
      <div
        class="relative w-14 h-14 rounded-full bg-neutral-950 border-2 border-white/20 shadow-2xl flex items-center justify-center overflow-hidden transition-transform duration-300 group-hover:scale-110 active:scale-95"
      >
        <!-- Concentric Vinyl Grooves -->
        <div class="absolute inset-1 rounded-full border border-neutral-700/50" />
        <div class="absolute inset-2.5 rounded-full border border-neutral-800" />

        <!-- Rotating Album Artwork Center -->
        <div
          class="w-8 h-8 rounded-full overflow-hidden border border-white/30 flex items-center justify-center bg-purple-900"
          :class="{ 'animate-spin': isPlaying }"
          style="animation-duration: 4s;"
        >
          <img
            :src="`/api/stream/thumbnail/${currentUnit.id}`"
            class="w-full h-full object-cover"
            @error="(e) => e.target.style.display = 'none'"
          />
          <component
            :is="isVideo ? Video : Music"
            class="w-4 h-4 text-white/80"
          />
        </div>

        <!-- Center spindle hole -->
        <div class="absolute w-2 h-2 rounded-full bg-white/90 shadow-inner z-10" />

        <!-- Hover Play/Pause Overlay -->
        <div
          @click.stop="togglePlay"
          class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-full text-white"
        >
          <Pause v-if="isPlaying" class="w-5 h-5 fill-current" />
          <Play v-else class="w-5 h-5 ml-0.5 fill-current" />
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- Mode 2: Draggable & Resizable Floating Mini Player ('mini')   -->
    <!-- ============================================================ -->
    <div
      v-else-if="viewMode === 'mini'"
      class="fixed z-40 rounded-2xl shadow-2xl backdrop-blur-2xl border flex flex-col overflow-hidden transition-shadow"
      :style="{
        left: `${posX}px`,
        top: `${posY}px`,
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border-color)',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
      }"
    >
      <!-- Draggable Window Titlebar -->
      <div
        @mousedown="startDrag"
        class="h-8 px-3 bg-white/5 border-b border-white/10 flex items-center justify-between cursor-move select-none"
      >
        <div class="flex items-center gap-1.5 truncate max-w-[180px]">
          <span
            class="w-2 h-2 rounded-full"
            :class="isPlaying ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'"
          />
          <span class="text-[11px] font-medium text-white truncate" :title="currentUnit.title">
            {{ currentUnit.title }}
          </span>
        </div>

        <!-- Control Action Icons -->
        <div class="flex items-center gap-1">
          <!-- Queue Drawer Toggle -->
          <button
            @click.stop="showMiniQueue = !showMiniQueue"
            class="p-1 rounded transition-colors relative"
            :class="showMiniQueue ? 'text-purple-300 bg-purple-500/20' : 'text-gray-400 hover:text-white hover:bg-white/10'"
            title="查看与编辑播放队列"
          >
            <ListMusic class="w-3.5 h-3.5" />
            <span
              v-if="playerStore.bgQueue.length > 0"
              class="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-purple-400"
            />
          </button>

          <!-- Minimize to Disc Widget -->
          <button
            @click.stop="minimizeToDisc"
            class="p-1 text-gray-400 hover:text-white rounded hover:bg-white/10 transition-colors"
            title="最小化为唱片挂件"
          >
            <Disc3 class="w-3.5 h-3.5 text-purple-400" />
          </button>

          <!-- Maximize to Full View -->
          <button
            @click.stop="expandToFull"
            class="p-1 text-gray-400 hover:text-white rounded hover:bg-white/10 transition-colors"
            title="最大化展开"
          >
            <Maximize2 class="w-3.5 h-3.5" />
          </button>

          <!-- Close Window -->
          <button
            @click.stop="playerStore.closeBgPlayer()"
            class="p-1 text-gray-400 hover:text-rose-400 rounded hover:bg-white/10 transition-colors"
            title="关闭背景播放"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Main Visual Viewport (Video canvas or Vinyl animation or Mini Queue) -->
      <div class="relative flex-grow bg-black flex items-center justify-center overflow-hidden group/canvas">
        <!-- Embedded Mini Queue Overlay -->
        <div
          v-if="showMiniQueue"
          class="absolute inset-0 z-30 p-2.5 flex flex-col backdrop-blur-xl select-none"
          style="background-color: rgba(15, 17, 26, 0.95);"
        >
          <div class="flex items-center justify-between pb-1.5 border-b border-white/10 text-[11px]">
            <div class="flex items-center gap-1.5">
              <ListMusic class="w-3 h-3 text-purple-400" />
              <span class="font-medium text-white">队列 ({{ playerStore.bgQueue.length }})</span>
            </div>
            <div class="flex items-center gap-1.5">
              <button
                @click.stop="playerStore.openQueueDrawer()"
                class="text-[10px] text-purple-300 hover:text-purple-200 px-1.5 py-0.5 rounded bg-purple-500/20 hover:bg-purple-500/30 transition-colors"
                title="打开完整播放队列面板 (拖拽排序/另存超集)"
              >
                面板管理
              </button>
              <button
                @click.stop="playerStore.clearBgQueue()"
                class="text-[10px] text-rose-400 hover:text-rose-300 px-1.5 py-0.5 rounded bg-rose-500/10 hover:bg-rose-500/20 transition-colors"
                title="清空当前队列并退出播放"
              >
                清空
              </button>
              <button
                @click.stop="showMiniQueue = false"
                class="p-1 text-gray-400 hover:text-white rounded hover:bg-white/10"
              >
                <X class="w-3 h-3" />
              </button>
            </div>
          </div>

          <!-- Mini Queue Item List -->
          <div class="flex-grow overflow-y-auto py-1 space-y-1 pr-0.5">
            <div
              v-if="playerStore.bgQueue.length === 0"
              class="h-full flex items-center justify-center text-[11px] text-gray-500"
            >
              队列为空
            </div>
            <div
              v-else
              v-for="(unit, idx) in playerStore.bgQueue"
              :key="unit.id"
              @click.stop="playerStore.playAudio(unit, playerStore.bgQueue, 'mini')"
              :class="[
                'group/item px-2 py-1 rounded-lg text-xs flex items-center justify-between gap-1.5 cursor-pointer transition-colors',
                playerStore.activeBgUnit?.id === unit.id
                  ? 'bg-purple-600/30 text-purple-200 border border-purple-500/30'
                  : 'text-gray-300 hover:bg-white/5 border border-transparent'
              ]"
            >
              <div class="flex items-center gap-1.5 truncate">
                <span class="text-[10px] text-gray-500 font-mono w-3 shrink-0">{{ idx + 1 }}</span>
                <span class="truncate text-[11px]" :title="unit.title">{{ unit.title }}</span>
              </div>
              <div class="flex items-center gap-0.5 shrink-0 opacity-0 group-hover/item:opacity-100 transition-opacity">
                <button
                  @click.stop="playerStore.moveBgQueueItem(idx, idx - 1)"
                  :disabled="idx === 0"
                  class="p-0.5 text-gray-400 hover:text-white rounded disabled:opacity-20"
                  title="上移"
                >
                  <ChevronUp class="w-3 h-3" />
                </button>
                <button
                  @click.stop="playerStore.moveBgQueueItem(idx, idx + 1)"
                  :disabled="idx === playerStore.bgQueue.length - 1"
                  class="p-0.5 text-gray-400 hover:text-white rounded disabled:opacity-20"
                  title="下移"
                >
                  <ChevronDown class="w-3 h-3" />
                </button>
                <button
                  @click.stop="playerStore.removeFromBgQueue(idx)"
                  class="p-0.5 text-gray-400 hover:text-rose-400 rounded"
                  title="从队列中移除"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- If Video: Synchronized Video Render -->
        <video
          v-if="isVideo"
          :src="mediaUrl"
          autoplay
          muted
          loop
          class="w-full h-full object-cover pointer-events-none"
        />

        <!-- If Audio: Spinning Vinyl Record Canvas -->
        <div
          v-else
          class="relative w-full h-full flex items-center justify-center bg-gradient-to-br from-purple-950/40 via-neutral-900 to-indigo-950/50"
        >
          <div
            class="w-24 h-24 rounded-full bg-neutral-950 border border-neutral-700 shadow-xl flex items-center justify-center overflow-hidden transition-transform"
            :class="{ 'animate-spin': isPlaying }"
            style="animation-duration: 5s;"
          >
            <!-- Vinyl label artwork -->
            <img
              :src="`/api/stream/thumbnail/${currentUnit.id}`"
              class="w-14 h-14 rounded-full object-cover border border-white/20"
              @error="(e) => e.target.style.display = 'none'"
            />
            <div class="absolute w-2.5 h-2.5 rounded-full bg-white shadow-inner" />
          </div>

          <!-- Soundwave Bar Animation on Hover -->
          <div class="absolute bottom-2 inset-x-3 flex items-center justify-center gap-1 opacity-70">
            <span
              v-for="i in 8"
              :key="i"
              class="w-1 bg-purple-400 rounded-full transition-all"
              :style="{
                height: isPlaying ? `${Math.sin(i * 1.2 + currentTime) * 8 + 12}px` : '4px',
                opacity: isPlaying ? 0.9 : 0.3
              }"
            />
          </div>
        </div>

        <!-- Hover overlay with Play / Next / Prev -->
        <div class="absolute inset-0 bg-black/40 opacity-0 group-hover/canvas:opacity-100 transition-opacity flex items-center justify-center gap-3">
          <button
            @click.stop="playerStore.prevAudio()"
            class="p-2 text-gray-200 hover:text-white rounded-full bg-black/50 hover:bg-black/80 transition-transform active:scale-95"
            title="上一首"
          >
            <SkipBack class="w-4 h-4" />
          </button>
          <button
            @click.stop="togglePlay"
            class="p-3 text-white rounded-full shadow-lg transition-transform active:scale-95"
            style="background-color: var(--accent-color);"
            :title="isPlaying ? '暂停' : '播放'"
          >
            <Pause v-if="isPlaying" class="w-4 h-4 fill-current" />
            <Play v-else class="w-4 h-4 ml-0.5 fill-current" />
          </button>
          <button
            @click.stop="playerStore.nextAudio()"
            class="p-2 text-gray-200 hover:text-white rounded-full bg-black/50 hover:bg-black/80 transition-transform active:scale-95"
            title="下一首"
          >
            <SkipForward class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Bottom Mini Scrubber & Volume Control -->
      <div class="h-7 px-2.5 bg-black/75 flex items-center justify-between gap-2 border-t border-white/10 text-[10px] text-gray-400 font-mono select-none">
        <span class="w-8 shrink-0 text-left">{{ formatTime(currentTime) }}</span>
        <!-- Progress Bar -->
        <div class="relative flex-grow h-1 bg-white/20 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all"
            style="background-color: var(--accent-color);"
            :style="{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }"
          />
        </div>
        <span class="w-8 shrink-0 text-right">{{ formatTime(duration) }}</span>

        <!-- Volume slider & Mute button -->
        <div class="flex items-center gap-1 pl-1.5 border-l border-white/15 shrink-0 group/vol">
          <button
            @click.stop="playerStore.toggleBgMute()"
            class="p-0.5 text-gray-400 hover:text-white transition-colors"
            :title="playerStore.bgVolume === 0 ? '取消静音' : '静音'"
          >
            <VolumeX v-if="playerStore.bgVolume === 0" class="w-3 h-3 text-rose-400" />
            <Volume2 v-else class="w-3 h-3 text-gray-300" />
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            :value="playerStore.bgVolume"
            @input.stop="playerStore.setBgVolume($event.target.value)"
            class="w-12 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-400"
            title="音量调节"
          />
        </div>
      </div>

      <!-- Resizable Corner Grip Handle -->
      <div
        @mousedown.stop="startResize"
        class="absolute bottom-0 right-0 w-3.5 h-3.5 cursor-nwse-resize flex items-end justify-end p-0.5 z-20 group"
        title="按住拖拽缩放小窗"
      >
        <div class="w-2 h-2 border-r-2 border-b-2 border-white/40 group-hover:border-white transition-colors" />
      </div>
    </div>
  </div>
</template>
