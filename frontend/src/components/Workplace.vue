<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import {
  Folder,
  FolderOpen,
  FolderCog,
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
  Bot,
  Play,
  ListPlus,
  Tv,
  Trash2,
  CheckSquare,
  Check,
  MinusCircle,
  X,
  BookmarkPlus,
  Anchor
} from 'lucide-vue-next'
import {
  revealInExplorer,
  openWithDefaultApp,
  createSuperset,
  addItemToSuperset,
  removeItemFromSuperset,
  deleteSuperset,
  fetchUnitTags,
  fetchAllTagsFlat,
  assignTag,
  removeTag,
  createTag
} from '../api'
import PipelineBuilderModal from './PipelineBuilderModal.vue'
import TagManagerModal from './TagManagerModal.vue'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const selectedItem = ref(null)
const newSupersetName = ref('')
const showNewSupersetInput = ref(false)
const showPipelineModal = ref(false)
const showTagManagerModal = ref(false)

// OOP Tag Inspector & Autocomplete
const selectedItemTags = ref([])
const allTagsFlat = ref([])
const isAddingTag = ref(false)
const tagSearchQuery = ref('')
const tagInputRef = ref(null)

// Batch Selection Mode
const isBatchMode = ref(false)
const selectedIds = ref(new Set())
const showBatchSupersetModal = ref(false)
const batchNewSupersetName = ref('')

onMounted(() => {
  mediaStore.loadWorkplaceItems()
  loadAllTags()
})

const loadAllTags = async () => {
  try {
    const list = await fetchAllTagsFlat()
    allTagsFlat.value = list || []
  } catch (e) {
    console.error('Failed to load all flat tags:', e)
  }
}

const loadSelectedItemTags = async () => {
  if (!selectedItem.value) {
    selectedItemTags.value = []
    return
  }
  try {
    const tags = await fetchUnitTags(selectedItem.value.id)
    selectedItemTags.value = tags || []
  } catch (e) {
    selectedItemTags.value = selectedItem.value.tags || []
  }
}

watch(selectedItem, () => {
  isAddingTag.value = false
  tagSearchQuery.value = ''
  loadSelectedItemTags()
})

const openAddTagInput = async () => {
  isAddingTag.value = true
  tagSearchQuery.value = ''
  if (!allTagsFlat.value.length) {
    await loadAllTags()
  }
  nextTick(() => {
    tagInputRef.value?.focus()
  })
}

const availableTagSuggestions = computed(() => {
  if (!tagSearchQuery.value.trim()) return allTagsFlat.value.slice(0, 8)
  const q = tagSearchQuery.value.trim().toLowerCase()
  return allTagsFlat.value.filter(t =>
    t.name.toLowerCase().includes(q) ||
    (t.display_path && t.display_path.toLowerCase().includes(q))
  ).slice(0, 8)
})

const handleAssignTag = async (tag) => {
  if (!selectedItem.value) return
  try {
    await assignTag(selectedItem.value.id, {
      tag_id: tag.id || tag.tag_id,
      is_primary_landing: false,
    })
    tagSearchQuery.value = ''
    isAddingTag.value = false
    await loadSelectedItemTags()
    playerStore.showToast(`已为作品关联标签: 「${tag.name}」`)
  } catch (err) {
    playerStore.showToast('关联标签失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleCreateAndAssignTag = async () => {
  if (!selectedItem.value || !tagSearchQuery.value.trim()) return
  try {
    const existing = allTagsFlat.value.find(t => t.name.toLowerCase() === tagSearchQuery.value.trim().toLowerCase())
    let tagId = existing ? existing.id : null
    if (!tagId) {
      const created = await createTag({
        name: tagSearchQuery.value.trim(),
        tag_class_id: 2, // domain
      })
      tagId = created.id
      await loadAllTags()
    }
    await assignTag(selectedItem.value.id, {
      tag_id: tagId,
      is_primary_landing: false,
    })
    tagSearchQuery.value = ''
    isAddingTag.value = false
    await loadSelectedItemTags()
    playerStore.showToast('打标成功！')
  } catch (err) {
    playerStore.showToast('打标失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleTogglePrimaryLanding = async (tag) => {
  if (!selectedItem.value) return
  try {
    const newStatus = !tag.is_primary_landing
    await assignTag(selectedItem.value.id, {
      tag_id: tag.tag_id,
      is_primary_landing: newStatus,
    })
    await loadSelectedItemTags()
    playerStore.showToast(`已${newStatus ? '设为' : '取消'}物理落点锚点: 「${tag.name}」`)
  } catch (err) {
    playerStore.showToast('设置落点失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleRemoveTag = async (tag) => {
  if (!selectedItem.value) return
  try {
    await removeTag(selectedItem.value.id, tag.tag_id)
    await loadSelectedItemTags()
    playerStore.showToast(`已移除标签: 「${tag.name}」`)
  } catch (err) {
    playerStore.showToast('移除标签失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleTagChanged = async () => {
  await Promise.all([
    loadAllTags(),
    loadSelectedItemTags(),
    mediaStore.loadWorkplaceItems(),
  ])
}

const handleSelectCollection = (colId) => {
  mediaStore.selectedCollectionId = colId
  mediaStore.selectedSupersetId = null
  selectedIds.value = new Set()
  mediaStore.loadWorkplaceItems()
}

const handleSelectSuperset = (supersetId) => {
  mediaStore.selectedSupersetId = supersetId
  mediaStore.selectedCollectionId = null
  selectedIds.value = new Set()
  mediaStore.loadWorkplaceItems()
}

const currentSuperset = computed(() => {
  return mediaStore.supersets.find(s => s.id === mediaStore.selectedSupersetId)
})

const currentCollection = computed(() => {
  return mediaStore.collections.find(c => c.id === mediaStore.selectedCollectionId)
})

const handlePlayCollectionAll = () => {
  if (!displayItems.value.length) return
  const first = displayItems.value[0]
  if (isAudioUnit(first)) {
    playerStore.openAudioModal(first, displayItems.value, true)
  } else if (first.unit_type === 'video' || first.unit_type === 'bundle') {
    playerStore.openVideo(first, displayItems.value, true)
  } else if (first.unit_type === 'image') {
    playerStore.openImage(first, displayItems.value, true)
  }
}

const handleCreateSuperset = async () => {
  if (!newSupersetName.value.trim()) return
  try {
    const created = await createSuperset({ name: newSupersetName.value.trim() })
    playerStore.showToast(`已成功创建虚拟超集「${created.name}」`)
    newSupersetName.value = ''
    showNewSupersetInput.value = false
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast('创建超集失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleAddToSuperset = async (supersetId) => {
  if (!selectedItem.value) return
  try {
    await addItemToSuperset(supersetId, selectedItem.value.id)
    playerStore.showToast(`已成功将「${selectedItem.value.title}」加入超集！`)
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast('添加失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleDeleteSuperset = async (sup, e) => {
  e?.stopPropagation()
  if (!confirm(`确定删除虚拟超集「${sup.name}」吗？\n（物理文件不受任何影响）`)) return
  try {
    await deleteSuperset(sup.id)
    playerStore.showToast(`已删除虚拟超集「${sup.name}」`)
    if (mediaStore.selectedSupersetId === sup.id) {
      mediaStore.selectedSupersetId = null
      await mediaStore.loadWorkplaceItems()
    }
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast('删除超集失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleRemoveFromCurrentSuperset = async (item, e) => {
  e?.stopPropagation()
  if (!mediaStore.selectedSupersetId) return
  try {
    await removeItemFromSuperset(mediaStore.selectedSupersetId, item.id)
    playerStore.showToast(`已从当前超集移出「${item.title}」`)
    await Promise.all([
      mediaStore.loadWorkplaceItems(),
      mediaStore.loadSupersets()
    ])
    if (selectedItem.value?.id === item.id) {
      selectedItem.value = null
    }
  } catch (err) {
    playerStore.showToast('移出失败：' + (err.response?.data?.detail || err.message))
  }
}

// Batch Actions
const toggleBatchMode = () => {
  isBatchMode.value = !isBatchMode.value
  if (!isBatchMode.value) {
    selectedIds.value = new Set()
  }
}

const toggleSelect = (unitId, e) => {
  if (e) e.stopPropagation()
  const s = new Set(selectedIds.value)
  if (s.has(unitId)) {
    s.delete(unitId)
  } else {
    s.add(unitId)
  }
  selectedIds.value = s
}

const isSelected = (unitId) => selectedIds.value.has(unitId)

const selectedUnits = computed(() => {
  return displayItems.value.filter(u => selectedIds.value.has(u.id))
})

const isAllSelected = computed(() => {
  return displayItems.value.length > 0 && selectedIds.value.size === displayItems.value.length
})

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(displayItems.value.map(u => u.id))
  }
}

const handleBatchAddToQueue = () => {
  playerStore.addMultipleToBgQueue(selectedUnits.value)
  selectedIds.value = new Set()
  isBatchMode.value = false
}

const handleBatchPlaySlideshow = () => {
  if (!selectedUnits.value.length) return
  playerStore.openImage(selectedUnits.value[0], selectedUnits.value, true)
}

const openBatchSupersetModal = () => {
  if (!selectedIds.value.size) return
  batchNewSupersetName.value = ''
  if (!mediaStore.supersets.length) {
    mediaStore.loadSupersets()
  }
  showBatchSupersetModal.value = true
}

const handleBatchAddToSuperset = async (superset) => {
  if (!selectedIds.value.size) return
  try {
    const ids = Array.from(selectedIds.value)
    await addItemsBatchToSuperset(superset.id, ids)
    playerStore.showToast(`已将 ${ids.length} 项批量加入超集「${superset.name}」`)
    await mediaStore.loadSupersets()
    showBatchSupersetModal.value = false
    selectedIds.value = new Set()
    isBatchMode.value = false
  } catch (err) {
    playerStore.showToast('批量添加失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleBatchCreateAndAddSuperset = async () => {
  if (!batchNewSupersetName.value.trim() || !selectedIds.value.size) return
  try {
    const newSup = await createSuperset({ name: batchNewSupersetName.value.trim() })
    const ids = Array.from(selectedIds.value)
    await addItemsBatchToSuperset(newSup.id, ids)
    playerStore.showToast(`已创建超集「${newSup.name}」并存入 ${ids.length} 项`)
    batchNewSupersetName.value = ''
    showBatchSupersetModal.value = false
    selectedIds.value = new Set()
    isBatchMode.value = false
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast('创建超集失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleSearch = () => {
  mediaStore.loadWorkplaceItems()
}

const displayItems = computed(() => {
  if (!mediaStore.searchQuery.trim()) return mediaStore.workplaceItems
  const q = mediaStore.searchQuery.trim().toLowerCase()
  return mediaStore.workplaceItems.filter(u =>
    (u.title && u.title.toLowerCase().includes(q)) ||
    (u.collection_name && u.collection_name.toLowerCase().includes(q))
  )
})

const handleItemClick = (item) => {
  if (isBatchMode.value) {
    toggleSelect(item.id)
    return
  }
  selectedItem.value = item
}

const isAudioUnit = (unit) => {
  if (!unit) return false
  if (unit.unit_type === 'audio') return true
  if (unit.unit_type === 'bundle') {
    const prim = unit.files?.find(f => f.role === 'primary') || unit.files?.[0]
    if (prim && ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.ape'].includes(prim.extension?.toLowerCase())) {
      return true
    }
  }
  return false
}

const handleDoubleClick = (item) => {
  if (isBatchMode.value) return
  let seriesPlaylist = []
  if (mediaStore.selectedCollectionId) {
    seriesPlaylist = displayItems.value.filter(u => u.collection_id === mediaStore.selectedCollectionId)
  } else if (item.collection_id) {
    seriesPlaylist = displayItems.value.filter(u => u.collection_id === item.collection_id)
  }
  if (!seriesPlaylist.length) {
    seriesPlaylist = [item]
  }
  seriesPlaylist.sort((a, b) => a.title.localeCompare(b.title, undefined, { numeric: true, sensitivity: 'base' }))

  if (isAudioUnit(item)) {
    playerStore.openAudioModal(item, seriesPlaylist, false) // DEFAULT PAUSED!
  } else if (item.unit_type === 'video' || item.unit_type === 'bundle') {
    playerStore.openVideo(item, seriesPlaylist, false) // DEFAULT PAUSED!
  } else if (item.unit_type === 'image') {
    playerStore.openImage(item, seriesPlaylist, false)
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
              <span>系列目录</span>
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
                @click.stop="mediaStore.openPhysicalOrganizer(col.folder_path)"
                class="p-1.5 text-amber-400 opacity-0 group-hover/col:opacity-100 hover:text-amber-200 transition-opacity"
                title="物理整理与发售时间对齐"
              >
                <FolderCog class="w-3.5 h-3.5" />
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
              <span>虚拟超集</span>
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
            <div
              v-for="sup in mediaStore.supersets"
              :key="sup.id"
              class="group/sup flex items-center justify-between rounded-lg transition-colors text-left"
              :class="[
                mediaStore.selectedSupersetId === sup.id
                  ? 'bg-pink-600/30 text-pink-200 border border-pink-500/30'
                  : 'text-gray-300 hover:bg-white/5'
              ]"
            >
              <button
                @click="handleSelectSuperset(sup.id)"
                class="flex-grow flex items-center justify-between px-2.5 py-1.5 text-xs truncate"
              >
                <span class="truncate flex items-center gap-2">
                  <Tag class="w-3.5 h-3.5 text-pink-400 shrink-0" />
                  <span class="truncate">{{ sup.name }}</span>
                </span>
                <span class="text-[10px] text-gray-500 shrink-0 bg-white/5 px-1.5 py-0.5 rounded-full mr-1">
                  {{ sup.unit_count }}
                </span>
              </button>

              <!-- Quick Play / Slideshow actions on hover -->
              <div class="flex items-center gap-0.5 pr-1 opacity-0 group-hover/sup:opacity-100 transition-opacity">
                <button
                  @click.stop="playerStore.loadSuperset(sup.id, 'bg', true)"
                  class="p-1 text-purple-300 hover:text-white hover:bg-white/10 rounded transition-colors"
                  title="载入并播放此超集 (背景队列)"
                >
                  <Play class="w-3 h-3 fill-current" />
                </button>
                <button
                  @click.stop="playerStore.loadSuperset(sup.id, 'fg', true)"
                  class="p-1 text-pink-300 hover:text-white hover:bg-white/10 rounded transition-colors"
                  title="一键开启全屏自动连播此超集"
                >
                  <Tv class="w-3 h-3" />
                </button>
                <button
                  @click.stop="handleDeleteSuperset(sup, $event)"
                  class="p-1 text-red-400 hover:text-red-200 hover:bg-red-500/20 rounded transition-colors"
                  title="删除此虚拟超集 (不破坏物理文件)"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>
            </div>
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

          <!-- Batch Mode Toggle -->
          <button
            @click="toggleBatchMode"
            :class="[
              'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all shrink-0 border select-none',
              isBatchMode
                ? 'bg-purple-600 text-white border-purple-500 shadow-sm'
                : 'bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10'
            ]"
            :title="isBatchMode ? '退出多选批量模式' : '进入多选批量模式'"
          >
            <CheckSquare class="w-4 h-4" />
            <span>{{ isBatchMode ? '退出多选' : '批量模式' }}</span>
          </button>

          <button
            @click="mediaStore.openAIOrganizer()"
            class="flex items-center gap-1.5 bg-gradient-to-r from-purple-600/30 to-pink-600/30 hover:from-purple-600/40 hover:to-pink-600/40 border border-purple-500/40 text-purple-200 text-xs px-3 py-2 rounded-xl transition-all shrink-0 shadow-sm"
            title="对当前或指定文件夹进行 AI 拓扑分析与重组"
          >
            <Bot class="w-4 h-4 text-purple-400" />
            <span>AI 深度整理</span>
          </button>

          <button
            @click="showPipelineModal = true"
            class="flex items-center gap-1.5 bg-gradient-to-r from-blue-600/30 to-indigo-600/30 hover:from-blue-600/40 hover:to-indigo-600/40 border border-blue-500/40 text-blue-200 text-xs px-3 py-2 rounded-xl transition-all shrink-0 shadow-sm"
            title="可视化多级文件目录投影管线配置与安全演练"
          >
            <FolderCog class="w-4 h-4 text-blue-400" />
            <span>规则流水线</span>
          </button>

          <button
            @click="showTagManagerModal = true"
            class="flex items-center gap-1.5 bg-gradient-to-r from-emerald-600/30 to-teal-600/30 hover:from-emerald-600/40 hover:to-teal-600/40 border border-emerald-500/40 text-emerald-200 text-xs px-3 py-2 rounded-xl transition-all shrink-0 shadow-sm"
            title="面向对象标签知识库：管理类继承关系、拓扑与别名"
          >
            <Tag class="w-4 h-4 text-emerald-400" />
            <span>标签中心</span>
          </button>
        </div>

        <!-- Active Superset Context Banner -->
        <div
          v-if="currentSuperset"
          class="mb-3 px-3.5 py-2.5 rounded-xl bg-pink-500/10 border border-pink-500/30 flex items-center justify-between transition-all"
        >
          <div class="flex items-center gap-2 text-xs text-pink-300 min-w-0 truncate">
            <Sparkles class="w-4 h-4 text-pink-400 shrink-0" />
            <span class="truncate">当前虚拟超集: <strong>{{ currentSuperset.name }}</strong> ({{ displayItems.length }}项)</span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="playerStore.loadSuperset(currentSuperset.id, 'fg', true)"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-pink-600 hover:bg-pink-500 text-white text-[11px] font-medium transition-all active:scale-95 shadow-sm"
              title="一键开启当前超集全屏自动连播"
            >
              <Play class="w-3 h-3 fill-current" />
              <span>全屏连播</span>
            </button>
            <button
              @click="handleSelectSuperset(null)"
              class="text-gray-400 hover:text-white p-1 rounded transition-colors"
              title="返回全部资产视图"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Active Collection Context Banner -->
        <div
          v-if="currentCollection"
          class="mb-3 px-3.5 py-2.5 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-between transition-all"
        >
          <div class="flex items-center gap-3 text-xs text-blue-300 min-w-0 truncate">
            <div class="w-10 h-10 rounded-lg overflow-hidden bg-black/40 border border-blue-400/30 shrink-0">
              <img
                :src="`/api/stream/collection_thumbnail/${currentCollection.id}`"
                class="w-full h-full object-cover"
                @error="(e) => e.target.style.display = 'none'"
              />
            </div>
            <div class="truncate">
              <div class="font-semibold text-white truncate flex items-center gap-2">
                <span>{{ currentCollection.name }}</span>
                <span class="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded font-mono">{{ displayItems.length }} 项</span>
              </div>
              <p class="text-[11px] text-gray-400 truncate mt-0.5" v-if="currentCollection.description">
                {{ currentCollection.description }}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="handlePlayCollectionAll"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-medium transition-all active:scale-95 shadow-sm"
              title="一键播放此专辑/系列全部曲目"
            >
              <Play class="w-3 h-3 fill-current" />
              <span>播放系列</span>
            </button>
            <button
              v-if="currentCollection.folder_path"
              @click="mediaStore.openPhysicalOrganizer(currentCollection.folder_path)"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-200 text-[11px] font-medium transition-all shadow-sm"
              title="为此系列所在目录进行物理重组、规范改名与发售时间戳对齐"
            >
              <FolderCog class="w-3.5 h-3.5 text-amber-400" />
              <span>物理整理</span>
            </button>
            <button
              @click="playerStore.addMultipleToBgQueue(displayItems)"
              class="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-gray-200 text-[11px] font-medium transition-all"
              title="将全部曲目加入背景播放队列"
            >
              <ListPlus class="w-3.5 h-3.5 text-purple-300" />
              <span>入队</span>
            </button>
            <button
              @click="handleSelectCollection(null)"
              class="text-gray-400 hover:text-white p-1 rounded transition-colors"
              title="返回全部资产视图"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Items Table / Grid -->
        <div class="flex-grow overflow-y-auto pr-1 space-y-2">
          <div
            v-if="displayItems.length === 0"
            class="text-center py-16 text-gray-500 text-xs"
          >
            暂无匹配的资产单元
          </div>

          <div
            v-for="item in displayItems"
            :key="item.id"
            @click="handleItemClick(item)"
            @dblclick="handleDoubleClick(item)"
            :class="[
              'p-3 rounded-xl border flex items-center justify-between gap-3 cursor-pointer transition-all select-none',
              isSelected(item.id)
                ? 'bg-purple-600/25 border-purple-500 shadow-md ring-1 ring-purple-500/50 text-white'
                : selectedItem?.id === item.id
                  ? 'bg-purple-600/20 border-purple-500/40 text-purple-100 shadow-md'
                  : 'bg-white/5 hover:bg-white/10 border-white/5 text-gray-300'
            ]"
          >
            <!-- Left Info -->
            <div class="flex items-center gap-3 truncate">
              <!-- Batch Selection Checkbox -->
              <div
                v-if="isBatchMode"
                @click.stop="toggleSelect(item.id, $event)"
                class="w-5 h-5 rounded-lg flex items-center justify-center border transition-all shrink-0 cursor-pointer"
                :class="[
                  isSelected(item.id)
                    ? 'bg-purple-600 text-white border-purple-400 shadow-sm'
                    : 'bg-white/5 border-white/20 hover:border-white/40'
                ]"
              >
                <Check v-if="isSelected(item.id)" class="w-3.5 h-3.5 stroke-[3]" />
              </div>

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

            <!-- Quick Actions: Remove from Superset & Add to Queue -->
            <div class="flex items-center gap-1.5 shrink-0">
              <!-- Remove from Current Superset (if viewing a superset) -->
              <button
                v-if="mediaStore.selectedSupersetId"
                @click.stop="handleRemoveFromCurrentSuperset(item, $event)"
                class="p-1.5 text-gray-400 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
                title="从当前虚拟超集中移出"
              >
                <MinusCircle class="w-4 h-4" />
              </button>

              <button
                @click.stop="playerStore.addToBgQueue(item)"
                class="p-1.5 text-gray-400 hover:text-purple-300 rounded-lg hover:bg-white/10 transition-colors"
                title="加入背景播放队列"
              >
                <ListPlus class="w-4 h-4" />
              </button>
              <div class="text-[11px] text-gray-500 hidden sm:block">
                双击预览
              </div>
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
            <!-- Remove from current superset if in superset view -->
            <button
              v-if="mediaStore.selectedSupersetId"
              @click="handleRemoveFromCurrentSuperset(selectedItem, $event)"
              class="w-full flex items-center justify-center gap-2 bg-red-500/15 hover:bg-red-500/25 text-red-200 text-xs py-2 px-3 rounded-xl border border-red-500/30 transition-colors font-medium"
            >
              <MinusCircle class="w-3.5 h-3.5 text-red-400" />
              <span>从当前超集移出此项</span>
            </button>

            <button
              @click="handleDoubleClick(selectedItem)"
              class="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs py-2.5 px-3 rounded-xl shadow-lg shadow-purple-600/30 transition-all font-medium active:scale-95"
            >
              <Play class="w-3.5 h-3.5 fill-current" />
              <span>在主屏打开播放 (系列选集)</span>
            </button>

            <button
              @click="playerStore.addToBgQueue(selectedItem)"
              class="w-full flex items-center justify-center gap-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-200 text-xs py-2 px-3 rounded-xl border border-purple-500/30 transition-colors"
            >
              <ListPlus class="w-3.5 h-3.5 text-purple-400" />
              <span>加入当前背景播放队列</span>
            </button>
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

          <!-- OOP Tags & Landing Anchors (面向对象标签与物理落点) -->
          <div>
            <div class="flex items-center justify-between text-xs font-semibold text-gray-400 mb-2">
              <span class="flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                <Tag class="w-3.5 h-3.5 text-purple-400" />
                <span>面向对象标签 ({{ selectedItemTags.length }})</span>
              </span>
              <button
                @click="showTagManagerModal = true"
                class="text-[10px] text-purple-400 hover:text-purple-300 transition-colors"
                title="打开标签知识库中心"
              >
                标签中心 →
              </button>
            </div>

            <!-- Tags List -->
            <div class="space-y-1.5 mb-2.5">
              <div
                v-for="t in selectedItemTags"
                :key="t.tag_id"
                class="flex items-center justify-between p-1.5 rounded-lg border text-xs"
                :style="{
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  borderColor: t.is_primary_landing ? 'rgba(168, 85, 247, 0.5)' : 'rgba(255, 255, 255, 0.08)'
                }"
              >
                <!-- Left: Category chip + Name + Hierarchy path -->
                <div class="flex items-center gap-1.5 truncate mr-1">
                  <!-- Category marker -->
                  <span
                    class="text-[9px] px-1 py-0.2 rounded font-mono shrink-0 uppercase"
                    :class="t.class_code === 'workflow' ? 'bg-emerald-500/20 text-emerald-300' :
                           (t.class_code === 'creator' ? 'bg-sky-500/20 text-sky-300' :
                           (t.class_code === 'media_kind' ? 'bg-amber-500/20 text-amber-300' : 'bg-purple-500/20 text-purple-300'))"
                  >
                    {{ t.class_name || t.class_code }}
                  </span>

                  <!-- Hierarchy display path -->
                  <span
                    class="truncate font-medium text-white text-[11px]"
                    :title="t.full_path || t.name"
                  >
                    {{ t.display_path || t.name }}
                  </span>
                </div>

                <!-- Right: Anchor indicator & Remove -->
                <div class="flex items-center gap-1 shrink-0">
                  <!-- Landing anchor toggle -->
                  <button
                    @click="handleTogglePrimaryLanding(t)"
                    :class="[
                      'p-1 rounded transition-colors text-[10px] flex items-center gap-0.5',
                      t.is_primary_landing
                        ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40 font-semibold'
                        : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                    ]"
                    :title="t.is_primary_landing ? '当前为该类物理落点锚点（点击取消）' : '设为物理落点锚点（用于文件规范整理）'"
                  >
                    <Anchor class="w-3 h-3" />
                    <span v-if="t.is_primary_landing" class="text-[9px]">落点</span>
                  </button>

                  <!-- Remove tag button -->
                  <button
                    @click="handleRemoveTag(t)"
                    class="p-1 rounded text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="移除此标签"
                  >
                    <X class="w-3 h-3" />
                  </button>
                </div>
              </div>

              <div v-if="selectedItemTags.length === 0" class="text-[11px] text-gray-500 italic py-1">
                暂未打标，点击下方快速添加
              </div>
            </div>

            <!-- Quick Add Tag Input with suggestions -->
            <div class="relative">
              <div v-if="!isAddingTag">
                <button
                  @click="openAddTagInput"
                  class="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-xl border border-dashed border-white/15 hover:border-purple-500/40 bg-white/5 hover:bg-white/10 text-xs text-gray-300 hover:text-white transition-all"
                >
                  <Plus class="w-3 h-3 text-purple-400" />
                  <span>为该作品添加标签...</span>
                </button>
              </div>

              <div v-else class="space-y-1.5 bg-black/40 border border-purple-500/30 p-2 rounded-xl">
                <div class="flex items-center gap-1.5">
                  <input
                    ref="tagInputRef"
                    v-model="tagSearchQuery"
                    type="text"
                    placeholder="输入或选择标签 (如 标签名、分类)..."
                    class="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    @keyup.enter="handleCreateAndAssignTag"
                  />
                  <button
                    @click="isAddingTag = false"
                    class="text-gray-400 hover:text-white p-1"
                  >
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>

                <!-- Suggestions list -->
                <div v-if="availableTagSuggestions.length > 0" class="max-h-36 overflow-y-auto space-y-1 pr-1">
                  <button
                    v-for="sug in availableTagSuggestions"
                    :key="sug.id"
                    @click="handleAssignTag(sug)"
                    class="w-full flex items-center justify-between p-1.5 rounded-lg bg-white/5 hover:bg-purple-600/20 text-left text-xs transition-colors"
                  >
                    <span class="truncate text-gray-200" :title="sug.full_path">{{ sug.display_path || sug.name }}</span>
                    <span class="text-[9px] text-gray-500 font-mono shrink-0 ml-1">{{ sug.class_name }}</span>
                  </button>
                </div>

                <div v-else-if="tagSearchQuery.trim()" class="p-1">
                  <button
                    @click="handleCreateAndAssignTag"
                    class="w-full text-center py-1 text-xs text-purple-300 bg-purple-500/10 hover:bg-purple-500/20 rounded-lg transition-colors"
                  >
                    + 新建并打上标签「{{ tagSearchQuery.trim() }}」
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

    <!-- Bottom Floating Batch Dock in Workplace -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="transform translate-y-8 opacity-0"
      enter-to-class="transform translate-y-0 opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="transform translate-y-0 opacity-100"
      leave-to-class="transform translate-y-8 opacity-0"
    >
      <div
        v-if="isBatchMode && selectedIds.size > 0"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-gray-950/90 backdrop-blur-xl border border-purple-500/40 rounded-2xl px-5 py-3 shadow-2xl flex items-center gap-3 sm:gap-4 max-w-[95vw] overflow-x-auto text-xs"
      >
        <!-- Selection Count & Select All -->
        <div class="flex items-center gap-2 pr-3 border-r border-white/10 shrink-0">
          <span class="font-semibold text-white">已选择 <span class="text-purple-400 font-mono">{{ selectedIds.size }}</span> 项</span>
          <button
            @click="toggleSelectAll"
            class="px-2 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-gray-200 hover:text-white transition-colors text-[11px]"
          >
            {{ isAllSelected ? '取消全选' : '全选' }}
          </button>
        </div>

        <!-- Batch Actions -->
        <div class="flex items-center gap-2 shrink-0">
          <!-- Add to Superset -->
          <button
            @click="openBatchSupersetModal"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-pink-600 hover:bg-pink-500 text-white font-medium shadow-md shadow-pink-600/30 transition-all active:scale-95"
            title="批量加入或创建超集"
          >
            <BookmarkPlus class="w-3.5 h-3.5" />
            <span>加入超集</span>
          </button>

          <!-- Add to Background Queue -->
          <button
            @click="handleBatchAddToQueue"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium shadow-md shadow-purple-600/30 transition-all active:scale-95"
            title="批量加入背景播放队列"
          >
            <ListPlus class="w-3.5 h-3.5" />
            <span>加入播放队列</span>
          </button>

          <!-- Batch Continuous Slideshow -->
          <button
            @click="handleBatchPlaySlideshow"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-md shadow-indigo-600/30 transition-all active:scale-95"
            title="立即连播所选项"
          >
            <Play class="w-3.5 h-3.5 fill-current" />
            <span>连播已选项</span>
          </button>

          <!-- Exit / Cancel -->
          <button
            @click="selectedIds = new Set(); isBatchMode = false"
            class="p-1.5 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-colors ml-1"
            title="取消多选"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>
    </Transition>

    <!-- Batch Add to Superset Dialog Modal in Workplace -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="showBatchSupersetModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
        @click.self="showBatchSupersetModal = false"
      >
        <div
          class="w-full max-w-md bg-gray-900 border border-pink-500/30 rounded-2xl p-5 shadow-2xl text-left"
          style="background-color: var(--bg-surface-elevated);"
        >
          <div class="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
            <h3 class="text-sm font-semibold text-white flex items-center gap-2">
              <BookmarkPlus class="w-4 h-4 text-pink-400" />
              <span>批量收纳至超集 (共 {{ selectedIds.size }} 项)</span>
            </h3>
            <button
              @click="showBatchSupersetModal = false"
              class="text-gray-400 hover:text-white p-1 rounded-lg"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Existing Supersets List -->
          <div class="mb-4">
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-2">
              选择已有超集
            </label>
            <div v-if="mediaStore.supersets.length > 0" class="max-h-48 overflow-y-auto space-y-1.5 pr-1">
              <button
                v-for="sup in mediaStore.supersets"
                :key="sup.id"
                @click="handleBatchAddToSuperset(sup)"
                class="w-full flex items-center justify-between p-2.5 rounded-xl bg-white/5 hover:bg-pink-600/20 hover:border-pink-500/30 border border-transparent text-gray-200 hover:text-pink-200 transition-all text-xs font-medium"
              >
                <span>{{ sup.name }}</span>
                <span class="text-[11px] text-gray-500 font-mono">{{ sup.unit_count }} 项</span>
              </button>
            </div>
            <div v-else class="text-xs text-gray-400 py-2">
              目前还没有创建任何超集，请在下方直接新建：
            </div>
          </div>

          <!-- Create New Superset and Batch Add -->
          <div class="pt-3 border-t border-white/10">
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-2">
              新建超集并存入
            </label>
            <div class="flex items-center gap-2">
              <input
                v-model="batchNewSupersetName"
                type="text"
                placeholder="输入新超集名称 (例如: 精选二次元插画)..."
                class="flex-grow bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
                @keyup.enter="handleBatchCreateAndAddSuperset"
              />
              <button
                @click="handleBatchCreateAndAddSuperset"
                class="bg-pink-600 hover:bg-pink-500 text-white text-xs font-medium px-4 py-2 rounded-xl transition-all shrink-0"
              >
                新建并存入
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Pipeline Builder Modal -->
    <PipelineBuilderModal
      :isOpen="showPipelineModal"
      @close="showPipelineModal = false"
      @executed="mediaStore.loadWorkplaceItems()"
    />

    <!-- Tag Taxonomy Manager Modal -->
    <TagManagerModal
      :isOpen="showTagManagerModal"
      @close="showTagManagerModal = false"
      @changed="handleTagChanged"
    />
  </div>
</template>
