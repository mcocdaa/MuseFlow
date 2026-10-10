<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { usePlayerStore } from '../stores/playerStore'
import { useMediaStore } from '../stores/mediaStore'
import {
  ListMusic,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Trash2,
  X,
  Sparkles,
  ChevronUp,
  ChevronDown,
  GripVertical,
  Music,
  Video,
  Layers,
  Repeat,
  Repeat1,
  Shuffle,
  Volume2,
  VolumeX,
  Power
} from 'lucide-vue-next'

const playerStore = usePlayerStore()
const mediaStore = useMediaStore()

const showSaveSupersetInput = ref(false)
const supersetNameInput = ref('')
const draggedIndex = ref(null)

const isOpen = computed(() => playerStore.queueDrawerOpen)
const currentUnit = computed(() => playerStore.activeBgUnit)
const isPlaying = computed(() => playerStore.isBgPlaying)
const queue = computed(() => playerStore.bgQueue)

const handleSaveSuperset = async () => {
  if (!supersetNameInput.value.trim()) return
  try {
    await playerStore.saveBgQueueAsSuperset(supersetNameInput.value.trim())
    await mediaStore.loadSupersets()
    supersetNameInput.value = ''
    showSaveSupersetInput.value = false
  } catch (err) {
    console.error('Failed to save queue as superset', err)
  }
}

const onDragStart = (e, idx) => {
  draggedIndex.value = idx
  e.dataTransfer.effectAllowed = 'move'
}

const onDragOver = (e) => {
  e.preventDefault()
}

const onDrop = (e, targetIdx) => {
  e.preventDefault()
  if (draggedIndex.value !== null && draggedIndex.value !== targetIdx) {
    playerStore.moveBgQueueItem(draggedIndex.value, targetIdx)
  }
  draggedIndex.value = null
}

const moveUp = (e, idx) => {
  e.stopPropagation()
  if (idx > 0) playerStore.moveBgQueueItem(idx, idx - 1)
}

const moveDown = (e, idx) => {
  e.stopPropagation()
  if (idx < queue.value.length - 1) playerStore.moveBgQueueItem(idx, idx + 1)
}

const removeItem = (e, idx) => {
  e.stopPropagation()
  playerStore.removeFromBgQueue(idx)
}

const playItem = (unit) => {
  const targetViewMode = playerStore.bgViewMode === 'hidden' ? 'disc' : playerStore.bgViewMode
  playerStore.playAudio(unit, playerStore.bgQueue, targetViewMode)
}

const handleClearQueue = () => {
  if (queue.value.length === 0) return
  if (confirm('确定清空当前背景播放队列吗？播放将随之停止。')) {
    playerStore.clearBgQueue()
  }
}

const handleExitPlayback = () => {
  playerStore.stopAndExitBgPlayback()
}

const close = () => {
  playerStore.closeQueueDrawer()
}

const handleKeyDown = (e) => {
  if (!isOpen.value) return
  if (e.key === 'Escape') {
    close()
  }
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown))
</script>

<template>
  <!-- Global Backdrop & Slide-over Drawer -->
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end"
      @click.self="close"
    >
      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="translate-x-0"
        leave-to-class="translate-x-full"
      >
        <div
          v-if="isOpen"
          class="w-full max-w-md h-full flex flex-col shadow-2xl border-l border-white/10 select-none backdrop-blur-2xl"
          style="background-color: var(--bg-surface-elevated);"
        >
          <!-- Drawer Header -->
          <div class="px-5 py-4 border-b border-white/10 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div
                class="w-8 h-8 rounded-xl flex items-center justify-center text-white shadow"
                style="background-color: var(--accent-color);"
              >
                <ListMusic class="w-4 h-4" />
              </div>
              <div>
                <h3 class="text-sm font-semibold text-white tracking-wide">背景播放队列</h3>
                <p class="text-[11px] text-gray-400 font-mono">
                  共 {{ queue.length }} 项
                  <span v-if="currentUnit">· 正在播放第 {{ playerStore.bgQueueIndex + 1 }} 项</span>
                </p>
              </div>
            </div>

            <!-- Header Quick Actions -->
            <div class="flex items-center gap-1.5">
              <!-- Exit / Stop playback -->
              <button
                v-if="currentUnit || isPlaying"
                @click="handleExitPlayback"
                class="p-1.5 text-gray-400 hover:text-amber-400 hover:bg-amber-400/10 rounded-lg transition-colors"
                title="停止并退出背景播放"
              >
                <Power class="w-4 h-4" />
              </button>

              <!-- Close drawer -->
              <button
                @click="close"
                class="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                title="关闭面板 (Esc)"
              >
                <X class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Queue Management Toolbar -->
          <div class="px-5 py-2.5 bg-white/5 border-b border-white/10 flex items-center justify-between gap-2 text-xs">
            <!-- Save as Superset Trigger -->
            <button
              @click="showSaveSupersetInput = !showSaveSupersetInput"
              :disabled="queue.length === 0"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium text-pink-200 bg-pink-600/20 hover:bg-pink-600/30 border border-pink-500/30 transition-all disabled:opacity-40 disabled:pointer-events-none active:scale-95"
              title="将当前活跃队列另存为持久化虚拟超集"
            >
              <Sparkles class="w-3.5 h-3.5 text-pink-400" />
              <span>另存为超集</span>
            </button>

            <!-- Clear Queue -->
            <button
              @click="handleClearQueue"
              :disabled="queue.length === 0"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-gray-400 hover:text-rose-300 hover:bg-rose-500/10 transition-all disabled:opacity-40 disabled:pointer-events-none active:scale-95"
              title="清空当前队列"
            >
              <Trash2 class="w-3.5 h-3.5" />
              <span>清空队列</span>
            </button>
          </div>

          <!-- Inline Save As Superset Dialog -->
          <div
            v-if="showSaveSupersetInput"
            class="m-4 p-3 rounded-2xl bg-pink-950/40 border border-pink-500/30 flex flex-col gap-2 transition-all"
          >
            <div class="text-[11px] font-medium text-pink-300 flex items-center justify-between">
              <span>保存队列为虚拟超集</span>
              <span class="text-gray-400 font-mono">{{ queue.length }}项</span>
            </div>
            <div class="flex items-center gap-2">
              <input
                v-model="supersetNameInput"
                type="text"
                placeholder="例如: 沉浸心流精选集..."
                class="flex-grow bg-black/40 border border-white/15 rounded-xl px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
                @keyup.enter="handleSaveSuperset"
                autofocus
              />
              <button
                @click="handleSaveSuperset"
                class="px-3 py-1.5 bg-pink-600 hover:bg-pink-500 text-white rounded-xl text-xs font-medium transition-colors shrink-0"
              >
                保存
              </button>
              <button
                @click="showSaveSupersetInput = false"
                class="px-2 py-1.5 text-gray-400 hover:text-white text-xs"
              >
                取消
              </button>
            </div>
          </div>

          <!-- Empty State -->
          <div
            v-if="queue.length === 0"
            class="flex-grow flex flex-col items-center justify-center text-center p-8 text-gray-500"
          >
            <div class="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-3 text-purple-400">
              <ListMusic class="w-7 h-7" />
            </div>
            <h4 class="text-sm font-medium text-gray-300 mb-1">播放队列为空</h4>
            <p class="text-xs text-gray-500 max-w-xs leading-relaxed">
              在沉浸流或工作台中，悬浮卡片点击「加入队列」或开启「批量模式」即可随时收录音乐与视频
            </p>
          </div>

          <!-- Queue Track List with Drag & Reorder & Remove -->
          <div v-else class="flex-grow overflow-y-auto px-4 py-3 space-y-1.5">
            <div
              v-for="(unit, idx) in queue"
              :key="unit.id"
              draggable="true"
              @dragstart="onDragStart($event, idx)"
              @dragover="onDragOver"
              @drop="onDrop($event, idx)"
              @click="playItem(unit)"
              :class="[
                'group p-2.5 rounded-xl border flex items-center justify-between gap-2.5 cursor-pointer transition-all select-none',
                currentUnit?.id === unit.id
                  ? 'bg-purple-600/25 border-purple-500/50 text-purple-100 shadow-md ring-1 ring-purple-500/30'
                  : 'bg-white/5 border-transparent text-gray-300 hover:bg-white/10 hover:border-white/10'
              ]"
            >
              <!-- Left: Drag Handle, Number/Indicator, Thumbnail, Title -->
              <div class="flex items-center gap-2.5 truncate min-w-0">
                <!-- Drag Grip Icon -->
                <GripVertical
                  class="w-3.5 h-3.5 text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab shrink-0 -mr-1"
                  title="按住拖拽调整顺序"
                />

                <!-- Index or Equalizer animation -->
                <div class="w-5 text-center shrink-0">
                  <span
                    v-if="currentUnit?.id === unit.id && isPlaying"
                    class="flex items-center justify-center gap-0.5 h-3.5"
                  >
                    <span class="w-0.5 h-3 bg-purple-400 rounded-full animate-pulse" />
                    <span class="w-0.5 h-2 bg-pink-400 rounded-full animate-pulse" style="animation-delay: 150ms;" />
                    <span class="w-0.5 h-3.5 bg-purple-300 rounded-full animate-pulse" style="animation-delay: 300ms;" />
                  </span>
                  <span v-else class="text-[11px] font-mono text-gray-500">
                    {{ idx + 1 }}
                  </span>
                </div>

                <!-- Thumbnail -->
                <div class="w-9 h-9 rounded-lg bg-black/40 overflow-hidden shrink-0 flex items-center justify-center border border-white/10">
                  <img
                    :src="`/api/stream/thumbnail/${unit.id}`"
                    class="w-full h-full object-cover"
                    loading="lazy"
                    @error="(e) => e.target.style.display = 'none'"
                  />
                  <component
                    :is="unit.unit_type === 'video' ? Video : unit.unit_type === 'bundle' ? Layers : Music"
                    class="w-4 h-4 text-white/40"
                  />
                </div>

                <!-- Title & Collection -->
                <div class="truncate">
                  <h4 class="text-xs font-medium truncate" :title="unit.title">
                    {{ unit.title }}
                  </h4>
                  <p class="text-[10px] text-gray-400 truncate mt-0.5">
                    {{ unit.collection_name || '散落文件' }}
                  </p>
                </div>
              </div>

              <!-- Right: Reorder & Remove Actions -->
              <div class="flex items-center gap-0.5 shrink-0">
                <!-- Move Up Button -->
                <button
                  @click="moveUp($event, idx)"
                  :disabled="idx === 0"
                  class="p-1 text-gray-400 hover:text-white rounded hover:bg-white/10 transition-colors disabled:opacity-20"
                  title="上移"
                >
                  <ChevronUp class="w-3.5 h-3.5" />
                </button>

                <!-- Move Down Button -->
                <button
                  @click="moveDown($event, idx)"
                  :disabled="idx === queue.length - 1"
                  class="p-1 text-gray-400 hover:text-white rounded hover:bg-white/10 transition-colors disabled:opacity-20"
                  title="下移"
                >
                  <ChevronDown class="w-3.5 h-3.5" />
                </button>

                <!-- Remove Button -->
                <button
                  @click="removeItem($event, idx)"
                  class="p-1 text-gray-400 hover:text-rose-400 rounded hover:bg-rose-500/10 transition-colors ml-0.5"
                  title="从队列中移除"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          <!-- Bottom Console Deck -->
          <div
            v-if="currentUnit"
            class="px-5 py-4 border-t border-white/10 bg-black/40 flex flex-col gap-3"
          >
            <!-- Current Track Info Strip -->
            <div class="flex items-center justify-between text-xs">
              <div class="truncate pr-2">
                <span class="text-gray-400 text-[11px]">正在播放: </span>
                <span class="font-medium text-white">{{ currentUnit.title }}</span>
              </div>
              <span class="text-[10px] text-purple-300 font-mono shrink-0 uppercase px-1.5 py-0.5 rounded bg-purple-500/20">
                {{ currentUnit.unit_type }}
              </span>
            </div>

            <!-- Transport Buttons & Play Mode -->
            <div class="flex items-center justify-between">
              <!-- Play Mode Toggle -->
              <button
                @click="playerStore.toggleAudioPlayMode()"
                class="p-2 text-gray-400 hover:text-white rounded-xl hover:bg-white/10 transition-colors"
                :title="`播放模式: ${playerStore.bgPlayMode === 'repeat' ? '单曲循环' : playerStore.bgPlayMode === 'shuffle' ? '随机播放' : '列表顺序'}`"
              >
                <Repeat1 v-if="playerStore.bgPlayMode === 'repeat'" class="w-4 h-4 text-purple-400" />
                <Shuffle v-else-if="playerStore.bgPlayMode === 'shuffle'" class="w-4 h-4 text-purple-400" />
                <Repeat v-else class="w-4 h-4" />
              </button>

              <!-- Center Transport -->
              <div class="flex items-center gap-3">
                <button
                  @click="playerStore.prevAudio()"
                  class="p-2 text-gray-300 hover:text-white rounded-full hover:bg-white/10 transition-all active:scale-95"
                  title="上一首"
                >
                  <SkipBack class="w-4 h-4 fill-current" />
                </button>

                <button
                  @click="playerStore.togglePlayAudio()"
                  class="w-10 h-10 rounded-full text-white flex items-center justify-center shadow-lg transition-transform active:scale-95"
                  style="background-color: var(--accent-color);"
                  :title="isPlaying ? '暂停' : '播放'"
                >
                  <Pause v-if="isPlaying" class="w-4 h-4 fill-current" />
                  <Play v-else class="w-4 h-4 ml-0.5 fill-current" />
                </button>

                <button
                  @click="playerStore.nextAudio()"
                  class="p-2 text-gray-300 hover:text-white rounded-full hover:bg-white/10 transition-all active:scale-95"
                  title="下一首"
                >
                  <SkipForward class="w-4 h-4 fill-current" />
                </button>
              </div>

              <!-- Volume Slider & Mute -->
              <div class="flex items-center gap-1.5">
                <button
                  @click="playerStore.toggleBgMute()"
                  class="p-1.5 text-gray-400 hover:text-white rounded-lg transition-colors"
                  :title="playerStore.bgVolume === 0 ? '取消静音' : '静音'"
                >
                  <VolumeX v-if="playerStore.bgVolume === 0" class="w-4 h-4 text-rose-400" />
                  <Volume2 v-else class="w-4 h-4 text-gray-300" />
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.02"
                  :value="playerStore.bgVolume"
                  @input="playerStore.setBgVolume($event.target.value)"
                  class="w-16 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-400"
                  title="音量调节"
                />
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>
