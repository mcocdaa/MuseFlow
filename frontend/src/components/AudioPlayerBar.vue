<script setup>
import { computed, ref, watch } from 'vue'
import { usePlayerStore } from '../stores/playerStore'
import {
  Play,
  Pause,
  Repeat,
  Volume2,
  Timer,
  FolderOpen,
  X,
  Music
} from 'lucide-vue-next'
import { revealInExplorer } from '../api'

const playerStore = usePlayerStore()
const audioRef = ref(null)

const currentTime = ref(0)
const duration = ref(0)
const showTimerMenu = ref(false)

const currentUnit = computed(() => playerStore.activeAudioUnit)
const primaryFile = computed(() => {
  if (!currentUnit.value?.files) return null
  return currentUnit.value.files[0]
})

const audioStreamUrl = computed(() => {
  if (!primaryFile.value) return ''
  return `/api/stream/file/${primaryFile.value.id}`
})

const formatTime = (secs) => {
  if (!secs || isNaN(secs)) return '00:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

watch(() => playerStore.isPlayingAudio, (playing) => {
  if (!audioRef.value) return
  if (playing) {
    audioRef.value.play().catch(() => {})
  } else {
    audioRef.value.pause()
  }
})

watch(currentUnit, () => {
  currentTime.value = 0
  if (audioRef.value) {
    audioRef.value.currentTime = 0
    if (playerStore.isPlayingAudio) {
      audioRef.value.play().catch(() => {})
    }
  }
})

const onTimeUpdate = () => {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
  }
}

const onLoadedMetadata = () => {
  if (audioRef.value) {
    duration.value = audioRef.value.duration
  }
}

const onEnded = () => {
  if (playerStore.audioLoop && audioRef.value) {
    audioRef.value.currentTime = 0
    audioRef.value.play()
  } else {
    playerStore.isPlayingAudio = false
  }
}

const onSeek = (e) => {
  const seekTime = parseFloat(e.target.value)
  if (audioRef.value) {
    audioRef.value.currentTime = seekTime
    currentTime.value = seekTime
  }
}

const setSleep = (minutes) => {
  playerStore.setSleepTimer(minutes)
  showTimerMenu.value = false
}

const closePlayer = () => {
  playerStore.isPlayingAudio = false
  playerStore.activeAudioUnit = null
}
</script>

<template>
  <div
    v-if="currentUnit"
    class="fixed bottom-0 inset-x-0 z-40 bg-[#171923]/95 backdrop-blur-xl border-t border-white/10 px-4 py-3 shadow-2xl transition-all"
  >
    <audio
      ref="audioRef"
      :src="audioStreamUrl"
      :loop="playerStore.audioLoop"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoadedMetadata"
      @ended="onEnded"
    ></audio>

    <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
      <!-- Left Track Info -->
      <div class="flex items-center gap-3 w-full md:w-1/4 truncate">
        <div class="w-12 h-12 rounded-xl bg-black/40 border border-white/10 overflow-hidden shrink-0 flex items-center justify-center">
          <img
            :src="`/api/stream/thumbnail/${currentUnit.id}`"
            class="w-full h-full object-cover"
            @error="(e) => e.target.style.display = 'none'"
          />
          <Music class="w-6 h-6 text-purple-400 absolute pointer-events-none -z-0" />
        </div>
        <div class="truncate">
          <div class="text-sm font-semibold text-white truncate">{{ currentUnit.title }}</div>
          <div class="text-xs text-gray-400 truncate">{{ currentUnit.collection_name || '单曲欣赏' }}</div>
        </div>
      </div>

      <!-- Center Controls & Progress Bar -->
      <div class="flex flex-col items-center gap-1.5 w-full md:w-2/4">
        <!-- Control buttons -->
        <div class="flex items-center gap-4">
          <button
            @click="playerStore.audioLoop = !playerStore.audioLoop"
            :class="['p-1.5 rounded-lg transition-colors', playerStore.audioLoop ? 'text-purple-400 bg-purple-500/10' : 'text-gray-400 hover:text-white']"
            title="单曲循环"
          >
            <Repeat class="w-4 h-4" />
          </button>

          <button
            @click="playerStore.togglePlayAudio"
            class="w-10 h-10 rounded-full bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center shadow-lg shadow-purple-600/30 transition-transform active:scale-95"
          >
            <Pause v-if="playerStore.isPlayingAudio" class="w-5 h-5 fill-current" />
            <Play v-else class="w-5 h-5 ml-0.5 fill-current" />
          </button>

          <!-- Sleep Timer Dropdown -->
          <div class="relative">
            <button
              @click="showTimerMenu = !showTimerMenu"
              :class="['p-1.5 rounded-lg transition-colors flex items-center gap-1 text-xs', playerStore.audioSleepTimerMinutes > 0 ? 'text-pink-400 bg-pink-500/10' : 'text-gray-400 hover:text-white']"
              title="睡眠定时器"
            >
              <Timer class="w-4 h-4" />
              <span v-if="playerStore.audioSleepTimerMinutes > 0" class="text-[10px]">{{ playerStore.audioSleepTimerMinutes }}m</span>
            </button>

            <div
              v-if="showTimerMenu"
              class="absolute bottom-10 left-1/2 -translate-x-1/2 bg-gray-900 border border-white/10 rounded-xl p-2 shadow-2xl flex flex-col gap-1 w-28 text-xs z-50"
            >
              <div class="text-[10px] text-gray-400 px-2 py-1 font-semibold border-b border-white/5">定时关闭</div>
              <button @click="setSleep(0)" class="text-left px-2 py-1 rounded hover:bg-white/10 text-gray-300">关闭定时</button>
              <button @click="setSleep(15)" class="text-left px-2 py-1 rounded hover:bg-white/10 text-gray-300">15 分钟</button>
              <button @click="setSleep(30)" class="text-left px-2 py-1 rounded hover:bg-white/10 text-gray-300">30 分钟</button>
              <button @click="setSleep(60)" class="text-left px-2 py-1 rounded hover:bg-white/10 text-gray-300">60 分钟</button>
            </div>
          </div>
        </div>

        <!-- Slider and Timestamps -->
        <div class="w-full flex items-center gap-3">
          <span class="text-[11px] text-gray-400 font-mono w-10 text-right">{{ formatTime(currentTime) }}</span>
          <input
            type="range"
            min="0"
            :max="duration || 100"
            :value="currentTime"
            @input="onSeek"
            class="flex-grow h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-purple-500"
          />
          <span class="text-[11px] text-gray-400 font-mono w-10">{{ formatTime(duration) }}</span>
        </div>
      </div>

      <!-- Right Utility Actions -->
      <div class="flex items-center gap-2 justify-end w-full md:w-1/4">
        <button
          @click="revealInExplorer({ unit_id: currentUnit.id })"
          class="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/10"
          title="在资源管理器中定位"
        >
          <FolderOpen class="w-4 h-4 text-blue-400" />
        </button>

        <button
          @click="closePlayer"
          class="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/10"
          title="关闭播放器"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
