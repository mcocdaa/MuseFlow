<script setup>
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import {
  Play,
  Heart,
  Star,
  Layers,
  Video,
  Music,
  Image as ImageIcon,
  FolderOpen,
  ExternalLink,
  Clock,
  Sparkles
} from 'lucide-vue-next'
import { revealInExplorer, openWithDefaultApp } from '../api'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const formatDuration = (seconds) => {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const handleCardClick = (unit) => {
  if (unit.unit_type === 'video' || unit.unit_type === 'bundle') {
    const videoQueue = mediaStore.feedItems.filter(
      u => u.unit_type === 'video' || u.unit_type === 'bundle'
    )
    playerStore.openVideo(unit, videoQueue)
  } else if (unit.unit_type === 'image') {
    playerStore.openImage(unit)
  } else if (unit.unit_type === 'audio') {
    playerStore.playAudio(unit)
  }
}

const handleReveal = async (e, unit) => {
  e.stopPropagation()
  try {
    await revealInExplorer({ unit_id: unit.id })
  } catch (err) {
    alert('无法在资源管理器中定位：' + (err.response?.data?.detail || err.message))
  }
}

const handleOpenExternal = async (e, unit) => {
  e.stopPropagation()
  try {
    await openWithDefaultApp({ unit_id: unit.id })
  } catch (err) {
    alert('无法用外部程序打开：' + (err.response?.data?.detail || err.message))
  }
}

const handleRate = (e, unit, stars) => {
  e.stopPropagation()
  const newRating = unit.rating === stars ? 0 : stars
  mediaStore.updateRating(unit.id, newRating)
}

const handleToggleFavorite = (e, unit) => {
  e.stopPropagation()
  mediaStore.toggleFavorite(unit.id)
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 lg:px-8 py-6">
    <!-- Empty State -->
    <div
      v-if="!mediaStore.loading && mediaStore.feedItems.length === 0"
      class="flex flex-col items-center justify-center py-20 text-center"
    >
      <div class="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4 text-purple-400">
        <Sparkles class="w-8 h-8" />
      </div>
      <h3 class="text-lg font-medium text-white mb-2">暂无已索引的媒体内容</h3>
      <p class="text-sm text-gray-400 max-w-md mb-6">
        你的媒体库目前是空的。点击上方“纳管目录”扫描本地照片、Vlog 工程或音乐文件夹，立即体验算法信息流！
      </p>
      <button
        @click="mediaStore.scanModalOpen = true"
        class="bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium px-5 py-2.5 rounded-xl shadow-lg shadow-purple-600/30 transition-all"
      >
        立刻纳管本地目录
      </button>
    </div>

    <!-- Feed Grid / Waterfall -->
    <div
      v-else
      class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5"
    >
      <div
        v-for="unit in mediaStore.feedItems"
        :key="unit.id"
        @click="handleCardClick(unit)"
        class="group relative border rounded-2xl overflow-hidden shadow-lg transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl cursor-pointer flex flex-col"
        style="background-color: var(--bg-card); border-color: var(--border-color);"
      >
        <!-- Media Thumbnail Container -->
        <div class="relative w-full aspect-[4/3] bg-black/40 overflow-hidden flex items-center justify-center">
          <img
            :src="`/api/stream/thumbnail/${unit.id}`"
            :alt="unit.title"
            loading="lazy"
            class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            @error="(e) => e.target.style.display = 'none'"
          />

          <!-- Fallback icon if thumbnail fails or audio without cover -->
          <div class="absolute inset-0 flex items-center justify-center pointer-events-none -z-0">
            <component
              :is="unit.unit_type === 'video' || unit.unit_type === 'bundle' ? Video : unit.unit_type === 'audio' ? Music : ImageIcon"
              class="w-12 h-12 text-white/10"
            />
          </div>

          <!-- Play overlay on hover -->
          <div
            v-if="unit.unit_type !== 'image'"
            class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
          >
            <div
              class="w-12 h-12 rounded-full text-white flex items-center justify-center shadow-lg transform group-hover:scale-110 transition-transform"
              style="background-color: var(--accent-color);"
            >
              <Play class="w-6 h-6 ml-0.5 fill-current" />
            </div>
          </div>

          <!-- Unit Type Badge -->
          <div class="absolute top-2.5 left-2.5 flex items-center gap-1.5">
            <span
              v-if="unit.unit_type === 'bundle'"
              class="flex items-center gap-1 bg-purple-600/80 backdrop-blur-md text-[11px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Layers class="w-3 h-3" />
              <span>复合包</span>
            </span>
            <span
              v-else-if="unit.unit_type === 'video'"
              class="flex items-center gap-1 bg-blue-600/80 backdrop-blur-md text-[11px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Video class="w-3 h-3" />
              <span>视频</span>
            </span>
            <span
              v-else-if="unit.unit_type === 'audio'"
              class="flex items-center gap-1 bg-emerald-600/80 backdrop-blur-md text-[11px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Music class="w-3 h-3" />
              <span>音频</span>
            </span>
          </div>

          <!-- Duration Chip -->
          <div
            v-if="unit.duration_seconds"
            class="absolute bottom-2.5 right-2.5 bg-black/70 backdrop-blur-sm text-[11px] text-gray-200 px-2 py-0.5 rounded-md flex items-center gap-1 font-mono"
          >
            <Clock class="w-3 h-3 text-gray-400" />
            <span>{{ formatDuration(unit.duration_seconds) }}</span>
          </div>

          <!-- Quick Action Buttons (top right) -->
          <div class="absolute top-2.5 right-2.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              @click="(e) => handleReveal(e, unit)"
              title="在系统文件管理器中查看"
              class="p-1.5 rounded-full bg-black/60 hover:bg-black/90 text-gray-200 hover:text-white backdrop-blur-md transition-colors"
            >
              <FolderOpen class="w-3.5 h-3.5" />
            </button>
            <button
              @click="(e) => handleOpenExternal(e, unit)"
              title="使用系统默认程序打开"
              class="p-1.5 rounded-full bg-black/60 hover:bg-black/90 text-gray-200 hover:text-white backdrop-blur-md transition-colors"
            >
              <ExternalLink class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Card Body -->
        <div class="p-3.5 flex flex-col justify-between flex-grow">
          <div>
            <!-- Title -->
            <h4 class="text-sm font-medium text-gray-100 truncate group-hover:text-purple-300 transition-colors" :title="unit.title">
              {{ unit.title }}
            </h4>

            <!-- Collection Info -->
            <div class="flex items-center justify-between text-[11px] text-gray-400 mt-1">
              <span class="truncate max-w-[150px]">
                {{ unit.collection_name || '散落文件' }}
              </span>
              <span v-if="unit.view_count > 0" class="text-gray-500 font-mono">
                {{ unit.view_count }} 次浏览
              </span>
            </div>
          </div>

          <!-- Feedback & Rating Bar -->
          <div class="flex items-center justify-between mt-3 pt-2.5 border-t border-white/5">
            <!-- 5-Star Rating -->
            <div class="flex items-center gap-0.5">
              <button
                v-for="s in 5"
                :key="s"
                @click="(e) => handleRate(e, unit, s)"
                class="p-0.5 text-gray-600 hover:text-amber-400 transition-colors"
                :title="`评分 ${s} 星`"
              >
                <Star
                  :class="[
                    'w-3.5 h-3.5',
                    s <= unit.rating ? 'text-amber-400 fill-amber-400' : ''
                  ]"
                />
              </button>
            </div>

            <!-- Favorite Heart -->
            <button
              @click="(e) => handleToggleFavorite(e, unit)"
              class="p-1 text-gray-500 hover:text-rose-500 transition-colors"
              :title="unit.is_favorite ? '取消喜欢' : '标记喜欢'"
            >
              <Heart
                :class="[
                  'w-4 h-4 transition-transform active:scale-125',
                  unit.is_favorite ? 'text-rose-500 fill-rose-500' : ''
                ]"
              />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
