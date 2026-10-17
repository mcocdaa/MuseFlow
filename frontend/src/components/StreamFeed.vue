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
  User,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronRight,
  Search,
  FolderTree,
  Flame,
  Snowflake
} from 'lucide-vue-next'
import {
  revealInExplorer,
  openWithDefaultApp,
  createSuperset,
  addItemToSuperset,
  addItemsBatchToSuperset,
  fetchAssets,
  fetchAssetDetail
} from '../api'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const algoMeta = {
  resonance: {
    icon: Flame,
    color: '#f43f5e',
    desc: '基于多次打分复合偏好、标签亲和力扩散与疲劳度冷却的深度智能共鸣推荐',
  },
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

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('scroll', handleScroll, { passive: true })
  if (!mediaStore.allTags || mediaStore.allTags.length === 0) {
    await mediaStore.loadTags()
  }
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

  // 2. Unit type fallback for media kind (strictly by primary unit_type so bound companion illustrations never leak into '图片')
  if (category === 'media_kind') {
    if (value === '音频' && item.unit_type === 'audio') return true
    if (value === '视频' && (item.unit_type === 'video' || item.unit_type === 'bundle')) return true
    if (value === '图片' && item.unit_type === 'image') return true
    return false
  }

  // 3. Resilient semantic fallback matching for domain / topic tags
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

const FACET_META = {
  media_kind: { name: '媒体形态', icon: Layers, color: '#60a5fa' },
  spec: { name: '语种与声学', icon: Globe, color: '#38bdf8' },
  domain: { name: '核心题材', icon: Sparkles, color: '#c084fc' },
  character: { name: '角色人设', icon: Heart, color: '#f472b6' },
  interaction: { name: '互动表现', icon: Flame, color: '#fb923c' },
  creator: { name: '创作者 / 社团', icon: User, color: '#34d399' },
  va: { name: '声优 / 演职员', icon: Music, color: '#fbbf24' },
  workflow: { name: '状态分流', icon: CheckCheck, color: '#a3e635' },
}

const availableFacets = computed(() => {
  const facetMap = new Map()
  const tagMetaMap = new Map()

  // 1. 优先使用率先载入的 allTags (<50ms)，瞬间就绪渲染结构化标签面板
  const sourceTags = (mediaStore.allTags && mediaStore.allTags.length > 0)
    ? mediaStore.allTags
    : mediaStore.feedItems.flatMap(i => i.tags || [])

  for (const t of sourceTags) {
    if (!t.name || t.name.length > 30) continue
    const code = t.class_code || 'domain'
    const metaCfg = FACET_META[code] || { name: t.class_name || '分类标签', icon: Sparkles, color: '#c084fc' }
    const displayName = t.class_name || metaCfg.name
    const iconComp = metaCfg.icon

    if (!facetMap.has(code)) {
      facetMap.set(code, {
        key: code,
        name: displayName,
        icon: iconComp,
        color: metaCfg.color,
        options: new Set()
      })
    }
    facetMap.get(code).options.add(t.name)
    const metaKey = `${code}::${t.name}`
    if (!tagMetaMap.has(metaKey)) {
      tagMetaMap.set(metaKey, {
        name: t.name,
        parent_name: t.parent_name,
        parent_id: t.parent_id,
        full_path: t.full_path,
        unit_count: t.unit_count || 0,
      })
    }
  }

  const result = []
  for (const facet of facetMap.values()) {
    if (facet.options.size > 0) {
      const tagList = Array.from(facet.options).map(name => {
        const meta = tagMetaMap.get(`${facet.key}::${name}`) || {}
        const fullPath = meta.full_path || name
        const depth = fullPath.split(' / ').length - 1
        return {
          value: name,
          label: name,
          parent_name: meta.parent_name,
          parent_id: meta.parent_id,
          full_path: fullPath,
          depth: Math.max(0, depth),
          isChild: depth > 0,
          unit_count: meta.unit_count || 0
        }
      })

      const parentNames = new Set(tagList.map(t => t.parent_name).filter(Boolean))
      for (const opt of tagList) {
        opt.hasChildren = parentNames.has(opt.value)
      }

      let sortedOptions = []
      if (facet.key === 'media_kind') {
        const order = ['音频', '视频', '图片', '复合媒体']
        sortedOptions = tagList.sort((a, b) => {
          const rootA = a.full_path.split(' / ')[0]
          const rootB = b.full_path.split(' / ')[0]
          const ia = order.indexOf(rootA)
          const ib = order.indexOf(rootB)
          if (ia !== ib) return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
          return a.full_path.localeCompare(b.full_path)
        })
      } else {
        // Group tree nodes cleanly so children follow their parent, while sorting siblings by unit_count desc
        const byPath = new Map(tagList.map(t => [t.full_path, t]))
        sortedOptions = tagList.sort((a, b) => {
          if (a.full_path === b.full_path) return 0
          if (b.full_path.startsWith(a.full_path + ' / ')) return -1
          if (a.full_path.startsWith(b.full_path + ' / ')) return 1
          const partsA = a.full_path.split(' / ')
          const partsB = b.full_path.split(' / ')
          const minLen = Math.min(partsA.length, partsB.length)
          for (let i = 0; i < minLen; i++) {
            if (partsA[i] !== partsB[i]) {
              const ancPathA = partsA.slice(0, i + 1).join(' / ')
              const ancPathB = partsB.slice(0, i + 1).join(' / ')
              const cntA = byPath.get(ancPathA)?.unit_count || 0
              const cntB = byPath.get(ancPathB)?.unit_count || 0
              if (cntA !== cntB) return cntB - cntA
              return partsA[i].localeCompare(partsB[i])
            }
          }
          return partsA.length - partsB.length
        })
      }

      result.push({
        key: facet.key,
        name: facet.name,
        icon: facet.icon,
        color: facet.color,
        options: sortedOptions
      })
    }
  }

  // 正交分面自然认知顺序（未知自定义维度自动排在 workflow 之前）
  const classOrder = ['media_kind', 'spec', 'domain', 'character', 'interaction', 'creator', 'va', 'workflow']
  result.sort((a, b) => {
    const ia = classOrder.indexOf(a.key)
    const ib = classOrder.indexOf(b.key)
    return (ia === -1 ? 6 : ia) - (ib === -1 ? 6 : ib)
  })

  return result
})

// Scheme A: Left Collapsible Facet Tree Sidebar State & Helpers
const sidebarSearch = ref('')
// 默认展开前 3 个核心高频维度，其余长列表维度默认折叠为一栏标题，保持边栏极简一目了然
const collapsedSections = ref(new Set(['character', 'interaction', 'creator', 'va', 'workflow']))
// 通用树折叠策略：顶层根节点 (depth === 0) 默认展开，二级及以上父节点 (depth >= 1) 默认收折
const collapsedRootNodes = ref(new Set())
const expandedSubNodes = ref(new Set())
const expandedFullSections = ref(new Set())

const toggleSection = (key) => {
  const s = new Set(collapsedSections.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  collapsedSections.value = s
}

const toggleAllSections = () => {
  const allKeys = availableFacets.value.map(f => f.key)
  if (collapsedSections.value.size >= allKeys.length - 1) {
    collapsedSections.value = new Set(['character', 'interaction', 'creator', 'va', 'workflow'])
  } else {
    collapsedSections.value = new Set(allKeys)
  }
}

const toggleSectionShowAll = (key) => {
  const s = new Set(expandedFullSections.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  expandedFullSections.value = s
}

const isSectionFullyExpanded = (key) => expandedFullSections.value.has(key)

const isNodeCollapsed = (nodeValue, depth = 0) => {
  return depth === 0 ? collapsedRootNodes.value.has(nodeValue) : !expandedSubNodes.value.has(nodeValue)
}

const toggleNodeCollapse = (nodeValue, e, depth = 0) => {
  if (e) e.stopPropagation()
  if (depth === 0) {
    const s = new Set(collapsedRootNodes.value)
    if (s.has(nodeValue)) s.delete(nodeValue)
    else s.add(nodeValue)
    collapsedRootNodes.value = s
  } else {
    const s = new Set(expandedSubNodes.value)
    if (s.has(nodeValue)) s.delete(nodeValue)
    else s.add(nodeValue)
    expandedSubNodes.value = s
  }
}

const isSectionCollapsed = (key) => collapsedSections.value.has(key)

const getActiveCountInSection = (key) => {
  return mediaStore.activeFacetFilters[key]?.length || 0
}

const isNodeVisible = (opt, group) => {
  if (sidebarSearch.value.trim()) {
    const q = sidebarSearch.value.trim().toLowerCase()
    if (opt.label.toLowerCase().includes(q) || (opt.full_path && opt.full_path.toLowerCase().includes(q))) {
      return true
    }
    const hasMatchingDescendant = group.options.some(child =>
      child.full_path?.startsWith(opt.full_path + ' / ') &&
      (child.label.toLowerCase().includes(q) || child.full_path.toLowerCase().includes(q))
    )
    return hasMatchingDescendant
  }

  if (!opt.full_path) return true
  const ancestors = opt.full_path.split(' / ').slice(0, -1)
  for (let i = 0; i < ancestors.length; i++) {
    if (isNodeCollapsed(ancestors[i], i)) {
      return false
    }
  }
  return true
}

const getVisibleGroupOptions = (group) => {
  const visible = group.options.filter(opt => isNodeVisible(opt, group))
  if (sidebarSearch.value.trim() || expandedFullSections.value.has(group.key) || group.key === 'media_kind' || group.key === 'spec' || group.key === 'workflow') {
    return visible
  }
  // Keep any currently active filter visible even if beyond top 10
  const topSlice = visible.slice(0, 10)
  const topSet = new Set(topSlice.map(o => o.value))
  for (const opt of visible.slice(10)) {
    if (mediaStore.isFacetActive(group.key, opt.value) && !topSet.has(opt.value)) {
      topSlice.push(opt)
    }
  }
  return topSlice
}

const getHiddenOptionCount = (group) => {
  if (sidebarSearch.value.trim() || group.key === 'media_kind' || group.key === 'spec' || group.key === 'workflow') return 0
  const visible = group.options.filter(opt => isNodeVisible(opt, group))
  return Math.max(0, visible.length - 10)
}

// O(1) Precomputed facet counts across current feedItems to avoid O(N*M) per-render lag
const facetMatchCountMap = computed(() => {
  const counts = new Map()
  const items = mediaStore.feedItems || []
  if (items.length === 0) return counts

  let audioCnt = 0
  let videoCnt = 0
  let imageCnt = 0

  for (const item of items) {
    if (item.unit_type === 'audio') audioCnt++
    if (item.unit_type === 'video' || item.unit_type === 'bundle') videoCnt++
    if (item.unit_type === 'image') imageCnt++

    const seenNamesForItem = new Set()
    if (item.tags && Array.isArray(item.tags)) {
      for (const t of item.tags) {
        if (t.name) seenNamesForItem.add(t.name)
        if (t.full_path) {
          for (const part of t.full_path.split(' / ')) {
            if (part) seenNamesForItem.add(part)
          }
        }
      }
    }
    if (item.tag_names && Array.isArray(item.tag_names)) {
      for (const tn of item.tag_names) {
        if (tn) seenNamesForItem.add(tn)
      }
    }
    for (const name of seenNamesForItem) {
      counts.set(name, (counts.get(name) || 0) + 1)
    }
  }
  counts.set('media_kind::音频', audioCnt)
  counts.set('media_kind::视频', videoCnt)
  counts.set('media_kind::图片', imageCnt)
  return counts
})

const getFacetMatchCount = (category, value) => {
  if (mediaStore.feedItems && mediaStore.feedItems.length > 0) {
    if (category === 'media_kind' && ['音频', '视频', '图片'].includes(value)) {
      return facetMatchCountMap.value.get(`media_kind::${value}`) || 0
    }
    return facetMatchCountMap.value.get(value) || 0
  }
  const tObj = mediaStore.allTags?.find(t => t.name === value && (!t.class_code || t.class_code === category))
  return tObj ? (tObj.unit_count || 0) : 0
}

const activeFilterList = computed(() => {
  const list = []
  for (const [cat, vals] of Object.entries(mediaStore.activeFacetFilters)) {
    if (vals && vals.length > 0) {
      const catConfig = availableFacets.value.find(f => f.key === cat)
      const catName = catConfig ? catConfig.name : (FACET_META[cat]?.name || cat)
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

const MEDIA_KIND_NAMES = new Set(['音频', '视频', '图片', '复合媒体'])

const tagGlobalCountMap = computed(() => {
  const m = new Map()
  for (const t of (mediaStore.allTags || [])) {
    m.set(t.name, t.unit_count || 0)
  }
  return m
})

const parentTagNameSet = computed(() => {
  const s = new Set()
  for (const t of (mediaStore.allTags || [])) {
    if (t.parent_name) s.add(t.parent_name)
  }
  return s
})

const getCardTagBadgeClass = (classCode) => {
  switch (classCode) {
    case 'character':
    case 'guest':
      return 'bg-pink-500/12 text-pink-300 border-pink-500/25 hover:bg-pink-500/25'
    case 'interaction':
    case 'difficulty':
      return 'bg-orange-500/12 text-orange-300 border-orange-500/25 hover:bg-orange-500/25'
    case 'domain':
    case 'genre':
    case 'topic':
    case 'project':
    case 'tech_stack':
      return 'bg-purple-500/12 text-purple-300 border-purple-500/25 hover:bg-purple-500/25'
    case 'va':
    case 'release_year':
    case 'gear':
      return 'bg-amber-500/12 text-amber-300 border-amber-500/25 hover:bg-amber-500/25'
    case 'spec':
    case 'album':
      return 'bg-sky-500/12 text-sky-300 border-sky-500/25 hover:bg-sky-500/25'
    case 'creator':
    case 'artist':
    case 'host':
    case 'client':
    case 'instructor':
      return 'bg-teal-500/12 text-teal-300 border-teal-500/25 hover:bg-teal-500/25'
    case 'workflow':
      return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20 hover:bg-emerald-500/25'
    default:
      return 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/15'
  }
}

const getCleanCardTags = (card) => {
  if (!card || !card.tags || !card.tags.length) return []
  const colName = (card.collection_name || '').trim()

  // 1. 过滤掉已在卡片左上角展示的媒体形态 (media_kind)，以及与副标题完全重复的创作者名
  const nonMedia = card.tags.filter(t => {
    if (!t.name || t.class_code === 'media_kind' || MEDIA_KIND_NAMES.has(t.name)) return false
    if (t.class_code === 'creator' && colName && colName.includes(t.name)) return false
    return true
  })

  // 2. 若同一卡片上既有父节点标签又有更具体的子节点标签，自动隐去冗余父节点标签，优先呈现高信息熵叶子标签
  const hasLeafInSameTree = (tag) => {
    if (!tag.full_path) return false
    return nonMedia.some(other => other !== tag && other.full_path && other.full_path.startsWith(tag.full_path + ' / '))
  }
  const hasSpecificNonParent = nonMedia.some(t => !parentTagNameSet.value.has(t.name) && t.class_code !== 'workflow')
  const filtered = nonMedia.filter(t => {
    if (hasLeafInSameTree(t)) return false
    if (hasSpecificNonParent && parentTagNameSet.value.has(t.name) && (t.full_path || t.name).indexOf(' / ') === -1) {
      return false
    }
    return true
  })

  const classPriority = {
    character: 1,
    interaction: 2,
    domain: 3,
    genre: 3,
    tech_stack: 3,
    topic: 3,
    project: 3,
    va: 4,
    spec: 5,
    creator: 6,
    artist: 6,
    instructor: 6,
    workflow: 8,
  }

  return [...filtered].sort((a, b) => {
    // 叶子节点优先于容器父节点
    const isParentA = parentTagNameSet.value.has(a.name) ? 1 : 0
    const isParentB = parentTagNameSet.value.has(b.name) ? 1 : 0
    if (isParentA !== isParentB) return isParentA - isParentB

    const pa = classPriority[a.class_code] || 5
    const pb = classPriority[b.class_code] || 5
    if (pa !== pb) return pa - pb

    // 同一维度内，按全库出现频次升序（IDF 信息熵降序：越具体独特的标签越靠前）
    const cntA = tagGlobalCountMap.value.get(a.name) || 0
    const cntB = tagGlobalCountMap.value.get(b.name) || 0
    return cntA - cntB
  })
}

const handleCardClick = async (card) => {
  if (isBatchMode.value) {
    toggleSelect(card.id)
    return
  }

  if (card.is_series && card.collection_id && card.unit_count > 1) {
    try {
      const fullSeries = await fetchAssets({ collection_id: card.collection_id, limit: 300 })
      if (fullSeries && fullSeries.length > 0) {
        const audioTracks = fullSeries.filter(u => isAudioUnit(u))
        const videoTracks = fullSeries.filter(u => u.unit_type === 'video' || u.unit_type === 'bundle')
        const imageTracks = fullSeries.filter(u => u.unit_type === 'image')

        if (audioTracks.length > 0) {
          playerStore.openAudioModal(audioTracks[0], audioTracks, false, imageTracks)
        } else if (videoTracks.length > 0) {
          playerStore.openVideo(videoTracks[0], videoTracks, false)
        } else if (imageTracks.length > 0) {
          playerStore.openImage(imageTracks[0], imageTracks, false)
        }
        return
      }
    } catch (e) {
      console.warn('Failed to load full series playlist, playing card directly', e)
    }
  }

  // Ensure playable unit has full files metadata for streaming
  let playableCard = card
  if (!playableCard.files || playableCard.files.length === 0) {
    try {
      const detail = await fetchAssetDetail(playableCard.representative_unit_id || playableCard.id)
      if (detail && detail.files && detail.files.length > 0) {
        playableCard = detail
      }
    } catch (e) {
      console.warn('Failed to fetch asset detail for card streaming', e)
    }
  }

  if (isAudioUnit(playableCard)) {
    playerStore.openAudioModal(playableCard, [playableCard], false)
  } else if (playableCard.unit_type === 'video' || playableCard.unit_type === 'bundle') {
    playerStore.openVideo(playableCard, [playableCard], false)
  } else if (playableCard.unit_type === 'image') {
    playerStore.openImage(playableCard, [playableCard], false)
  }
}

const handleAddSeriesToQueue = async (card) => {
  if (card.is_series && card.collection_id) {
    try {
      const full = await fetchAssets({ collection_id: card.collection_id, limit: 300 })
      if (full && full.length > 0) {
        const playable = full.filter(u => isAudioUnit(u) || u.unit_type === 'video' || u.unit_type === 'bundle')
        const toAdd = playable.length > 0 ? playable : full
        playerStore.addMultipleToBgQueue(toAdd)
        playerStore.showToast(`已将系列「${card.title}」共 ${toAdd.length} 项加入队列`)
        return
      }
    } catch (e) {}
  }
  let toEnqueue = card
  if (!toEnqueue.files || toEnqueue.files.length === 0) {
    try {
      const detail = await fetchAssetDetail(toEnqueue.representative_unit_id || toEnqueue.id)
      if (detail && detail.files && detail.files.length > 0) {
        toEnqueue = detail
      }
    } catch (e) {}
  }
  playerStore.addToBgQueue(toEnqueue)
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

const hoveredCardStar = ref({})

const getStarFillPercent = (card, s) => {
  const cid = card.card_id || card.id
  const h = hoveredCardStar.value[cid]
  if (h && h > 0) {
    return s <= h ? 100 : 0
  }
  const rating = Number(card.rating || 0)
  if (s <= rating) return 100
  if (s - 1 >= rating) return 0
  return Math.round((rating - (s - 1)) * 100)
}

const handleAppendRate = async (e, card, stars) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  const updated = await mediaStore.updateRating(targetId, stars)
  if (updated && updated.rating !== undefined) {
    card.rating = updated.rating
  }
  const finalRating = Number(card.rating || stars).toFixed(1)
  playerStore.showToast(`✨ 追加 ${stars} 星好评 (当前有效评分: ${finalRating}★)`)
}

const handleCooldown = async (e, card) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  await mediaStore.addToCooldown(targetId, 14, '听腻了')
  playerStore.showToast('已加入冷却池 (未来 14 天不再推荐)')
}

const handleToggleFavorite = (e, card) => {
  e.stopPropagation()
  const targetId = card.representative_unit_id || card.id
  mediaStore.toggleFavorite(targetId)
  card.is_favorite = !card.is_favorite
  playerStore.showToast(card.is_favorite ? '已加入喜爱收藏' : '已取消收藏')
}
</script>

<template>
  <div class="max-w-[1720px] mx-auto px-4 sm:px-6 lg:px-8 py-5 transition-all">
    <!-- Stream Toolbar: Category Filters & Custom Algorithm Popover -->
    <div class="flex items-center justify-between gap-4 mb-4 select-none">
      <!-- Left Controls: Sidebar toggle, Series/Flat mode pill, Actions -->
      <div class="flex items-center gap-2">
        <!-- Sidebar Toggle Icon Button -->
        <button
          @click="mediaStore.sidebarOpen = !mediaStore.sidebarOpen"
          :class="[
            'p-2 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 border cursor-pointer',
            mediaStore.sidebarOpen
              ? 'bg-purple-600/20 text-purple-200 border-purple-500/40 shadow-sm'
              : 'bg-white/5 border-white/10 text-gray-400 hover:text-white hover:bg-white/10'
          ]"
          :title="mediaStore.sidebarOpen ? '收起分类边栏' : '展开分类边栏'"
        >
          <component :is="mediaStore.sidebarOpen ? PanelLeftClose : PanelLeftOpen" class="w-4 h-4 text-purple-400" />
          <span
            v-if="activeFilterList.length > 0"
            class="text-[10px] px-1.5 py-0.2 rounded-full font-bold text-white bg-purple-600 font-mono"
          >
            {{ activeFilterList.length }}
          </span>
        </button>

        <!-- Segmented Mode Control: 系列聚合 vs 单篇平铺 -->
        <div class="flex items-center bg-black/25 p-1 rounded-xl border border-white/5">
          <button
            @click="mediaStore.setFeedDisplayMode('series')"
            :class="[
              'px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer',
              mediaStore.feedDisplayMode === 'series'
                ? 'bg-purple-600/30 text-purple-200 shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            title="系列聚合视图：同一系列打包成单张卡片"
          >
            系列聚合
          </button>
          <button
            @click="mediaStore.setFeedDisplayMode('flat')"
            :class="[
              'px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer',
              mediaStore.feedDisplayMode === 'flat'
                ? 'bg-purple-600/30 text-purple-200 shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            title="单篇平铺视图：所有分集独立平铺"
          >
            单篇平铺
          </button>
        </div>

        <!-- Slideshow Autoplay Trigger Button -->
        <button
          v-if="displayItems.length > 0"
          @click="startSlideshowAll"
          class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium text-purple-200 bg-white/5 hover:bg-purple-600/20 border border-white/10 hover:border-purple-500/30 transition-all cursor-pointer"
          title="开启当前列表自动连播"
        >
          <Play class="w-3.5 h-3.5 fill-current text-purple-400" />
          <span>连播</span>
        </button>

        <!-- Batch Selection Mode Toggle -->
        <button
          v-if="displayItems.length > 0"
          @click="toggleBatchMode"
          :class="[
            'p-2 rounded-xl text-xs font-medium transition-all border cursor-pointer',
            isBatchMode
              ? 'bg-purple-600 text-white border-purple-500 shadow-sm'
              : 'bg-white/5 border-white/10 text-gray-400 hover:text-white hover:bg-white/10'
          ]"
          :title="isBatchMode ? '退出批量多选' : '进入批量多选'"
        >
          <CheckSquare class="w-4 h-4" />
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

    <!-- Main Content: Left Facet Tree Sidebar (Scheme A) + Right Media Feed -->
    <div class="flex items-start gap-6 relative">
      <!-- Scheme A: Left Sticky Collapsible Facet Tree Sidebar -->
      <aside
        v-show="mediaStore.sidebarOpen"
        class="w-64 lg:w-72 xl:w-80 shrink-0 sticky top-20 max-h-[calc(100vh-6rem)] flex flex-col rounded-2xl border backdrop-blur-xl shadow-xl transition-all overflow-hidden z-20"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Sidebar Header -->
        <div class="px-4 py-3 border-b flex items-center justify-between shrink-0" style="border-color: var(--border-color);">
          <div class="flex items-center gap-2">
            <div class="p-1 rounded-lg text-purple-400 bg-purple-500/10">
              <FolderTree class="w-4 h-4" />
            </div>
            <span class="text-xs font-bold tracking-wide uppercase" style="color: var(--text-main);">
              分类与标签
            </span>
            <span
              v-if="activeFilterList.length > 0"
              class="text-[10px] px-2 py-0.5 rounded-full font-bold text-white shadow-xs"
              style="background: var(--accent-color);"
            >
              已选 {{ activeFilterList.length }}
            </span>
          </div>

          <div class="flex items-center gap-1">
            <button
              v-if="mediaStore.hasAnyActiveFacet()"
              @click="mediaStore.clearFacetFilters()"
              class="text-[11px] text-red-400 hover:text-red-300 hover:bg-red-500/10 px-2 py-1 rounded-lg transition-colors flex items-center gap-1"
              title="清空所有分类筛选"
            >
              <RotateCcw class="w-3 h-3" />
              <span>清空</span>
            </button>
            <button
              @click="mediaStore.sidebarOpen = false"
              class="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
              title="收起分类边栏"
            >
              <PanelLeftClose class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Sidebar Search Box -->
        <div class="p-2.5 border-b shrink-0" style="border-color: var(--border-color); background: rgba(255, 255, 255, 0.01);">
          <div class="relative">
            <Search class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              v-model="sidebarSearch"
              type="text"
              placeholder="过滤分类标签..."
              class="w-full bg-white/5 border border-white/10 rounded-xl pl-8 pr-7 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/60 transition-colors"
            />
            <button
              v-if="sidebarSearch"
              @click="sidebarSearch = ''"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>

        <!-- Tree Accordion Scroll Area -->
        <div class="flex-grow overflow-y-auto min-h-0 no-scrollbar p-2 space-y-2">
          <!-- Loading skeleton while tags are being fetched -->
          <div v-if="mediaStore.tagsLoading && availableFacets.length === 0" class="p-3 space-y-3">
            <div v-for="i in 4" :key="i" class="animate-pulse space-y-2 p-2 rounded-xl bg-white/5">
              <div class="h-3.5 bg-white/10 rounded w-20"></div>
              <div class="h-3 bg-white/5 rounded w-32 ml-3"></div>
              <div class="h-3 bg-white/5 rounded w-24 ml-3"></div>
            </div>
          </div>

          <!-- Empty state if no tags found -->
          <div v-else-if="availableFacets.length === 0" class="p-6 text-center text-xs text-gray-500">
            <TagIcon class="w-6 h-6 mx-auto mb-2 opacity-40 text-purple-400" />
            <p>未发现已分类标签</p>
            <button
              @click="mediaStore.loadTags()"
              class="mt-2 text-purple-400 hover:text-purple-300 underline text-[11px]"
            >
              重新同步标签树
            </button>
          </div>

          <!-- Facet Groups -->
          <div
            v-else
            v-for="group in availableFacets"
            :key="group.key"
            class="rounded-xl overflow-hidden border border-white/5 bg-white/[0.02]"
          >
            <!-- Section Header -->
            <button
              @click="toggleSection(group.key)"
              class="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/5 transition-colors select-none cursor-pointer"
            >
              <div class="flex items-center gap-2">
                <component :is="group.icon || TagIcon" class="w-3.5 h-3.5" :style="{ color: group.color || '#c084fc' }" />
                <span>{{ group.name }}</span>
                <span
                  v-if="getActiveCountInSection(group.key) > 0"
                  class="text-[10px] px-1.5 py-0.2 rounded-full font-bold text-purple-200 bg-purple-600/40 border border-purple-500/40"
                >
                  {{ getActiveCountInSection(group.key) }}
                </span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="text-[10px] text-gray-500 font-mono">{{ group.options.length }}</span>
                <component
                  :is="isSectionCollapsed(group.key) ? ChevronRight : ChevronDown"
                  class="w-3.5 h-3.5 text-gray-500 transition-transform"
                />
              </div>
            </button>

            <!-- Tree Node List -->
            <div
              v-show="!isSectionCollapsed(group.key)"
              class="py-1 px-1 space-y-0.5"
            >
              <!-- For media_kind: Quick '全部形态 (不限)' option -->
              <div
                v-if="group.key === 'media_kind' && !sidebarSearch"
                @click="mediaStore.activeFacetFilters.media_kind = []"
                :class="[
                  'group flex items-center justify-between py-1.5 px-2 rounded-lg text-xs cursor-pointer select-none transition-all mb-1',
                  (!mediaStore.activeFacetFilters.media_kind || mediaStore.activeFacetFilters.media_kind.length === 0)
                    ? 'bg-purple-600/25 border border-purple-500/50 text-white font-medium shadow-xs'
                    : 'hover:bg-white/5 text-gray-400 hover:text-gray-200 border border-transparent'
                ]"
                style="padding-left: 8px;"
              >
                <div class="flex items-center gap-1.5 min-w-0">
                  <span class="w-3 text-center text-purple-400 text-[10px]">★</span>
                  <component
                    :is="(!mediaStore.activeFacetFilters.media_kind || mediaStore.activeFacetFilters.media_kind.length === 0) ? CheckSquare : Square"
                    class="w-3.5 h-3.5 shrink-0 transition-colors"
                    :class="(!mediaStore.activeFacetFilters.media_kind || mediaStore.activeFacetFilters.media_kind.length === 0) ? 'text-purple-400' : 'text-gray-600 group-hover:text-gray-400'"
                  />
                  <span class="truncate font-medium">全部形态 (不限)</span>
                </div>
                <span
                  class="text-[10px] font-mono px-1.5 py-0.2 rounded-full shrink-0 ml-1.5"
                  :class="(!mediaStore.activeFacetFilters.media_kind || mediaStore.activeFacetFilters.media_kind.length === 0) ? 'bg-purple-500/30 text-purple-200 font-bold' : 'bg-white/5 text-gray-500'"
                >
                  {{ mediaStore.feedItems.length }}
                </span>
              </div>
              <template v-for="opt in getVisibleGroupOptions(group)" :key="opt.value">
                <div
                  @click="mediaStore.toggleFacetFilter(group.key, opt.value)"
                  :class="[
                    'group flex items-center justify-between py-1.5 px-2 rounded-lg text-xs cursor-pointer select-none transition-all',
                    mediaStore.isFacetActive(group.key, opt.value)
                      ? 'bg-purple-600/25 border border-purple-500/50 text-white font-medium shadow-xs'
                      : 'hover:bg-white/5 text-gray-400 hover:text-gray-200 border border-transparent'
                  ]"
                  :style="{ paddingLeft: `${(opt.depth || 0) * 14 + 8}px` }"
                >
                  <div class="flex items-center gap-1.5 min-w-0">
                    <!-- Folding chevron if has children -->
                    <button
                      v-if="opt.hasChildren"
                      @click.stop="toggleNodeCollapse(opt.value, $event, opt.depth)"
                      class="p-0.5 rounded hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors cursor-pointer"
                      :title="isNodeCollapsed(opt.value, opt.depth) ? '展开子标签' : '折叠子标签'"
                    >
                      <ChevronRight
                        class="w-3 h-3 transition-transform duration-150"
                        :class="{ 'rotate-90': !isNodeCollapsed(opt.value, opt.depth) }"
                      />
                    </button>
                    <div v-else class="w-3" />

                    <!-- Checkbox Square / CheckSquare -->
                    <component
                      :is="mediaStore.isFacetActive(group.key, opt.value) ? CheckSquare : Square"
                      class="w-3.5 h-3.5 shrink-0 transition-colors"
                      :class="mediaStore.isFacetActive(group.key, opt.value) ? 'text-purple-400' : 'text-gray-600 group-hover:text-gray-400'"
                    />

                    <!-- Label -->
                    <span class="truncate" :title="opt.full_path">{{ opt.label }}</span>
                  </div>

                  <!-- Match count badge -->
                  <span
                    class="text-[10px] font-mono px-1.5 py-0.2 rounded-full shrink-0 ml-1.5 transition-colors"
                    :class="mediaStore.isFacetActive(group.key, opt.value) ? 'bg-purple-500/30 text-purple-200 font-bold' : 'bg-white/5 text-gray-500 group-hover:text-gray-400'"
                  >
                    {{ getFacetMatchCount(group.key, opt.value) }}
                  </span>
                </div>
              </template>

              <!-- Show More / Collapse Toggle for Long Facets -->
              <button
                v-if="getHiddenOptionCount(group) > 0"
                @click.stop="toggleSectionShowAll(group.key)"
                class="w-full py-1.5 px-2 text-[11px] text-gray-400 hover:text-purple-300 hover:bg-white/5 rounded-lg transition-colors flex items-center justify-center gap-1 cursor-pointer mt-0.5"
              >
                <span>{{ isSectionFullyExpanded(group.key) ? '收起部分标签' : `展开其余 ${getHiddenOptionCount(group)} 个标签` }}</span>
                <component :is="isSectionFullyExpanded(group.key) ? ChevronUp : ChevronDown" class="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <!-- Right Main Area: Filter Ribbon + Feed Waterfall Grid -->
      <div class="flex-grow min-w-0">
        <!-- Active Filters Ribbon (Quick Remove Pills) -->
        <div
          v-if="activeFilterList.length > 0"
          class="mb-4 p-3 rounded-2xl border flex flex-wrap items-center gap-2 shadow-sm"
          style="background-color: var(--bg-surface); border-color: var(--border-color);"
        >
          <div class="flex items-center gap-1.5 text-xs font-semibold text-gray-400 mr-1">
            <Filter class="w-3.5 h-3.5 text-purple-400" />
            <span>已生效筛选 ({{ activeFilterList.length }}):</span>
          </div>

          <div
            v-for="flt in activeFilterList"
            :key="`${flt.category}-${flt.value}`"
            class="flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-medium text-white shadow-xs border border-purple-400/40 bg-purple-600/30 backdrop-blur-sm"
          >
            <span class="text-[10px] text-purple-300 font-normal">[{{ flt.categoryName }}]</span>
            <span>{{ flt.value }}</span>
            <button
              @click="mediaStore.toggleFacetFilter(flt.category, flt.value)"
              class="hover:bg-white/20 rounded-full p-0.5 ml-0.5 text-purple-200 hover:text-white transition-colors"
              title="移除此标签"
            >
              <X class="w-3 h-3" />
            </button>
          </div>

          <button
            @click="mediaStore.clearFacetFilters()"
            class="ml-auto text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 px-2.5 py-1 rounded-lg transition-colors flex items-center gap-1"
          >
            <RotateCcw class="w-3 h-3" />
            <span>清空全部</span>
          </button>
        </div>

        <!-- Feed Header Stats -->
        <div class="flex items-center justify-between mb-4 px-1 text-xs text-gray-400">
          <div>
            找到 <span class="font-bold text-white font-mono">{{ displayItems.length }}</span> 项结果
          </div>
          <div v-if="mediaStore.searchQuery" class="text-purple-400">
            包含关键词「{{ mediaStore.searchQuery }}」
          </div>
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
      class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-5"
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
        <div class="relative w-full aspect-[16/10] bg-black/40 overflow-hidden flex items-center justify-center">
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
            <!-- Composite Multi-Media Badges for Series -->
            <template v-if="card.is_series && card.unit_count > 1">
              <span
                v-if="card.audio_count > 0"
                class="flex items-center gap-1 bg-emerald-600/90 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
              >
                <Music class="w-3 h-3" />
                <span>{{ card.audio_count }} 音轨</span>
              </span>
              <span
                v-if="card.video_count > 0"
                class="flex items-center gap-1 bg-blue-600/90 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
              >
                <Video class="w-3 h-3" />
                <span>{{ card.video_count }} 视频</span>
              </span>
              <span
                v-if="card.image_count > 0"
                class="flex items-center gap-1 bg-amber-600/90 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
              >
                <ImageIcon class="w-3 h-3" />
                <span>{{ card.image_count }} 插画</span>
              </span>
              <span
                v-if="!card.audio_count && !card.video_count && !card.image_count"
                class="flex items-center gap-1 bg-purple-600/90 backdrop-blur-md text-[10px] font-semibold text-white px-2 py-0.5 rounded-full shadow"
              >
                <Layers class="w-3 h-3" />
                <span>{{ card.unit_count }} 选集</span>
              </span>
            </template>
            <template v-else>
              <span
                v-if="card.unit_type === 'bundle'"
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
            </template>
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
              <span v-if="card.is_series && card.unit_count > 1 && (card.audio_count > 0 || card.image_count > 0 || card.video_count > 0)" class="text-purple-400 font-mono text-[11px] font-semibold truncate max-w-[200px]">
                <template v-if="card.audio_count > 0 && card.image_count > 0">
                  全 {{ card.audio_count }} 选集 · 附 {{ card.image_count }} 张画册
                </template>
                <template v-else-if="card.audio_count > 0">
                  全 {{ card.audio_count }} 选集 · 连播
                </template>
                <template v-else-if="card.image_count > 0">
                  全 {{ card.image_count }} 张画册
                </template>
                <template v-else-if="card.video_count > 0">
                  全 {{ card.video_count }} 选集 · 视频
                </template>
                <template v-else>
                  全 {{ card.unit_count }} 选集
                </template>
              </span>
              <span v-else class="truncate max-w-[150px]">
                {{ card.collection_name || '散落文件' }}
              </span>
              <span v-if="card.view_count > 0" class="text-gray-500 font-mono">
                {{ card.view_count }} 次浏览
              </span>
            </div>

            <!-- Tag Badges on Card (High-entropy, color-coded, clickable to filter) -->
            <div v-if="getCleanCardTags(card).length > 0" class="flex flex-wrap items-center gap-1 mt-2">
              <button
                v-for="t in getCleanCardTags(card).slice(0, 3)"
                :key="t.id || t.name"
                @click.stop="mediaStore.toggleFacetFilter(t.class_code || 'domain', t.name)"
                class="text-[10px] px-1.5 py-0.5 rounded-md font-medium border transition-colors cursor-pointer"
                :class="getCardTagBadgeClass(t.class_code)"
                :title="`点击按「${t.name}」筛选`"
              >
                {{ t.name }}
              </button>
              <span
                v-if="getCleanCardTags(card).length > 3"
                class="text-[9px] px-1 py-0.5 rounded text-gray-500 hover:text-gray-300 font-mono cursor-help transition-colors"
                :title="getCleanCardTags(card).slice(3).map(t => t.name).join(' · ')"
              >
                +{{ getCleanCardTags(card).length - 3 }}
              </span>
            </div>
          </div>

          <!-- Feedback & Rating Bar (Clean, Minimalist Aesthetics) -->
          <div class="flex items-center justify-between mt-3 pt-2 border-t border-white/5 text-xs">
            <!-- Left: Rating Pill if rated, or subtle hover to rate -->
            <div class="flex items-center gap-1.5">
              <div
                v-if="card.rating > 0"
                class="flex items-center gap-1 text-[11px] font-mono font-bold text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-full border border-amber-400/20"
                :title="`有效评分: ${Number(card.rating).toFixed(1)} 星`"
              >
                <Star class="w-3 h-3 fill-amber-400 text-amber-400" />
                <span>{{ Number(card.rating).toFixed(1) }}</span>
              </div>
              <div
                v-else
                class="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-gray-500 hover:text-amber-400 cursor-pointer"
                @click.stop="(e) => handleAppendRate(e, card, 5)"
                title="点击评 5 星"
              >
                <Star class="w-3.5 h-3.5" />
                <span class="text-[10px]">评分</span>
              </div>
            </div>

            <!-- Right Actions: Favorite Heart & Cooldown Snowflake (Subtle on hover) -->
            <div class="flex items-center gap-1">
              <!-- Cooldown / 听腻了 -->
              <button
                @click.stop="(e) => handleCooldown(e, card)"
                class="p-1 text-gray-500 opacity-0 group-hover:opacity-60 hover:opacity-100 hover:text-sky-400 transition-all rounded-lg hover:bg-white/5"
                title="听腻了 / 冷却 14 天 (沉淀至冷却池，暂不推荐)"
              >
                <Snowflake class="w-3.5 h-3.5 transition-transform active:scale-125" />
              </button>

              <!-- Favorite Heart -->
              <button
                @click.stop="(e) => handleToggleFavorite(e, card)"
                class="p-1 transition-all rounded-lg hover:bg-white/5"
                :class="[
                  card.is_favorite
                    ? 'text-rose-500'
                    : 'text-gray-500 opacity-0 group-hover:opacity-80 hover:opacity-100 hover:text-rose-400'
                ]"
                :title="card.is_favorite ? '已收藏' : '标记喜欢'"
              >
                <Heart
                  :class="[
                    'w-3.5 h-3.5 transition-transform active:scale-125',
                    card.is_favorite ? 'text-rose-500 fill-rose-500 scale-105' : ''
                  ]"
                />
              </button>
            </div>
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

      </div> <!-- End of Right Main Area: flex-grow min-w-0 -->
    </div> <!-- End of Main Flex Layout: flex items-start gap-6 -->

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
