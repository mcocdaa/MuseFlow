<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { usePlayerStore } from '../stores/playerStore'
import { useMediaStore } from '../stores/mediaStore'
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Repeat,
  Repeat1,
  Shuffle,
  Volume2,
  VolumeX,
  Minimize2,
  Disc3,
  X,
  Music,
  ListMusic,
  Trash2,
  ChevronUp,
  ChevronDown,
  Sparkles,
  Subtitles,
  Layers,
  Clock,
  Plus
} from 'lucide-vue-next'

const playerStore = usePlayerStore()
const mediaStore = useMediaStore()

const audioRef = ref(null)
const currentTime = ref(0)
const duration = ref(0)
const activeCueText = ref('')

const isFg = computed(() => playerStore.fgAudioModalOpen && !!playerStore.activeFgAudioUnit)
const isOpen = computed(() => isFg.value || (playerStore.bgViewMode === 'full' && !!playerStore.activeBgUnit))

const currentUnit = computed(() => {
  return isFg.value ? playerStore.activeFgAudioUnit : playerStore.activeBgUnit
})

const playlist = computed(() => {
  return isFg.value ? playerStore.fgAudioPlaylist : playerStore.bgQueue
})

const playlistIndex = computed(() => {
  return isFg.value ? playerStore.fgAudioPlaylistIndex : playerStore.bgQueueIndex
})

const isPlaying = computed(() => {
  return isFg.value ? playerStore.isFgAudioPlaying : playerStore.isBgPlaying
})

const primaryFile = computed(() => {
  if (!currentUnit.value?.files?.length) return null
  return (
    currentUnit.value.files.find(f => f.role === 'primary' || f.role === 'audio') ||
    currentUnit.value.files[0]
  )
})

const subtitleFile = computed(() => {
  if (!currentUnit.value?.files?.length) return null
  return currentUnit.value.files.find(f => f.role === 'subtitle' || f.role === 'lyrics')
})

const audioStreamUrl = computed(() => {
  if (!primaryFile.value) return ''
  return `/api/stream/file/${primaryFile.value.id}`
})

const subtitleStreamUrl = computed(() => {
  if (!subtitleFile.value) return ''
  return `/api/stream/subtitle/${subtitleFile.value.id}`
})

const setupSubtitleTracking = () => {
  if (!audioRef.value) return
  const trackEl = audioRef.value.querySelector('track')
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

// Media event handlers
const onTimeUpdate = () => {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
  }
}

const onLoadedMetadata = () => {
  if (audioRef.value) {
    duration.value = audioRef.value.duration || currentUnit.value?.duration_seconds || 0
    audioRef.value.volume = isFg.value ? playerStore.fgAudioVolume : playerStore.bgVolume
    setTimeout(setupSubtitleTracking, 300)
    if (isPlaying.value) {
      audioRef.value.play().catch(() => {})
    }
  }
}

const onEnded = () => {
  if (isFg.value) {
    playerStore.nextFgAudio()
  } else {
    playerStore.nextAudio()
  }
}

const onAudioError = (e) => {
  console.warn('Foreground audio load error:', e)
  playerStore.showToast('音频读取超时或 NAS 存储设备离线，请检查网络连接')
}

const seek = (e) => {
  const time = parseFloat(e.target.value)
  currentTime.value = time
  if (audioRef.value) {
    audioRef.value.currentTime = time
  }
}

const togglePlay = () => {
  if (isFg.value) {
    playerStore.togglePlayFgAudio()
    if (audioRef.value) {
      if (playerStore.isFgAudioPlaying) {
        audioRef.value.play().catch(() => {})
      } else {
        audioRef.value.pause()
      }
    }
  } else {
    playerStore.togglePlayAudio()
  }
}

// Watchers
watch(isPlaying, (newVal) => {
  if (!audioRef.value || !isFg.value) return
  if (newVal) {
    audioRef.value.play().catch(() => {})
  } else {
    audioRef.value.pause()
  }
})

watch(currentUnit, () => {
  activeCueText.value = ''
  currentTime.value = 0
  if (audioRef.value) {
    audioRef.value.currentTime = 0
    if (isPlaying.value) {
      audioRef.value.play().catch(() => {})
    }
    setTimeout(setupSubtitleTracking, 300)
  }
})

watch(() => playerStore.fgAudioVolume, (newVol) => {
  if (audioRef.value && isFg.value) {
    audioRef.value.volume = newVol
  }
})

const handleKeyDown = (e) => {
  if (!isOpen.value) return
  if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return
  if (e.key === 'Escape') {
    close()
  } else if (e.key === ' ' || e.code === 'Space') {
    e.preventDefault()
    togglePlay()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    if (isFg.value) playerStore.nextFgAudio()
    else playerStore.nextAudio()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    if (isFg.value) playerStore.prevFgAudio()
    else playerStore.prevAudio()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

const formatTime = (seconds) => {
  if (!seconds || isNaN(seconds)) return '00:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const close = () => {
  if (isFg.value) {
    if (audioRef.value) audioRef.value.pause()
    playerStore.closeAudioModal()
  } else {
    playerStore.setBgViewMode('disc')
  }
}

const transferToBg = () => {
  if (audioRef.value) audioRef.value.pause()
  playerStore.transferFgAudioToBg()
}

const selectTrack = (idx) => {
  if (isFg.value) {
    playerStore.selectFgAudioIndex(idx, true)
  } else {
    playerStore.bgQueueIndex = idx
    playerStore.activeBgUnit = playerStore.bgQueue[idx]
    playerStore.isBgPlaying = true
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="isOpen && currentUnit"
      class="fixed inset-0 z-50 flex flex-col justify-between p-6 lg:p-10 select-none overflow-hidden backdrop-blur-3xl"
      style="background-color: rgba(10, 12, 18, 0.95);"
    >
      <!-- Dedicated HTML5 Audio Element for Foreground Playback -->
      <audio
        v-if="isFg"
        ref="audioRef"
        :src="audioStreamUrl"
        class="hidden"
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onLoadedMetadata"
        @ended="onEnded"
        @error="onAudioError"
      >
        <track
          v-if="subtitleStreamUrl"
          kind="subtitles"
          :src="subtitleStreamUrl"
          default
        />
      </audio>

      <!-- Background Ambient Aurora -->
      <div
        class="absolute -top-40 -left-40 w-96 h-96 rounded-full opacity-20 blur-3xl pointer-events-none"
        style="background-color: var(--accent-color);"
      />
      <div
        class="absolute -bottom-40 -right-40 w-96 h-96 rounded-full opacity-20 blur-3xl pointer-events-none bg-pink-600"
      />

      <!-- Top Bar -->
      <header class="relative z-10 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-2xl flex items-center justify-center text-white shadow-lg"
            style="background-color: var(--accent-color);"
          >
            <Disc3 :class="['w-5 h-5', isPlaying ? 'animate-spin' : '']" style="animation-duration: 6s;" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="text-[10px] uppercase font-semibold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20">
                {{ isFg ? '系列内播放' : '背景伴奏流' }}
              </span>
              <span v-if="playlist.length > 1" class="text-xs text-gray-400 font-mono">
                第 {{ playlistIndex + 1 }} / {{ playlist.length }} 轨
              </span>
            </div>
            <h2 class="text-base font-semibold text-white tracking-wide truncate max-w-sm sm:max-w-md mt-0.5">
              {{ currentUnit.title }}
            </h2>
            <p class="text-xs text-gray-400">
              {{ currentUnit.collection_name || 'MuseFlow 音频沉浸' }}
            </p>
          </div>
        </div>

        <!-- Window Actions -->
        <div class="flex items-center gap-2">
          <!-- Move to Background Queue (only in Foreground mode) -->
          <button
            v-if="isFg"
            @click="transferToBg"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs text-purple-300 hover:text-white rounded-xl bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 transition-all"
            title="移入后台继续播放，释放主屏"
          >
            <Minimize2 class="w-3.5 h-3.5" />
            <span class="hidden sm:inline">移入背景播放</span>
          </button>

          <!-- Close -->
          <button
            @click="close"
            class="p-2 text-gray-400 hover:text-white rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all"
            title="关闭 (Esc)"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </header>

      <!-- Center Stage: Giant Vinyl Record & Lyrics -->
      <div class="relative z-10 flex-grow flex flex-col items-center justify-center py-4">
        <div class="relative flex items-center justify-center">
          <!-- Ambient Glow Ring -->
          <div
            class="absolute w-80 h-80 sm:w-96 sm:h-96 rounded-full blur-2xl opacity-40 transition-all duration-700"
            :class="isPlaying ? 'scale-110 opacity-60' : 'scale-95 opacity-20'"
            style="background: radial-gradient(circle, var(--accent-color), transparent 70%);"
          />

          <!-- Giant Vinyl Record Body -->
          <div
            class="relative w-64 h-64 sm:w-80 sm:h-80 rounded-full bg-neutral-950 border-4 border-neutral-800 shadow-2xl flex items-center justify-center overflow-hidden transition-transform duration-500"
            :class="{ 'animate-spin': isPlaying }"
            style="animation-duration: 10s;"
          >
            <!-- Grooves -->
            <div class="absolute inset-3 rounded-full border border-neutral-700/40" />
            <div class="absolute inset-6 rounded-full border border-neutral-700/30" />
            <div class="absolute inset-10 rounded-full border border-neutral-700/40" />
            <div class="absolute inset-14 rounded-full border border-neutral-700/30" />
            <div class="absolute inset-20 rounded-full border border-neutral-800" />

            <!-- Center Artwork Label -->
            <div class="w-24 h-24 sm:w-32 sm:h-32 rounded-full overflow-hidden border-2 border-white/40 shadow-inner flex items-center justify-center bg-purple-950">
              <img
                :src="`/api/stream/thumbnail/${currentUnit.id}`"
                :alt="currentUnit.title"
                class="w-full h-full object-cover"
                @error="(e) => e.target.style.display = 'none'"
              />
              <Music class="w-8 h-8 text-white/60" />
            </div>

            <!-- Center hole -->
            <div class="absolute w-4 h-4 rounded-full bg-white shadow-inner z-20 border border-neutral-400" />
          </div>

          <!-- Stylized Turntable Tone Arm -->
          <div
            class="absolute -top-10 right-4 sm:right-12 w-20 h-44 pointer-events-none transition-transform duration-700 origin-top-right z-30"
            :style="{ transform: isPlaying ? 'rotate(24deg)' : 'rotate(0deg)' }"
          >
            <div class="absolute top-0 right-0 w-8 h-8 rounded-full bg-neutral-700 border-2 border-neutral-500 shadow-lg" />
            <div class="absolute top-4 right-3.5 w-1.5 h-36 bg-neutral-400 rounded-full shadow" />
            <div class="absolute bottom-0 right-1 w-4 h-6 bg-neutral-200 rounded shadow border border-neutral-400" />
          </div>
        </div>

        <!-- Synchronized Lyric / Cue Text Display -->
        <div class="mt-6 h-12 flex items-center justify-center px-4 text-center">
          <Transition
            enter-active-class="transition duration-200 ease-out"
            enter-from-class="opacity-0 translate-y-2"
            enter-to-class="opacity-100 translate-y-0"
            leave-active-class="transition duration-150 ease-in"
            leave-from-class="opacity-100 translate-y-0"
            leave-to-class="opacity-0 -translate-y-2"
          >
            <div
              v-if="activeCueText"
              :key="activeCueText"
              class="px-5 py-2 rounded-2xl bg-black/60 backdrop-blur-md border border-white/10 text-white font-medium text-sm sm:text-base max-w-xl text-center shadow-xl [text-shadow:_0_1px_4px_rgba(0,0,0,0.8)]"
            >
              {{ activeCueText }}
            </div>
            <div v-else class="text-xs text-gray-500 font-mono">
              {{ subtitleFile ? '已挂载字幕 · 等待歌词对齐' : (isPlaying ? '高保真音频心流沉浸中' : '默认暂停 · 点击下方播放按钮开始') }}
            </div>
          </Transition>
        </div>
      </div>

      <!-- Bottom Player Control Deck -->
      <footer class="relative z-10 max-w-3xl mx-auto w-full flex flex-col items-center gap-3 bg-white/5 border border-white/10 p-4 sm:p-5 rounded-3xl backdrop-blur-md shadow-2xl">
        <!-- Progress Bar & Time Scrubber -->
        <div class="w-full flex items-center gap-3 text-xs text-gray-400 font-mono">
          <span>{{ formatTime(currentTime) }}</span>
          <input
            type="range"
            min="0"
            :max="duration || 100"
            step="0.5"
            :value="currentTime"
            @input="seek"
            class="flex-grow h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-400"
          />
          <span>{{ formatTime(duration) }}</span>
        </div>

        <!-- Main Controls -->
        <div class="flex items-center justify-between w-full mt-1">
          <!-- Left: Repeat / Playlist Info -->
          <div class="flex items-center gap-2">
            <span class="text-xs text-gray-400 flex items-center gap-1 font-mono">
              <Clock class="w-3.5 h-3.5 text-gray-500" />
              <span>{{ formatTime(duration) }}</span>
            </span>
          </div>

          <!-- Center Transport: Prev, Big Play/Pause, Next -->
          <div class="flex items-center gap-4">
            <button
              @click="isFg ? playerStore.prevFgAudio() : playerStore.prevAudio()"
              :disabled="playlist.length <= 1"
              class="p-2.5 text-gray-300 hover:text-white rounded-full hover:bg-white/10 transition-transform active:scale-90 disabled:opacity-30"
              title="上一轨"
            >
              <SkipBack class="w-5 h-5 fill-current" />
            </button>

            <button
              @click="togglePlay"
              class="w-14 h-14 rounded-full text-white flex items-center justify-center shadow-xl transform hover:scale-105 active:scale-95 transition-all"
              style="background-color: var(--accent-color);"
              :title="isPlaying ? '暂停 (空格)' : '播放 (空格)'"
            >
              <Pause v-if="isPlaying" class="w-6 h-6 fill-current" />
              <Play v-else class="w-6 h-6 ml-1 fill-current" />
            </button>

            <button
              @click="isFg ? playerStore.nextFgAudio() : playerStore.nextAudio()"
              :disabled="playlist.length <= 1"
              class="p-2.5 text-gray-300 hover:text-white rounded-full hover:bg-white/10 transition-transform active:scale-90 disabled:opacity-30"
              title="下一轨"
            >
              <SkipForward class="w-5 h-5 fill-current" />
            </button>
          </div>

          <!-- Right Actions: Volume & Series Playlist Drawer Toggle -->
          <div class="flex items-center gap-3">
            <!-- Volume slider -->
            <div class="flex items-center gap-1.5">
              <button
                @click="playerStore.toggleFgAudioMute()"
                class="p-2 text-gray-400 hover:text-white rounded-xl hover:bg-white/10 transition-colors"
                title="静音切换"
              >
                <VolumeX v-if="playerStore.fgAudioVolume === 0" class="w-4 h-4 text-rose-400" />
                <Volume2 v-else class="w-4 h-4 text-gray-300" />
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.02"
                :value="playerStore.fgAudioVolume"
                @input="playerStore.setFgAudioVolume($event.target.value)"
                class="w-16 sm:w-20 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-400"
                title="音量"
              />
            </div>

            <!-- Series Playlist Drawer Toggle -->
            <button
              @click="playerStore.toggleFgAudioDrawer()"
              class="flex items-center gap-1.5 px-3 py-2 text-xs rounded-xl transition-all"
              :class="playerStore.fgAudioDrawerOpen ? 'bg-purple-600 text-white' : 'bg-white/10 text-gray-300 hover:bg-white/15'"
              title="查看系列选集播放列表"
            >
              <ListMusic class="w-4 h-4" />
              <span>选集 ({{ playlist.length }})</span>
            </button>
          </div>
        </div>
      </footer>

      <!-- Series Playlist Drawer Slide-over -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="translate-x-0"
        leave-to-class="translate-x-full"
      >
        <div
          v-if="playerStore.fgAudioDrawerOpen"
          class="fixed right-0 top-0 bottom-0 w-80 sm:w-96 z-50 p-6 flex flex-col shadow-2xl border-l border-white/10 backdrop-blur-2xl"
          style="background-color: var(--bg-surface-elevated);"
        >
          <!-- Drawer Header -->
          <div class="flex items-center justify-between pb-3 border-b border-white/10">
            <div>
              <div class="flex items-center gap-2">
                <ListMusic class="w-4 h-4 text-purple-400" />
                <span class="text-sm font-semibold text-white">系列选集列表</span>
                <span class="text-xs px-2 py-0.5 rounded-full bg-white/10 text-purple-300 font-mono">
                  {{ playlist.length }}
                </span>
              </div>
              <p class="text-[11px] text-gray-400 mt-1 truncate max-w-[240px]">
                {{ currentUnit.collection_name || '当前系列' }}
              </p>
            </div>
            <button
              @click="playerStore.toggleFgAudioDrawer()"
              class="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Queue Action Toolbar -->
          <div class="py-2.5 border-b border-white/10 flex items-center justify-between">
            <button
              @click="playerStore.addMultipleToBgQueue(playlist)"
              class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium text-purple-200 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 transition-all"
              title="将整个系列的音轨全部追加到背景队列"
            >
              <Plus class="w-3.5 h-3.5 text-purple-400" />
              <span>全系列加入背景</span>
            </button>
          </div>

          <!-- Track List -->
          <div class="flex-grow overflow-y-auto pr-1 py-3 space-y-1.5">
            <div
              v-for="(unit, idx) in playlist"
              :key="unit.id"
              @click="selectTrack(idx)"
              :class="[
                'group p-2.5 rounded-xl border flex items-center justify-between gap-2 cursor-pointer transition-all select-none',
                idx === playlistIndex
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
                <Music
                  v-if="idx === playlistIndex"
                  class="w-3.5 h-3.5 text-purple-400 mr-1 animate-pulse"
                />
                <span v-if="unit.duration_seconds" class="text-[10px] font-mono text-gray-500">
                  {{ formatTime(unit.duration_seconds) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>
