<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
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
  LayoutGrid,
  FolderOpen,
  ExternalLink,
  Clock,
  Sparkles,
  SearchX,
  ChevronDown,
  ChevronUp,
  Check,
  Compass,
  ListPlus,
  BookmarkPlus,
  CheckSquare,
  Square,
  CheckCheck,
  Plus,
  X,
  Filter,
  RotateCcw,
  Globe,
  Tag as TagIcon,
  User
} from 'lucide-vue-next'
import {
  revealInExplorer,
  openWithDefaultApp,
  createSuperset,
  addItemToSuperset,
  addItemsBatchToSuperset,
  fetchAssets
} from '../api'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const categories = [
  { id: 'all', name: '全部', icon: LayoutGrid },
  { id: 'image', name: '图片', icon: ImageIcon },
  { id: 'video', name: '视频', icon: Video },
  { id: 'audio', name: '音乐', icon: Music },
]

const algoMeta = {
  discover: {
    icon: Compass,
    color: '#38bdf8',
    desc: '全库随机漫游，探索未被注意的角落',
  },
  affinity: {
    icon: Sparkles,
    color: '#c084fc',
    desc: '根据评分、收藏与有效停留时长个性化加权',
  },
  flashback: {
    icon: Clock,
    color: '#fbbf24',
    desc: '优先重温往日索引、久未浏览的珍贵记忆',
  },
}

const isAlgoDropdownOpen = ref(false)
const algoDropdownRef = ref(null)

// Batch Selection Mode
const isBatchMode = ref(false)
const selectedIds = ref(new Set())
const showBatchSupersetModal = ref(false)
const batchNewSupersetName = ref('')

// Single Card Quick Superset
const activePopoverUnit = ref(null)
const cardNewSupersetName = ref('')

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

// Single Card Quick Superset
const openQuickSuperset = (e, unit) => {
  e.stopPropagation()
  activePopoverUnit.value = unit
  cardNewSupersetName.value = ''
  if (!mediaStore.supersets.length) {
    mediaStore.loadSupersets()
  }
}

const handleCardAddToSuperset = async (superset) => {
  if (!activePopoverUnit.value) return
  try {
    await addItemToSuperset(superset.id, activePopoverUnit.value.id)
    playerStore.showToast(`已将「${activePopoverUnit.value.title}」加入超集「${superset.name}」`)
    await mediaStore.loadSupersets()
    activePopoverUnit.value = null
  } catch (err) {
    playerStore.showToast('加入超集失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleCardCreateAndAddSuperset = async () => {
  if (!cardNewSupersetName.value.trim() || !activePopoverUnit.value) return
  try {
    const newSup = await createSuperset({ name: cardNewSupersetName.value.trim() })
    await addItemToSuperset(newSup.id, activePopoverUnit.value.id)
    playerStore.showToast(`已创建超集「${newSup.name}」并成功加入`)
    cardNewSupersetName.value = ''
    activePopoverUnit.value = null
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast('创建超集失败：' + (err.response?.data?.detail || err.message))
  }
}

// Batch Actions
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

const currentAlgo = computed(() => {
  return mediaStore.algorithms.find(a => a.name === mediaStore.selectedAlgorithm) || {
    name: 'discover',
    display_name: '探索漫游'
  }
})

const handleCategoryChange = (catId) => {
  mediaStore.activeCategory = catId
  mediaStore.loadFeed()
}

const selectAlgorithm = (algoName) => {
  mediaStore.selectedAlgorithm = algoName
  mediaStore.loadFeed()
  isAlgoDropdownOpen.value = false
}

const handleClickOutside = (e) => {
  if (algoDropdownRef.value && !algoDropdownRef.value.contains(e.target)) {
    isAlgoDropdownOpen.value = false
  }
  if (activePopoverUnit.value && !e.target.closest('.quick-superset-container')) {
    activePopoverUnit.value = null
  }
}

const handleScroll = () => {
  if (mediaStore.feedDisplayMode !== 'flat' || !mediaStore.hasMoreFeed || mediaStore.loadingMore) return
  const scrollY = window.scrollY || document.documentElement.scrollTop
  const windowHeight = window.innerHeight
  const docHeight = document.documentElement.scrollHeight
  if (scrollY + windowHeight >= docHeight - 400) {
    mediaStore.loadMoreFeed()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('scroll', handleScroll)
})

const matchesFacet = (item, category, value) => {
  if (!item) return false
  const valLower = (value || '').toLowerCase()

  // 1. Direct structured tags match from backend API
  if (item.tags && Array.isArray(item.tags)) {
    const found = item.tags.some(t => {
      if (t.name === value) return true
      if (t.class_code === category && t.name.toLowerCase() === valLower) return true
      // Support OOP inheritance chain cascade!
      if (t.full_path && t.full_path.toLowerCase().includes(valLower)) return true
      return false
    })
    if (found) return true
  }

  if (item.tag_names && Array.isArray(item.tag_names)) {
    if (item.tag_names.includes(value)) return true
  }

  // 2. Resilient semantic fallback matching
  const title = (item.title || '').toLowerCase()
  const colName = (item.collection_name || '').toLowerCase()
  const fullText = `${title} ${colName}`
  return fullText.includes(valLower)
}

const displayItems = computed(() => {
  let items = mediaStore.feedItems

  // 1. Search Query filter
  if (mediaStore.searchQuery.trim()) {
    const q = mediaStore.searchQuery.trim().toLowerCase()
    items = items.filter(u =>
      (u.title && u.title.toLowerCase().includes(q)) ||
      (u.collection_name && u.collection_name.toLowerCase().includes(q))
    )
  }

  // 2. Multi-facet Progressive Filter: Cross-row is AND, Within-row is OR
  const facets = mediaStore.activeFacetFilters
  const activeCategories = Object.keys(facets).filter(k => facets[k] && facets[k].length > 0)

  if (activeCategories.length > 0) {
    items = items.filter(item => {
      return activeCategories.every(cat => {
        const selectedValues = facets[cat]
        return selectedValues.some(val => matchesFacet(item, cat, val))
      })
    })
  }

  return items
})

const availableFacets = computed(() => {
  const facetMap = new Map()

  // 动态从当前流项目的所有结构化标签中聚合分类与选项 (零硬编码)
  for (const item of mediaStore.feedItems) {
    if (item.tags && Array.isArray(item.tags)) {
      for (const t of item.tags) {
        if (!t.name || t.name.length > 30) continue
        const code = t.class_code || 'domain'
        const displayName = t.class_name || (code === 'creator' ? '创作者 / 社团' : code === 'workflow' ? '整理状态' : '题材流派')
        const iconComp = code === 'creator' ? User : code === 'workflow' ? Globe : Sparkles

        if (!facetMap.has(code)) {
          facetMap.set(code, {
            key: code,
            name: displayName,
            icon: iconComp,
            options: new Set()
          })
        }
        facetMap.get(code).options.add(t.name)
      }
    }
  }

  const result = []
  for (const facet of facetMap.values()) {
    if (facet.options.size > 0) {
      result.push({
        key: facet.key,
        name: facet.name,
        icon: facet.icon,
        options: Array.from(facet.options).sort()
      })
    }
  }

  return result
})

const getFacetMatchCount = (category, value) => {
  return mediaStore.feedItems.filter(item => matchesFacet(item, category, value)).length
}

const activeFilterList = computed(() => {
  const list = []
  for (const [cat, vals] of Object.entries(mediaStore.activeFacetFilters)) {
    if (vals && vals.length > 0) {
      const catConfig = availableFacets.value.find(f => f.key === cat)
      const catName = catConfig ? catConfig.name : cat
      for (const val of vals) {
        list.push({ category: cat, categoryName: catName, value: val })
      }
    }
  }
  return list
})

const formatDuration = (seconds) => {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
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

const seriesDisplayItems = computed(() => {
  return displayItems.value
})

const handleCardClick = async (card) => {
  if (isBatchMode.value) {
    toggleSelect(card.id)
    return
  }

  if (card.is_series && card.collection_id) {
    try {
      const fullSeries = await fetchAssets({ collection_id: card.collection_id, limit: 300 })
      if (fullSeries && fullSeries.length > 0) {
        const firstItem = fullSeries[0]
        if (isAudioUnit(firstItem)) {
          playerStore.openAudioModal(firstItem, fullSeries, false) // DEFAULT PAUSED!
        } else if (firstItem.unit_type === 'video' || firstItem.unit_type === 'bundle') {
          playerStore.openVideo(firstItem, fullSeries, false)
        } else if (firstItem.unit_type === 'image') {
          playerStore.openImage(firstItem, fullSeries, false)
        }
        return
      }
    } catch (e) {
      console.warn('Failed to load full series playlist, playing card directly', e)
    }
  }

  if (isAudioUnit(card)) {
    playerStore.openAudioModal(card, [card], false)
  } else if (card.unit_type === 'video' || card.unit_type === 'bundle') {
    playerStore.openVideo(card, [card], false)
  } else if (card.unit_type === 'image') {
    playerStore.openImage(card, [card], false)
  }
}

const handleAddSeriesToQueue = async (card) => {
  if (card.is_series && card.collection_id) {
    try {
      const full = await fetchAssets({ collection_id: card.collection_id, limit: 300 })
      if (full && full.length > 0) {
        playerStore.addMultipleToBgQueue(full)
        playerStore.showToast(`已将系列「${card.title}」共 ${full.length} 项加入队列`)
        return
      }
    } catch (e) {}
  }
  playerStore.addToBgQueue(card)
}

const startSlideshowAll = () => {
  if (!displayItems.value.length) return
  playerStore.openImage(displayItems.value[0], displayItems.value, true)
}

const handleReveal = async (e, card) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  try {
    await revealInExplorer({ unit_id: targetId })
  } catch (err) {
    playerStore.showToast('无法在资源管理器中定位：' + (err.response?.data?.detail || err.message))
  }
}

const handleOpenExternal = async (e, card) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  try {
    await openWithDefaultApp({ unit_id: targetId })
  } catch (err) {
    playerStore.showToast('无法用外部程序打开：' + (err.response?.data?.detail || err.message))
  }
}

const handleRate = (e, card, stars) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  const newRating = card.rating === stars ? 0 : stars
  mediaStore.updateRating(targetId, newRating)
  card.rating = newRating
}

const handleToggleFavorite = (e, card) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  mediaStore.toggleFavorite(targetId)
  card.is_favorite = !card.is_favorite
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 lg:px-8 py-5">
    <!-- Stream Toolbar: Category Filters & Custom Algorithm Popover -->
    <div class="flex items-center justify-between gap-4 mb-5 pb-1">
      <!-- Category Pills & Slideshow Trigger -->
      <div class="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
        <button
          v-for="cat in categories"
          :key="cat.id"
          @click="handleCategoryChange(cat.id)"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all shrink-0 select-none border',
            mediaStore.activeCategory === cat.id
              ? 'shadow-sm text-white'
              : 'bg-white/5 border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10'
          ]"
          :style="mediaStore.activeCategory === cat.id ? { backgroundColor: 'var(--accent-color)', borderColor: 'var(--accent-border)' } : {}"
          :title="cat.name"
        >
          <component :is="cat.icon" class="w-3.5 h-3.5" />
          <span>{{ cat.name }}</span>
        </button>

        <!-- Slideshow Autoplay Trigger Button -->
        <button
          v-if="displayItems.length > 0"
          @click="startSlideshowAll"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-purple-200 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 shadow-sm transition-all shrink-0 ml-1 active:scale-95"
          title="一键开启当前列表全屏自动连播 (图片每15秒切换，视频播完下切)"
        >
          <Play class="w-3.5 h-3.5 fill-current text-purple-300" />
          <span>连播</span>
        </button>

        <!-- Batch Selection Mode Toggle -->
        <button
          v-if="displayItems.length > 0"
          @click="toggleBatchMode"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all shrink-0 ml-1 border select-none',
            isBatchMode
              ? 'bg-purple-600 text-white border-purple-500 shadow-sm'
              : 'bg-white/5 border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10'
          ]"
          :title="isBatchMode ? '退出多选批量模式' : '进入多选批量模式 (批量加入超集/队列)'"
        >
          <CheckSquare class="w-3.5 h-3.5" />
          <span>{{ isBatchMode ? '退出多选' : '批量模式' }}</span>
        </button>

        <!-- View Mode Toggle: Series Aggregation vs Flat Episodes -->
        <button
          @click="mediaStore.setFeedDisplayMode(mediaStore.feedDisplayMode === 'series' ? 'flat' : 'series')"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all shrink-0 ml-1 border select-none',
            mediaStore.feedDisplayMode === 'series'
              ? 'bg-purple-600/20 text-purple-200 border-purple-500/40 shadow-sm'
              : 'bg-white/5 border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10'
          ]"
          :title="mediaStore.feedDisplayMode === 'series' ? '当前：系列聚合视图 (点击切换为分集平铺)' : '当前：分集平铺视图 (点击切换为系列聚合)'"
        >
          <Layers class="w-3.5 h-3.5 text-purple-400" />
          <span>{{ mediaStore.feedDisplayMode === 'series' ? '系列聚合' : '分集平铺' }}</span>
        </button>
      </div>

      <!-- Custom Aesthetic Recommendation Algorithm Popover -->
      <div ref="algoDropdownRef" class="relative shrink-0">
        <!-- Trigger Button -->
        <button
          @click.stop="isAlgoDropdownOpen = !isAlgoDropdownOpen"
          :class="[
            'flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium transition-all select-none border',
            isAlgoDropdownOpen
              ? 'bg-white/10 text-white shadow-md'
              : 'bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10 hover:border-white/20'
          ]"
          :style="isAlgoDropdownOpen ? { borderColor: 'var(--accent-border)' } : {}"
          title="切换推荐算法策略"
        >
          <component
            :is="algoMeta[mediaStore.selectedAlgorithm]?.icon || Sparkles"
            class="w-3.5 h-3.5 transition-transform"
            :style="{ color: algoMeta[mediaStore.selectedAlgorithm]?.color || 'var(--accent-color)' }"
          />
          <span class="font-medium tracking-wide">{{ currentAlgo.display_name }}</span>
          <ChevronDown
            class="w-3.5 h-3.5 text-gray-400 transition-transform duration-200"
            :class="{ 'rotate-180': isAlgoDropdownOpen }"
          />
        </button>

        <!-- Floating Popover Menu -->
        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="transform scale-95 opacity-0 -translate-y-1"
          enter-to-class="transform scale-100 opacity-100 translate-y-0"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="transform scale-100 opacity-100 translate-y-0"
          leave-to-class="transform scale-95 opacity-0 -translate-y-1"
        >
          <div
            v-if="isAlgoDropdownOpen"
            class="absolute right-0 top-full mt-2 w-72 rounded-2xl p-1.5 shadow-2xl backdrop-blur-xl border border-white/10 z-40 overflow-hidden"
            style="background-color: var(--bg-surface-elevated);"
          >
            <div class="px-2.5 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider border-b border-white/5 mb-1">
              推荐算法分流策略
            </div>

            <div class="space-y-1">
              <div
                v-for="algo in mediaStore.algorithms"
                :key="algo.name"
                @click="selectAlgorithm(algo.name)"
                :class="[
                  'group flex items-start gap-2.5 p-2 rounded-xl cursor-pointer transition-all border',
                  mediaStore.selectedAlgorithm === algo.name
                    ? 'bg-white/10 border-white/15 text-white shadow-sm'
                    : 'border-transparent text-gray-300 hover:text-white hover:bg-white/5'
                ]"
              >
                <!-- Icon badge -->
                <div
                  class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                  :style="{ backgroundColor: 'rgba(255, 255, 255, 0.06)' }"
                >
                  <component
                    :is="algoMeta[algo.name]?.icon || Sparkles"
                    class="w-4 h-4"
                    :style="{ color: algoMeta[algo.name]?.color || 'var(--accent-color)' }"
                  />
                </div>

                <!-- Text info -->
                <div class="flex-grow min-w-0">
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold tracking-wide">
                      {{ algo.display_name }}
                    </span>
                    <Check
                      v-if="mediaStore.selectedAlgorithm === algo.name"
                      class="w-3.5 h-3.5 shrink-0"
                      :style="{ color: 'var(--accent-color)' }"
                    />
                  </div>
                  <p class="text-[11px] text-gray-400 mt-0.5 leading-snug">
                    {{ algoMeta[algo.name]?.desc || algo.description }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Multi-facet Progressive Filter Tray (多维标签筛选抽屉) -->
    <div
      v-if="mediaStore.feedItems.length > 0"
      class="mb-5 rounded-2xl border transition-all overflow-hidden"
      style="background-color: var(--bg-surface); border-color: var(--border-color);"
    >
      <!-- Tray Header Bar -->
      <div class="px-4 py-2.5 flex items-center justify-between border-b" style="border-color: var(--border-color);">
        <div class="flex items-center gap-2.5">
          <div class="p-1 rounded-lg text-purple-400 bg-purple-500/10">
            <Filter class="w-3.5 h-3.5" />
          </div>
          <span class="text-xs font-semibold tracking-wide" style="color: var(--text-main);">
            多维标签筛选
          </span>
          <span
            v-if="activeFilterList.length > 0"
            class="text-[10px] px-2 py-0.5 rounded-full font-bold text-white shadow-xs"
            style="background: var(--accent-color);"
          >
            {{ activeFilterList.length }} 项生效
          </span>
          <span class="text-[11px] text-gray-500 hidden sm:inline">
            (行内 OR 并集 / 跨行 AND 交集)
          </span>
        </div>

        <div class="flex items-center gap-3">
          <!-- Filter result count indicator -->
          <div class="text-[11px] text-gray-400">
            找到 <span class="font-semibold text-white font-mono">{{ displayItems.length }}</span> 项结果
          </div>

          <!-- One-click Clear All -->
          <button
            v-if="mediaStore.hasAnyActiveFacet()"
            @click="mediaStore.clearFacetFilters()"
            class="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
            title="清空所有维度的标签筛选"
          >
            <RotateCcw class="w-3 h-3" />
            <span>清空筛选</span>
          </button>

          <!-- Expand / Collapse Tray Button -->
          <button
            @click="mediaStore.facetTrayOpen = !mediaStore.facetTrayOpen"
            class="flex items-center gap-1 text-[11px] text-gray-400 hover:text-white p-1 rounded-lg transition-colors"
            :title="mediaStore.facetTrayOpen ? '收起筛选面板' : '展开多维筛选面板'"
          >
            <span>{{ mediaStore.facetTrayOpen ? '收起' : '展开' }}</span>
            <component :is="mediaStore.facetTrayOpen ? ChevronUp : ChevronDown" class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Active Filters Ribbon (Quick Remove Pills) -->
      <div
        v-if="activeFilterList.length > 0"
        class="px-4 py-2 border-b flex flex-wrap items-center gap-2"
        style="background: rgba(255, 255, 255, 0.02); border-color: var(--border-color);"
      >
        <span class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">当前生效:</span>
        <div
          v-for="flt in activeFilterList"
          :key="`${flt.category}-${flt.value}`"
          class="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium text-white shadow-xs"
          style="background: var(--accent-color);"
        >
          <span class="text-[10px] opacity-80 mr-0.5">[{{ flt.categoryName }}]</span>
          <span>{{ flt.value }}</span>
          <button
            @click="mediaStore.toggleFacetFilter(flt.category, flt.value)"
            class="hover:bg-black/20 rounded-full p-0.5 ml-1 transition-colors"
            title="移除此筛选"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>

      <!-- Expandable Multi-row Facets Matrix -->
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="max-h-0 opacity-0 py-0"
        enter-to-class="max-h-96 opacity-100 py-3"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="max-h-96 opacity-100 py-3"
        leave-to-class="max-h-0 opacity-0 py-0"
      >
        <div v-show="mediaStore.facetTrayOpen" class="px-4 py-3 space-y-3">
          <div
            v-for="group in availableFacets"
            :key="group.key"
            class="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3"
          >
            <!-- Facet Label -->
            <div class="flex items-center gap-1.5 w-28 shrink-0 text-gray-400 text-xs font-medium">
              <component :is="group.icon || TagIcon" class="w-3.5 h-3.5 text-purple-400/80" />
              <span>{{ group.name }}</span>
            </div>

            <!-- Facet Option Chips -->
            <div class="flex flex-wrap items-center gap-1.5 flex-grow">
              <button
                v-for="opt in group.options"
                :key="opt"
                @click="mediaStore.toggleFacetFilter(group.key, opt)"
                :class="[
                  'px-2.5 py-1 rounded-lg text-xs font-medium transition-all select-none border flex items-center gap-1.5',
                  mediaStore.isFacetActive(group.key, opt)
                    ? 'text-white shadow-xs'
                    : 'bg-white/5 border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10'
                ]"
                :style="mediaStore.isFacetActive(group.key, opt) ? { backgroundColor: 'var(--accent-color)', borderColor: 'var(--accent-border)' } : {}"
              >
                <span>{{ opt }}</span>
                <span
                  class="text-[10px] px-1 py-0.2 rounded-full font-mono transition-opacity"
                  :class="mediaStore.isFacetActive(group.key, opt) ? 'bg-white/20 text-white' : 'bg-white/5 text-gray-500'"
                >
                  {{ getFacetMatchCount(group.key, opt) }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </div>

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

    <!-- Search Empty State -->
    <div
      v-else-if="displayItems.length === 0 && mediaStore.searchQuery"
      class="flex flex-col items-center justify-center py-20 text-center"
    >
      <div class="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4 text-gray-400">
        <SearchX class="w-8 h-8" />
      </div>
      <h3 class="text-base font-medium text-white mb-1.5">未找到匹配结果</h3>
      <p class="text-xs text-gray-400 mb-4">
        没有找到包含「{{ mediaStore.searchQuery }}」的媒体文件或系列
      </p>
      <button
        @click="mediaStore.searchQuery = ''"
        class="text-xs bg-white/10 hover:bg-white/20 text-gray-300 px-3.5 py-1.5 rounded-lg transition-colors"
      >
        清除搜索关键词
      </button>
    </div>

    <!-- Facet Filter Empty State -->
    <div
      v-else-if="displayItems.length === 0 && mediaStore.hasAnyActiveFacet()"
      class="flex flex-col items-center justify-center py-20 text-center"
    >
      <div class="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4 text-purple-400">
        <Filter class="w-8 h-8" />
      </div>
      <h3 class="text-base font-medium text-white mb-1.5">当前筛选组合下暂无内容</h3>
      <p class="text-xs text-gray-400 mb-4">
        已应用的多维标签组合较严格，可尝试取消部分标签以扩大探索范围
      </p>
      <button
        @click="mediaStore.clearFacetFilters()"
        class="text-xs bg-purple-600 hover:bg-purple-500 text-white px-3.5 py-1.5 rounded-lg transition-colors font-medium shadow-sm"
      >
        清空标签筛选
      </button>
    </div>

    <!-- Feed Grid / Waterfall -->
    <div
      v-else
      class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5"
    >
      <div
        v-for="card in seriesDisplayItems"
        :key="card.card_id || card.id"
        @click="handleCardClick(card)"
        class="group relative border rounded-2xl overflow-hidden shadow-lg transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl cursor-pointer flex flex-col"
        :class="[
          isSelected(card.id)
            ? 'ring-2 ring-purple-500 border-purple-500/60 shadow-purple-900/30'
            : ''
        ]"
        style="background-color: var(--bg-card); border-color: var(--border-color);"
      >
        <!-- Batch Select Overlay Checkbox -->
        <div
          v-if="isBatchMode"
          @click.stop="toggleSelect(card.id)"
          class="absolute top-2.5 left-2.5 z-30 flex items-center justify-center w-7 h-7 rounded-xl transition-all shadow-md cursor-pointer select-none"
          :class="[
            isSelected(card.id)
              ? 'bg-purple-600 text-white border border-purple-400'
              : 'bg-black/60 text-white/70 border border-white/20 hover:border-white/40'
          ]"
        >
          <Check v-if="isSelected(card.id)" class="w-4 h-4 stroke-[3]" />
          <div v-else class="w-3 h-3 rounded-sm border border-white/40" />
        </div>

        <!-- Quick Superset Inline Popover -->
        <div
          v-if="activePopoverUnit?.id === (card.representative_unit_id || card.id)"
          @click.stop
          class="quick-superset-container absolute inset-x-2 top-2 z-40 bg-gray-950/95 backdrop-blur-xl border border-pink-500/40 rounded-xl p-3 shadow-2xl flex flex-col gap-2.5 text-left text-xs"
        >
          <div class="flex items-center justify-between border-b border-white/10 pb-1.5">
            <span class="font-semibold text-pink-300 flex items-center gap-1.5">
              <BookmarkPlus class="w-3.5 h-3.5" />
              <span>收纳至超集</span>
            </span>
            <button
              @click.stop="activePopoverUnit = null"
              class="text-gray-400 hover:text-white p-0.5 rounded transition-colors"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Existing supersets list -->
          <div v-if="mediaStore.supersets.length > 0" class="max-h-36 overflow-y-auto space-y-1 pr-1">
            <button
              v-for="sup in mediaStore.supersets"
              :key="sup.id"
              @click.stop="handleCardAddToSuperset(sup)"
              class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-pink-600/20 hover:border-pink-500/30 border border-transparent text-gray-300 hover:text-pink-200 transition-colors text-left"
            >
              <span class="truncate font-medium">{{ sup.name }}</span>
              <span class="text-[10px] text-gray-500 font-mono">{{ sup.unit_count }}项</span>
            </button>
          </div>
          <div v-else class="text-[11px] text-gray-400 py-1">
            暂无超集，输入名称即可创建新超集：
          </div>

          <!-- Quick Create New Superset -->
          <div class="flex items-center gap-1.5 pt-1 border-t border-white/10">
            <input
              v-model="cardNewSupersetName"
              type="text"
              placeholder="新建超集名称..."
              class="flex-grow bg-white/10 border border-white/10 rounded-lg px-2 py-1 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-400"
              @keyup.enter="handleCardCreateAndAddSuperset"
            />
            <button
              @click.stop="handleCardCreateAndAddSuperset"
              class="bg-pink-600 hover:bg-pink-500 text-white text-xs px-2.5 py-1 rounded-lg shrink-0 font-medium transition-colors"
            >
              存入
            </button>
          </div>
        </div>

        <!-- Media Thumbnail Container -->
        <div class="relative w-full aspect-[4/3] bg-black/40 overflow-hidden flex items-center justify-center">
          <!-- Fallback icon / artwork strictly behind the image (z-0), visible only if image fails or is missing -->
          <div
            class="absolute inset-0 flex items-center justify-center pointer-events-none z-0"
            :class="[
              card.unit_type === 'audio'
                ? 'bg-gradient-to-br from-purple-950/70 via-slate-900 to-indigo-950/80'
                : 'bg-black/40'
            ]"
          >
            <!-- Stylized vinyl rings for audio fallback -->
            <div v-if="card.unit_type === 'audio'" class="relative flex items-center justify-center">
              <div class="w-28 h-28 rounded-full border border-purple-500/20 flex items-center justify-center">
                <div class="w-20 h-20 rounded-full border border-purple-400/20 flex items-center justify-center">
                  <div class="w-12 h-12 rounded-full bg-purple-600/30 border border-purple-400/40 flex items-center justify-center shadow-lg">
                    <Music class="w-6 h-6 text-purple-200" />
                  </div>
                </div>
              </div>
            </div>
            <component
              v-else
              :is="card.unit_type === 'video' || card.unit_type === 'bundle' ? Video : ImageIcon"
              class="w-10 h-10 text-white/10"
            />
          </div>

          <img
            :src="card.is_series && card.collection_id ? `/api/stream/collection_thumbnail/${card.collection_id}` : `/api/stream/thumbnail/${card.representative_unit_id || card.id}`"
            :alt="card.title"
            loading="lazy"
            class="relative z-10 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            @error="(e) => e.target.style.display = 'none'"
          />

          <!-- Play overlay on hover -->
          <div
            v-if="card.unit_type !== 'image' && !isBatchMode"
            class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-20 pointer-events-none"
          >
            <div
              class="w-11 h-11 rounded-full text-white flex items-center justify-center shadow-lg transform group-hover:scale-105 transition-transform"
              style="background-color: var(--accent-color);"
            >
              <Play class="w-5 h-5 ml-0.5 fill-current" />
            </div>
          </div>

          <!-- Unit Type Badge (hidden if batch mode checkbox is in place) -->
          <div
            v-if="!isBatchMode"
            class="absolute top-2.5 left-2.5 flex items-center gap-1.5 z-20"
          >
            <span
              v-if="card.is_series && card.unit_count > 1"
              class="flex items-center gap-1 bg-gradient-to-r from-purple-600/90 to-indigo-600/90 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Layers class="w-3 h-3" />
              <span>{{ card.unit_count }} {{ card.unit_type === 'video' ? '视频' : (card.unit_type === 'audio' ? '音轨' : '项目') }}</span>
            </span>
            <span
              v-else-if="card.unit_type === 'bundle'"
              class="flex items-center gap-1 bg-purple-600/80 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Layers class="w-3 h-3" />
              <span>复合包</span>
            </span>
            <span
              v-else-if="card.unit_type === 'video'"
              class="flex items-center gap-1 bg-blue-600/80 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Video class="w-3 h-3" />
              <span>视频</span>
            </span>
            <span
              v-else-if="card.unit_type === 'audio'"
              class="flex items-center gap-1 bg-emerald-600/80 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <Music class="w-3 h-3" />
              <span>音频</span>
            </span>
            <span
              v-else
              class="flex items-center gap-1 bg-amber-600/80 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
            >
              <ImageIcon class="w-3 h-3" />
              <span>图片</span>
            </span>
          </div>

          <!-- Duration Chip -->
          <div
            v-if="card.duration_seconds"
            class="absolute bottom-2.5 right-2.5 bg-black/70 backdrop-blur-sm text-[10px] text-gray-200 px-2 py-0.5 rounded-md flex items-center gap-1 font-mono z-20"
          >
            <Clock class="w-3 h-3 text-gray-400" />
            <span>{{ formatDuration(card.duration_seconds) }}</span>
          </div>

          <!-- Quick Action Buttons (top right) -->
          <div class="absolute top-2.5 right-2.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-20">
            <!-- Quick Add to Superset -->
            <button
              @click.stop="(e) => openQuickSuperset(e, card)"
              title="收纳至虚拟超集"
              class="p-1.5 rounded-full bg-black/60 hover:bg-black/90 text-gray-200 hover:text-pink-300 backdrop-blur-md transition-colors"
            >
              <BookmarkPlus class="w-3.5 h-3.5" />
            </button>
            <!-- Add to Queue -->
            <button
              v-if="card.is_series && card.unit_count > 1"
              @click.stop="handleAddSeriesToQueue(card)"
              :title="`将整个系列 (${card.unit_count}项) 加入背景播放队列`"
              class="p-1.5 rounded-full bg-black/60 hover:bg-black/90 text-gray-200 hover:text-purple-300 backdrop-blur-md transition-colors"
            >
              <ListPlus class="w-3.5 h-3.5" />
            </button>
            <button
              v-else
              @click.stop="playerStore.addToBgQueue(card)"
              title="加入背景播放队列"
              class="p-1.5 rounded-full bg-black/60 hover:bg-black/90 text-gray-200 hover:text-purple-300 backdrop-blur-md transition-colors"
            >
              <ListPlus class="w-3.5 h-3.5" />
            </button>
            <button
              @click="(e) => handleReveal(e, card)"
              title="在系统文件管理器中查看"
              class="p-1.5 rounded-full bg-black/60 hover:bg-black/90 text-gray-200 hover:text-white backdrop-blur-md transition-colors"
            >
              <FolderOpen class="w-3.5 h-3.5" />
            </button>
            <button
              @click="(e) => handleOpenExternal(e, card)"
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
            <h4 class="text-sm font-medium text-gray-100 truncate group-hover:text-purple-300 transition-colors" :title="card.title">
              {{ card.title }}
            </h4>

            <!-- Collection Info -->
            <div class="flex items-center justify-between text-[11px] text-gray-400 mt-1">
              <span v-if="card.is_series && card.unit_count > 1" class="text-purple-400 font-mono text-[11px] font-semibold truncate max-w-[150px]">
                全 {{ card.unit_count }} 选集 · 系列连播
              </span>
              <span v-else class="truncate max-w-[150px]">
                {{ card.collection_name || '散落文件' }}
              </span>
              <span v-if="card.view_count > 0" class="text-gray-500 font-mono">
                {{ card.view_count }} 次浏览
              </span>
            </div>

            <!-- Tag Badges on Card -->
            <div v-if="card.tags && card.tags.length > 0" class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="t in card.tags.slice(0, 3)"
                :key="t.id || t.name"
                class="text-[10px] px-1.5 py-0.5 rounded-md font-medium border"
                :class="t.class_code === 'workflow'
                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                  : (t.class_code === 'domain'
                    ? 'bg-purple-500/10 text-purple-300 border-purple-500/20'
                    : 'bg-white/5 text-gray-400 border-white/5')"
              >
                {{ t.name }}
              </span>
              <span
                v-if="card.tags.length > 3"
                class="text-[9px] px-1 py-0.5 rounded text-gray-500 font-mono"
              >
                +{{ card.tags.length - 3 }}
              </span>
            </div>
          </div>

          <!-- Feedback & Rating Bar (Clean, Minimalist Aesthetics) -->
          <div class="flex items-center justify-between mt-3 pt-2 border-t border-white/5">
            <!-- Rating Display & Interactive Rate -->
            <div class="flex items-center gap-1.5">
              <!-- Rated Star Badge -->
              <span
                v-if="card.rating > 0"
                class="flex items-center gap-1 text-[11px] font-semibold text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20"
                :title="`评分: ${card.rating} 星`"
              >
                <Star class="w-3 h-3 fill-amber-400 text-amber-400" />
                <span>{{ card.rating }}</span>
              </span>

              <!-- Interactive 5-Star (appears smoothly on hover or subtle if unrated) -->
              <div
                class="flex items-center gap-0.5 transition-opacity duration-200"
                :class="card.rating > 0 ? 'opacity-0 group-hover:opacity-100' : 'opacity-20 group-hover:opacity-100'"
              >
                <button
                  v-for="s in 5"
                  :key="s"
                  @click.stop="(e) => handleRate(e, card, s)"
                  class="p-0.5 text-gray-500 hover:text-amber-400 transition-colors"
                  :title="`评分 ${s} 星`"
                >
                  <Star
                    :class="[
                      'w-3 h-3',
                      s <= card.rating ? 'text-amber-400 fill-amber-400' : ''
                    ]"
                  />
                </button>
              </div>
            </div>

            <!-- Favorite Heart -->
            <button
              @click.stop="(e) => handleToggleFavorite(e, card)"
              class="p-1 transition-all"
              :class="[
                card.is_favorite
                  ? 'text-rose-500'
                  : 'text-gray-500 opacity-40 group-hover:opacity-100 hover:text-rose-400'
              ]"
              :title="card.is_favorite ? '已收藏' : '标记喜欢'"
            >
              <Heart
                :class="[
                  'w-4 h-4 transition-transform active:scale-125',
                  card.is_favorite ? 'text-rose-500 fill-rose-500 scale-105' : ''
                ]"
              />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Stream Infinite Scroll / Load More Footer (Flat Unit Mode) -->
    <div
      v-if="mediaStore.feedDisplayMode === 'flat' && !mediaStore.loading && displayItems.length > 0"
      class="mt-10 py-6 flex flex-col items-center justify-center border-t border-white/5 text-xs text-gray-400"
    >
      <button
        v-if="mediaStore.hasMoreFeed"
        @click="mediaStore.loadMoreFeed()"
        :disabled="mediaStore.loadingMore"
        class="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 hover:text-white border border-white/10 font-medium transition-all shadow-md active:scale-95 disabled:opacity-50"
      >
        <span v-if="mediaStore.loadingMore" class="w-4 h-4 rounded-full border-2 border-purple-400 border-t-transparent animate-spin" />
        <Layers v-else class="w-4 h-4 text-purple-400" />
        <span>{{ mediaStore.loadingMore ? '正在填充下一批单轨...' : '加载更多分集单轨 (流式填充)' }}</span>
      </button>
      <div v-else class="flex items-center gap-1.5 text-gray-500 font-mono">
        <Check class="w-4 h-4 text-emerald-400" />
        <span>已展示全库全部 {{ displayItems.length }} 轨内容（零遗漏）</span>
      </div>
    </div>

    <!-- Series Mode Bottom Summary -->
    <div
      v-else-if="mediaStore.feedDisplayMode === 'series' && !mediaStore.loading && displayItems.length > 0"
      class="mt-10 py-6 flex items-center justify-center border-t border-white/5 text-xs text-gray-500 font-mono"
    >
      <span>已全景陈列全库全部 {{ displayItems.length }} 个作品系列</span>
    </div>

    <!-- Bottom Floating Batch Dock -->
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

    <!-- Batch Add to Superset Dialog Modal -->
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
  </div>
</template>
