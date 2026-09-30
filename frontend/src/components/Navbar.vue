<script setup>
import { computed } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import {
  Compass,
  FolderOpen,
  Sparkles,
  Image as ImageIcon,
  Video,
  Music,
  LayoutGrid,
  RefreshCw,
  FolderSearch,
  BrainCircuit
} from 'lucide-vue-next'

const mediaStore = useMediaStore()

const categories = [
  { id: 'all', name: '全部', icon: LayoutGrid },
  { id: 'image', name: '图片', icon: ImageIcon },
  { id: 'video', name: '视频 / 复合包', icon: Video },
  { id: 'audio', name: '音乐', icon: Music },
]

const handleCategoryChange = (catId) => {
  mediaStore.activeCategory = catId
  if (mediaStore.currentMode === 'stream') {
    mediaStore.loadFeed()
  } else {
    mediaStore.loadWorkplaceItems()
  }
}

const handleAlgorithmChange = (e) => {
  mediaStore.selectedAlgorithm = e.target.value
  mediaStore.loadFeed()
}

const handleRefresh = () => {
  if (mediaStore.currentMode === 'stream') {
    mediaStore.loadFeed()
  } else {
    mediaStore.loadWorkplaceItems()
  }
}
</script>

<template>
  <header class="sticky top-0 z-30 bg-[#0f1117]/80 backdrop-blur-md border-b border-white/10 px-4 lg:px-8 py-3">
    <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
      <!-- Brand & Mode Switch -->
      <div class="flex items-center gap-6 w-full md:w-auto justify-between md:justify-start">
        <div class="flex items-center gap-2 cursor-pointer" @click="mediaStore.currentMode = 'stream'">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Compass class="w-5 h-5 text-white" />
          </div>
          <div>
            <div class="font-bold text-lg tracking-wide bg-gradient-to-r from-purple-300 via-pink-200 to-indigo-200 bg-clip-text text-transparent">
              MuseFlow
            </div>
            <div class="text-[10px] text-gray-400 -mt-1 font-medium tracking-wider">灵眸流 · 记忆中枢</div>
          </div>
        </div>

        <!-- Mode Toggle Tabs -->
        <div class="flex items-center p-1 bg-white/5 rounded-xl border border-white/10">
          <button
            @click="mediaStore.currentMode = 'stream'"
            :class="[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              mediaStore.currentMode === 'stream'
                ? 'bg-purple-600 text-white shadow-md'
                : 'text-gray-400 hover:text-gray-200'
            ]"
          >
            <Sparkles class="w-3.5 h-3.5" />
            <span>沉浸流 (Stream)</span>
          </button>
          <button
            @click="mediaStore.currentMode = 'workplace'; mediaStore.loadWorkplaceItems()"
            :class="[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              mediaStore.currentMode === 'workplace'
                ? 'bg-purple-600 text-white shadow-md'
                : 'text-gray-400 hover:text-gray-200'
            ]"
          >
            <FolderOpen class="w-3.5 h-3.5" />
            <span>工作台 (Workplace)</span>
          </button>
        </div>
      </div>

      <!-- Categories & Filtering -->
      <div class="flex items-center gap-2 overflow-x-auto max-w-full pb-1 md:pb-0">
        <button
          v-for="cat in categories"
          :key="cat.id"
          @click="handleCategoryChange(cat.id)"
          :class="[
            'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all border shrink-0',
            mediaStore.activeCategory === cat.id
              ? 'bg-white/15 border-purple-400/50 text-purple-300 shadow-sm'
              : 'bg-white/5 border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/10'
          ]"
        >
          <component :is="cat.icon" class="w-3.5 h-3.5" />
          <span>{{ cat.name }}</span>
        </button>
      </div>

      <!-- Actions & Algorithm Dropdown -->
      <div class="flex items-center gap-2.5 w-full md:w-auto justify-end">
        <!-- Recommender selector (only in stream mode) -->
        <div v-if="mediaStore.currentMode === 'stream'" class="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1">
          <Sparkles class="w-3.5 h-3.5 text-purple-400" />
          <select
            :value="mediaStore.selectedAlgorithm"
            @change="handleAlgorithmChange"
            class="bg-transparent text-xs text-gray-200 focus:outline-none cursor-pointer"
          >
            <option
              v-for="algo in mediaStore.algorithms"
              :key="algo.name"
              :value="algo.name"
              class="bg-gray-900 text-white"
            >
              {{ algo.display_name }}
            </option>
          </select>
        </div>

        <!-- AI Memory Recap -->
        <button
          @click="mediaStore.recapModalOpen = true"
          title="AI 记忆唤醒与待整理建议"
          class="flex items-center gap-1.5 bg-gradient-to-r from-pink-500/20 to-purple-500/20 border border-pink-500/30 hover:border-pink-500/50 text-pink-300 text-xs px-2.5 py-1.5 rounded-lg transition-all"
        >
          <BrainCircuit class="w-3.5 h-3.5 text-pink-400" />
          <span class="hidden sm:inline">AI 记忆中枢</span>
        </button>

        <!-- Scan Directory Button -->
        <button
          @click="mediaStore.scanModalOpen = true"
          class="flex items-center gap-1.5 bg-white/10 hover:bg-white/15 text-white text-xs px-3 py-1.5 rounded-lg transition-all border border-white/10"
        >
          <FolderSearch class="w-3.5 h-3.5 text-indigo-400" />
          <span>纳管目录</span>
        </button>

        <!-- Refresh Button -->
        <button
          @click="handleRefresh"
          title="刷新内容"
          class="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
        >
          <RefreshCw :class="['w-4 h-4', mediaStore.loading ? 'animate-spin text-purple-400' : '']" />
        </button>
      </div>
    </div>
  </header>
</template>
