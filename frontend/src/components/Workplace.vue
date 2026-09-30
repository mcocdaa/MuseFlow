<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import {
  Folder,
  FolderOpen,
  Sparkles,
  Layers,
  FileVideo,
  FileAudio,
  FileImage,
  FileText,
  Search,
  ExternalLink,
  Plus,
  Tag,
  CheckCircle,
  Clock,
  HardDrive,
  Bot
} from 'lucide-vue-next'
import { revealInExplorer, openWithDefaultApp, createSuperset, addItemToSuperset } from '../api'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const selectedItem = ref(null)
const newSupersetName = ref('')
const showNewSupersetInput = ref(false)

onMounted(() => {
  mediaStore.loadWorkplaceItems()
})

const handleSelectCollection = (colId) => {
  mediaStore.selectedCollectionId = colId
  mediaStore.selectedSupersetId = null
  mediaStore.loadWorkplaceItems()
}

const handleSelectSuperset = (supersetId) => {
  mediaStore.selectedSupersetId = supersetId
  mediaStore.selectedCollectionId = null
  mediaStore.loadWorkplaceItems()
}

const handleCreateSuperset = async () => {
  if (!newSupersetName.value.trim()) return
  try {
    await createSuperset({ name: newSupersetName.value.trim() })
    newSupersetName.value = ''
    showNewSupersetInput.value = false
    await mediaStore.loadSupersets()
  } catch (err) {
    alert('创建超集失败：' + err.message)
  }
}

const handleAddToSuperset = async (supersetId) => {
  if (!selectedItem.value) return
  try {
    await addItemToSuperset(supersetId, selectedItem.value.id)
    alert('已成功加入超集！')
    await mediaStore.loadSupersets()
  } catch (err) {
    alert('添加失败：' + err.message)
  }
}

const handleSearch = () => {
  mediaStore.loadWorkplaceItems()
}

const handleItemClick = (item) => {
  selectedItem.value = item
}

const handleDoubleClick = (item) => {
  if (item.unit_type === 'video' || item.unit_type === 'bundle') {
    playerStore.openVideo(item)
  } else if (item.unit_type === 'image') {
    playerStore.openImage(item)
  } else if (item.unit_type === 'audio') {
    playerStore.playAudio(item)
  }
}

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 lg:px-8 py-6">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[700px]">
      <!-- Left Sidebar: Collections & Supersets -->
      <aside
        class="lg:col-span-3 border rounded-2xl p-4 flex flex-col gap-6 transition-colors"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- All Root Items -->
        <div>
          <button
            @click="handleSelectCollection(null); handleSelectSuperset(null)"
            :class="[
              'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-colors text-left',
              !mediaStore.selectedCollectionId && !mediaStore.selectedSupersetId
                ? 'bg-purple-600/30 text-purple-200 border border-purple-500/30'
                : 'text-gray-300 hover:bg-white/5'
            ]"
          >
            <span class="flex items-center gap-2">
              <HardDrive class="w-4 h-4 text-purple-400" />
              <span>全部资产</span>
            </span>
          </button>
        </div>

        <!-- Collections / Folders Tree -->
        <div>
          <div class="flex items-center justify-between text-xs font-semibold text-gray-400 mb-2.5 px-1">
            <span class="flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
              <Folder class="w-3.5 h-3.5 text-blue-400" />
              <span>系列目录 (Collections)</span>
            </span>
            <div class="flex items-center gap-1">
              <button
                @click="mediaStore.openAIOrganizer()"
                class="p-1 hover:text-purple-300 text-purple-400/80 rounded transition-colors"
                title="AI 智能整理分析"
              >
                <Bot class="w-3.5 h-3.5" />
              </button>
              <span class="text-[11px] text-gray-500">{{ mediaStore.collections.length }}</span>
            </div>
          </div>

          <div class="space-y-1 max-h-60 overflow-y-auto pr-1">
            <div
              v-for="col in mediaStore.collections"
              :key="col.id"
              class="group/col flex items-center justify-between rounded-lg transition-colors text-left"
              :class="[
                mediaStore.selectedCollectionId === col.id
                  ? 'bg-blue-600/30 text-blue-200 border border-blue-500/30'
                  : 'text-gray-300 hover:bg-white/5'
              ]"
            >
              <button
                @click="handleSelectCollection(col.id)"
                class="flex-grow flex items-center justify-between px-2.5 py-1.5 text-xs truncate"
              >
                <span class="truncate flex items-center gap-2">
                  <FolderOpen class="w-3.5 h-3.5 text-blue-400 shrink-0" />
                  <span class="truncate">{{ col.name }}</span>
                </span>
                <span class="text-[10px] text-gray-500 shrink-0 bg-white/5 px-1.5 py-0.5 rounded-full mr-1">
                  {{ col.unit_count }}
                </span>
              </button>

              <button
                v-if="col.folder_path"
                @click.stop="mediaStore.openAIOrganizer(col.folder_path)"
                class="p-1.5 text-purple-400 opacity-0 group-hover/col:opacity-100 hover:text-purple-200 transition-opacity"
                title="AI 深入分析并整理此系列"
              >
                <Bot class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        <!-- Virtual Supersets -->
        <div>
          <div class="flex items-center justify-between text-xs font-semibold text-gray-400 mb-2.5 px-1">
            <span class="flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
              <Sparkles class="w-3.5 h-3.5 text-pink-400" />
              <span>虚拟超集 (Supersets)</span>
            </span>
            <button
              @click="showNewSupersetInput = !showNewSupersetInput"
              class="p-1 hover:text-white text-gray-400 rounded transition-colors"
              title="新建跨目录超集"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- New Superset input -->
          <div v-if="showNewSupersetInput" class="mb-2 flex items-center gap-1.5">
            <input
              v-model="newSupersetName"
              type="text"
              placeholder="例如: 好友小李的照片"
              class="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500/50"
              @keyup.enter="handleCreateSuperset"
            />
            <button
              @click="handleCreateSuperset"
              class="bg-pink-600 hover:bg-pink-500 text-white text-xs px-2 py-1 rounded-lg shrink-0"
            >
              确定
            </button>
          </div>

          <div class="space-y-1 max-h-60 overflow-y-auto pr-1">
            <button
              v-for="sup in mediaStore.supersets"
              :key="sup.id"
              @click="handleSelectSuperset(sup.id)"
              :class="[
                'w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors text-left',
                mediaStore.selectedSupersetId === sup.id
                  ? 'bg-pink-600/30 text-pink-200 border border-pink-500/30'
                  : 'text-gray-300 hover:bg-white/5'
              ]"
            >
              <span class="truncate flex items-center gap-2">
                <Tag class="w-3.5 h-3.5 text-pink-400 shrink-0" />
                <span class="truncate">{{ sup.name }}</span>
              </span>
              <span class="text-[10px] text-gray-500 shrink-0 bg-white/5 px-1.5 py-0.5 rounded-full">
                {{ sup.unit_count }}
              </span>
            </button>
          </div>
        </div>
      </aside>

      <!-- Main Explorer Area -->
      <main
        class="lg:col-span-6 border rounded-2xl p-4 flex flex-col transition-colors"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Top Toolbar -->
        <div class="flex items-center gap-3 mb-4">
          <div class="relative flex-grow">
            <Search class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              v-model="mediaStore.searchQuery"
              @input="handleSearch"
              type="text"
              placeholder="搜索资产单元标题..."
              class="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
            />
          </div>

          <button
            @click="mediaStore.openAIOrganizer()"
            class="flex items-center gap-1.5 bg-gradient-to-r from-purple-600/30 to-pink-600/30 hover:from-purple-600/40 hover:to-pink-600/40 border border-purple-500/40 text-purple-200 text-xs px-3 py-2 rounded-xl transition-all shrink-0 shadow-sm"
            title="对当前或指定文件夹进行 AI 拓扑分析与重组"
          >
            <Bot class="w-4 h-4 text-purple-400" />
            <span>AI 深度整理</span>
          </button>
        </div>

        <!-- Items Table / Grid -->
        <div class="flex-grow overflow-y-auto pr-1 space-y-2">
          <div
            v-if="mediaStore.workplaceItems.length === 0"
            class="text-center py-16 text-gray-500 text-xs"
          >
            暂无匹配的资产单元
          </div>

          <div
            v-for="item in mediaStore.workplaceItems"
            :key="item.id"
            @click="handleItemClick(item)"
            @dblclick="handleDoubleClick(item)"
            :class="[
              'p-3 rounded-xl border flex items-center justify-between gap-3 cursor-pointer transition-all select-none',
              selectedItem?.id === item.id
                ? 'bg-purple-600/20 border-purple-500/40 text-purple-100 shadow-md'
                : 'bg-white/5 hover:bg-white/10 border-white/5 text-gray-300'
            ]"
          >
            <!-- Left Info -->
            <div class="flex items-center gap-3 truncate">
              <!-- Icon/Thumbnail -->
              <div class="w-10 h-10 rounded-lg bg-black/40 overflow-hidden shrink-0 flex items-center justify-center border border-white/10">
                <img
                  :src="`/api/stream/thumbnail/${item.id}`"
                  class="w-full h-full object-cover"
                  loading="lazy"
                  @error="(e) => e.target.style.display = 'none'"
                />
              </div>

              <div class="truncate">
                <div class="text-xs font-medium truncate flex items-center gap-2">
                  <span class="truncate">{{ item.title }}</span>
                  <span
                    v-if="item.unit_type === 'bundle'"
                    class="bg-purple-500/20 text-purple-300 text-[10px] px-1.5 py-0.2 rounded border border-purple-500/30 shrink-0"
                  >
                    复合包 ({{ item.files?.length || 1 }}文件)
                  </span>
                </div>
                <div class="text-[11px] text-gray-400 mt-0.5 flex items-center gap-3">
                  <span>{{ item.collection_name || '散落文件' }}</span>
                  <span v-if="item.width && item.height">{{ item.width }}x{{ item.height }}</span>
                  <span v-if="item.files?.length > 0">{{ formatBytes(item.files[0]?.file_size) }}</span>
                </div>
              </div>
            </div>

            <!-- Double Click hint -->
            <div class="text-[11px] text-gray-500 shrink-0 hidden sm:block">
              双击预览
            </div>
          </div>
        </div>
      </main>

      <!-- Right Inspector Details Drawer -->
      <aside
        class="lg:col-span-3 border rounded-2xl p-4 flex flex-col justify-between transition-colors"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div v-if="selectedItem" class="space-y-5">
          <!-- Title & Type Header -->
          <div>
            <span class="text-[10px] uppercase tracking-wider font-semibold text-purple-400">
              {{ selectedItem.unit_type === 'bundle' ? '复合消费包' : selectedItem.unit_type }}
            </span>
            <h3 class="text-sm font-semibold text-white mt-1 break-words">
              {{ selectedItem.title }}
            </h3>
          </div>

          <!-- Preview Thumbnail -->
          <div class="w-full aspect-video rounded-xl bg-black/50 border border-white/10 overflow-hidden flex items-center justify-center">
            <img
              :src="`/api/stream/thumbnail/${selectedItem.id}`"
              class="w-full h-full object-cover"
            />
          </div>

          <!-- External Actions -->
          <div class="space-y-2">
            <button
              @click="revealInExplorer({ unit_id: selectedItem.id })"
              class="w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/15 text-white text-xs py-2 px-3 rounded-xl border border-white/10 transition-colors"
            >
              <FolderOpen class="w-3.5 h-3.5 text-blue-400" />
              <span>在系统文件资源管理器中定位</span>
            </button>
            <button
              @click="openWithDefaultApp({ unit_id: selectedItem.id })"
              class="w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/15 text-white text-xs py-2 px-3 rounded-xl border border-white/10 transition-colors"
            >
              <ExternalLink class="w-3.5 h-3.5 text-purple-400" />
              <span>使用外部默认程序打开</span>
            </button>
          </div>

          <!-- Attached Physical Files List -->
          <div>
            <div class="text-xs font-semibold text-gray-400 mb-2">
              纳管物理文件 ({{ selectedItem.files?.length || 0 }})
            </div>
            <div class="space-y-1.5 max-h-48 overflow-y-auto">
              <div
                v-for="f in selectedItem.files"
                :key="f.id"
                class="bg-white/5 border border-white/5 rounded-lg p-2 text-xs flex flex-col gap-1"
              >
                <div class="flex items-center justify-between text-gray-200">
                  <span class="truncate font-mono text-[11px]" :title="f.file_name">{{ f.file_name }}</span>
                  <span class="text-[10px] text-purple-300 uppercase px-1 py-0.2 rounded bg-purple-500/20 shrink-0">
                    {{ f.role }}
                  </span>
                </div>
                <div class="text-[10px] text-gray-500 flex justify-between font-mono">
                  <span>{{ formatBytes(f.file_size) }}</span>
                  <button
                    @click="revealInExplorer({ file_id: f.id })"
                    class="text-blue-400 hover:underline"
                  >
                    定位此文件
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Add to Superset -->
          <div v-if="mediaStore.supersets.length > 0">
            <div class="text-xs font-semibold text-gray-400 mb-2">关联至虚拟超集</div>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="sup in mediaStore.supersets"
                :key="sup.id"
                @click="handleAddToSuperset(sup.id)"
                class="text-[11px] bg-pink-500/10 hover:bg-pink-500/20 text-pink-300 border border-pink-500/30 px-2 py-0.5 rounded-full transition-colors flex items-center gap-1"
              >
                <Plus class="w-3 h-3" />
                <span>{{ sup.name }}</span>
              </button>
            </div>
          </div>
        </div>

        <div v-else class="text-center py-20 text-gray-500 text-xs">
          点击左侧文件单元查看详情与物理文件拓扑
        </div>
      </aside>
    </div>
  </div>
</template>
