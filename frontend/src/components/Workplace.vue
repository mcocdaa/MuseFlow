<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import { locale, t, tData, tFacet } from '../i18n'
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
  Anchor,
  Music,
  Video,
  Image as ImageIcon,
  Star,
  RefreshCw,
  Users,
  Zap,
  AlertTriangle,
  AlertCircle,
  Compass,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ArrowRight,
  Lightbulb,
  MoreHorizontal
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
  createTag,
  fetchAssetAlgorithmStats,
  syncLibraryChanges,
  reindexLibrary,
  fetchTagSuggestions,
  batchAssignTag
} from '../api'
import PipelineBuilderModal from './PipelineBuilderModal.vue'
import TagManagerModal from './TagManagerModal.vue'
import TaxonomyWorkspaceView from './TaxonomyWorkspaceView.vue'
import AgentMCPModal from './AgentMCPModal.vue'
import LensTreeNode from './LensTreeNode.vue'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const selectedItem = ref(null)
const newSupersetName = ref('')
const showNewSupersetInput = ref(false)
const showPipelineModal = ref(false)
const showTagManagerModal = ref(false)
const showMCPModal = ref(false)
const showMoreTools = ref(false)
const showAlgoDetails = ref(false)

// Tag Inspector & Autocomplete
const selectedItemTags = ref([])
const allTagsFlat = ref([])
const isAddingTag = ref(false)
const tagSearchQuery = ref('')
const tagInputRef = ref(null)

// Smart Tag Suggestions & Quick Triage
const unitSuggestions = ref(null)
const loadingSuggestions = ref(false)

// Batch Selection & Batch Tagging Mode
const isBatchMode = ref(false)
const selectedIds = ref(new Set())
const showBatchSupersetModal = ref(false)
const batchNewSupersetName = ref('')
const showBatchTagModal = ref(false)
const batchSelectedTagId = ref(null)
const batchIsPrimaryLanding = ref(true)
const batchTagCategory = ref('creator')
const batchTagSearchQuery = ref('')
const isSyncing = ref(false)

const handleSyncChanges = async () => {
  isSyncing.value = true
  playerStore.showToast(t('workplace.toastSyncing'))
  try {
    const res = await syncLibraryChanges()
    if (res.status === 'success') {
      const added = res.added_units || 0
      const pruned = res.pruned_units || 0
      playerStore.showToast(t('workplace.toastSyncSuccess', { added, pruned }))
      await Promise.all([
        mediaStore.loadWorkplaceItems(),
        mediaStore.loadCollections(),
        mediaStore.loadFeed()
      ])
    } else {
      playerStore.showToast(t('workplace.toastSyncFailed') + (res.message || t('workplace.unknownError')))
    }
  } catch (err) {
    playerStore.showToast(t('workplace.toastSyncError') + (err.response?.data?.detail || err.message))
  } finally {
    isSyncing.value = false
  }
}

const handleReindexAll = async () => {
  if (!confirm(t('workplace.confirmReindex'))) {
    return
  }
  isSyncing.value = true
  playerStore.showToast(t('workplace.toastReindexing'))
  try {
    const res = await reindexLibrary()
    if (res.status === 'success') {
      const added = res.added_units || 0
      playerStore.showToast(t('workplace.toastReindexSuccess', { added }))
      await Promise.all([
        mediaStore.loadWorkplaceItems(),
        mediaStore.loadCollections(),
        mediaStore.loadFeed()
      ])
    } else {
      playerStore.showToast(t('workplace.toastReindexFailed') + (res.message || t('workplace.unknownError')))
    }
  } catch (err) {
    playerStore.showToast(t('workplace.toastReindexError') + (err.response?.data?.detail || err.message))
  } finally {
    isSyncing.value = false
  }
}

const handleGlobalKeydown = (e) => {
  if (e.key === 'Escape') {
    if (showMoreTools.value) {
      showMoreTools.value = false
    } else if (selectedItem.value) {
      selectedItem.value = null
    }
  }
}

onMounted(() => {
  mediaStore.loadWorkplaceItems()
  mediaStore.loadFacetSummary()
  loadAllTags()
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
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

const itemAlgorithmStats = ref(null)
const loadingStats = ref(false)

const loadItemAlgorithmStats = async (unitId) => {
  if (!unitId) {
    itemAlgorithmStats.value = null
    return
  }
  loadingStats.value = true
  try {
    const stats = await fetchAssetAlgorithmStats(unitId)
    itemAlgorithmStats.value = stats
  } catch (e) {
    console.error('Failed to load algorithm stats:', e)
    itemAlgorithmStats.value = null
  } finally {
    loadingStats.value = false
  }
}

const handleWorkplaceAppendRate = async (stars) => {
  if (!selectedItem.value) return
  const updated = await mediaStore.updateRating(selectedItem.value.id, stars)
  if (updated && updated.rating !== undefined) {
    selectedItem.value.rating = updated.rating
    if (updated.composite_score !== undefined) {
      selectedItem.value.composite_score = updated.composite_score
    }
  }
  await loadItemAlgorithmStats(selectedItem.value.id)
  playerStore.showToast(t('workplace.toastRateSuccess', { stars, rating: Number(selectedItem.value.rating).toFixed(1) }))
}

watch(selectedItem, () => {
  isAddingTag.value = false
  tagSearchQuery.value = ''
  loadSelectedItemTags()
  if (selectedItem.value) {
    loadItemAlgorithmStats(selectedItem.value.id)
    loadTagSuggestions(selectedItem.value.id)
  } else {
    itemAlgorithmStats.value = null
    unitSuggestions.value = null
  }
})

const loadTagSuggestions = async (unitId) => {
  if (!unitId) return
  loadingSuggestions.value = true
  try {
    const data = await fetchTagSuggestions(unitId)
    unitSuggestions.value = data
  } catch (e) {
    console.error('Failed to load tag suggestions:', e)
    unitSuggestions.value = null
  } finally {
    loadingSuggestions.value = false
  }
}

const handleQuickAssignSuggestion = async (suggested) => {
  if (!selectedItem.value) return
  try {
    const classCode = suggested.class_code || suggested.class
    const hasLandingForClass = selectedItemTags.value.some(
      t => t.class_code === classCode && t.is_primary_landing
    )
    const isPrimary = !hasLandingForClass
    await assignTag(selectedItem.value.id, {
      tag_id: suggested.tag_id || suggested.id,
      is_primary_landing: isPrimary,
      confidence: suggested.confidence || 1.0,
    })
    const tagName = tData(suggested.tag_name || suggested.name)
    playerStore.showToast(`${t('workplace.toastQuickTagged', { name: tagName })}${isPrimary ? t('workplace.toastPrimaryLandingSuffix') : ''}`)
    await Promise.all([
      loadSelectedItemTags(),
      loadTagSuggestions(selectedItem.value.id),
      mediaStore.loadFacetSummary()
    ])
  } catch (err) {
    playerStore.showToast(t('workplace.toastTagFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleNextUntaggedItem = () => {
  if (!displayItems.value || displayItems.value.length === 0) return
  const currentIdx = displayItems.value.findIndex(u => u.id === selectedItem.value?.id)
  const len = displayItems.value.length
  const targetFacet = mediaStore.selectedMissingFacet || 'creator'

  for (let step = 1; step <= len; step++) {
    const nextIdx = (currentIdx + step) % len
    const candidate = displayItems.value[nextIdx]
    const hasTargetFacet = candidate.tags?.some(t => t.class_code === targetFacet)
    if (!hasTargetFacet) {
      selectedItem.value = candidate
      playerStore.showToast(t('workplace.toastNextUntagged', { facet: tFacet(targetFacet, targetFacet) }))
      return
    }
  }
  playerStore.showToast(t('workplace.toastAllTagged'))
}

const handlePrevItem = () => {
  if (!displayItems.value || displayItems.value.length === 0) return
  const currentIdx = displayItems.value.findIndex(u => u.id === selectedItem.value?.id)
  const prevIdx = (currentIdx - 1 + displayItems.value.length) % displayItems.value.length
  selectedItem.value = displayItems.value[prevIdx]
}

const handleNextItem = () => {
  if (!displayItems.value || displayItems.value.length === 0) return
  const currentIdx = displayItems.value.findIndex(u => u.id === selectedItem.value?.id)
  const nextIdx = (currentIdx + 1) % displayItems.value.length
  selectedItem.value = displayItems.value[nextIdx]
}

// Batch Tagging
const openBatchTagModal = () => {
  if (!selectedIds.value.size) return
  batchSelectedTagId.value = null
  batchIsPrimaryLanding.value = true
  batchTagSearchQuery.value = ''
  if (!allTagsFlat.value.length) {
    loadAllTags()
  }
  showBatchTagModal.value = true
}

const batchFilteredTags = computed(() => {
  let list = allTagsFlat.value || []
  if (batchTagCategory.value) {
    list = list.filter(t => t.class_code === batchTagCategory.value)
  }
  if (batchTagSearchQuery.value.trim()) {
    const q = batchTagSearchQuery.value.trim().toLowerCase()
    list = list.filter(t => t.name.toLowerCase().includes(q))
  }
  return list.slice(0, 30)
})

const handleConfirmBatchTag = async () => {
  if (!batchSelectedTagId.value || !selectedIds.value.size) return
  try {
    const ids = Array.from(selectedIds.value)
    const tag = allTagsFlat.value.find(t => t.id === batchSelectedTagId.value)
    const res = await batchAssignTag({
      unit_ids: ids,
      tag_id: batchSelectedTagId.value,
      is_primary_landing: batchIsPrimaryLanding.value,
    })
    playerStore.showToast(t('workplace.toastBatchTagSuccess', { count: res.assigned_count, name: tData(tag?.name || '') }))
    showBatchTagModal.value = false
    selectedIds.value = new Set()
    isBatchMode.value = false
    await Promise.all([
      mediaStore.loadWorkplaceItems(),
      mediaStore.loadFacetSummary()
    ])
  } catch (err) {
    playerStore.showToast(t('workplace.toastBatchTagFailed') + (err.response?.data?.detail || err.message))
  }
}

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
    playerStore.showToast(t('workplace.toastTagLinked', { name: tData(tag.name) }))
  } catch (err) {
    playerStore.showToast(t('workplace.toastTagLinkFailed') + (err.response?.data?.detail || err.message))
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
    playerStore.showToast(t('workplace.toastTagCreatedSuccess'))
  } catch (err) {
    playerStore.showToast(t('workplace.toastTagFailed') + (err.response?.data?.detail || err.message))
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
    playerStore.showToast(newStatus ? t('workplace.toastSetPrimaryLanding', { name: tData(tag.name) }) : t('workplace.toastUnsetPrimaryLanding', { name: tData(tag.name) }))
  } catch (err) {
    playerStore.showToast(t('workplace.toastSetLandingFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleRemoveTag = async (tag) => {
  if (!selectedItem.value) return
  try {
    await removeTag(selectedItem.value.id, tag.tag_id)
    await loadSelectedItemTags()
    playerStore.showToast(t('workplace.toastTagRemoved', { name: tData(tag.name) }))
  } catch (err) {
    playerStore.showToast(t('workplace.toastTagRemoveFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleTagChanged = async () => {
  await Promise.all([
    loadAllTags(),
    loadSelectedItemTags(),
    mediaStore.loadWorkplaceItems(),
  ])
}

const collectionMediaType = ref('all') // 'all' | 'audio' | 'image' | 'video'

const facetSummaryMap = computed(() => {
  const map = {}
  for (const item of (mediaStore.facetSummary || [])) {
    map[item.code] = item
  }
  return map
})

const vacuumFacets = computed(() => {
  if (!mediaStore.facetSummary) return []
  return [...mediaStore.facetSummary]
    .filter(f => f.missing_units > 0 && f.tagged_units > 0)
    .sort((a, b) => (b.is_required ? 1 : 0) - (a.is_required ? 1 : 0))
})

const totalUntaggedCount = computed(() => {
  if (!vacuumFacets.value || vacuumFacets.value.length === 0) return 0
  const required = vacuumFacets.value.filter(f => f.is_required)
  if (required.length > 0) {
    return Math.max(...required.map(f => f.missing_units), 0)
  }
  return vacuumFacets.value[0]?.missing_units || 0
})

const projectableFacets = computed(() => {
  if (!mediaStore.facetSummary) return []
  const order = ['domain', 'character', 'interaction', 'spec', 'creator', 'va', 'workflow', 'media_kind']
  return [...mediaStore.facetSummary].sort((a, b) => {
    const ia = order.indexOf(a.code)
    const ib = order.indexOf(b.code)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
})

const batchCategoryTabs = computed(() => {
  const dynamicTabs = projectableFacets.value
    .filter(f => f.code !== 'media_kind')
    .map(f => ({ code: f.code, label: tFacet(f.code, f.display_name) }))
  return [...dynamicTabs, { code: '', label: t('workplace.allTagsTab') }]
})

const WORKPLACE_MEDIA_KIND_NAMES = new Set(['Audio', 'Video', 'Image', 'Bundle', '\u97f3\u9891', '\u89c6\u9891', '\u56fe\u7247', '\u590d\u5408\u5a92\u4f53'])

const parentTagSetWorkplace = computed(() => {
  const s = new Set()
  for (const t of (allTagsFlat.value || [])) {
    if (t.parent_name) s.add(t.parent_name)
  }
  return s
})

const getTagBadgeStyle = (classCode) => {
  switch (classCode) {
    case 'character':
    case 'guest':
      return 'bg-pink-500/12 text-pink-300 border-pink-500/25'
    case 'interaction':
    case 'difficulty':
      return 'bg-orange-500/12 text-orange-300 border-orange-500/25'
    case 'domain':
    case 'genre':
    case 'topic':
    case 'project':
    case 'tech_stack':
      return 'bg-purple-500/12 text-purple-300 border-purple-500/25'
    case 'va':
    case 'release_year':
    case 'gear':
      return 'bg-amber-500/12 text-amber-300 border-amber-500/25'
    case 'spec':
    case 'album':
      return 'bg-sky-500/12 text-sky-300 border-sky-500/25'
    case 'creator':
    case 'artist':
    case 'host':
    case 'client':
    case 'instructor':
      return 'bg-teal-500/12 text-teal-300 border-teal-500/25'
    case 'workflow':
      return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
    default:
      return 'bg-white/5 text-gray-300 border-white/10'
  }
}

const getRowCleanTags = (item) => {
  if (!item || !item.tags || !Array.isArray(item.tags)) return []
  const nonMedia = item.tags.filter(t => t.name && t.class_code !== 'media_kind' && !WORKPLACE_MEDIA_KIND_NAMES.has(t.name))
  const hasSpecific = nonMedia.some(t => !parentTagSetWorkplace.value.has(t.name) && t.class_code !== 'workflow')
  const filtered = nonMedia.filter(t => {
    if (hasSpecific && parentTagSetWorkplace.value.has(t.name) && (t.full_path || t.name).indexOf(' / ') === -1) {
      return false
    }
    return true
  })
  const priority = { character: 1, interaction: 2, domain: 3, va: 4, spec: 5, creator: 6, workflow: 7 }
  return filtered.sort((a, b) => (priority[a.class_code] || 5) - (priority[b.class_code] || 5))
}

const currentLensContext = computed(() => {
  if (mediaStore.selectedMissingFacet) {
    const f = mediaStore.facetSummary?.find(x => x.code === mediaStore.selectedMissingFacet)
    const facetName = tFacet(mediaStore.selectedMissingFacet, f ? f.display_name : mediaStore.selectedMissingFacet)
    return {
      title: `${t('workplace.missingPrefix', { name: facetName })}`,
      is_unassigned: true,
      facet_code: mediaStore.selectedMissingFacet
    }
  }
  if (mediaStore.selectedLensTagId) {
    const findInTree = (nodes) => {
      if (!nodes) return null
      for (const n of nodes) {
        if (n.id === mediaStore.selectedLensTagId) return n
        const sub = findInTree(n.children)
        if (sub) return sub
      }
      return null
    }
    const node = findInTree(mediaStore.lensTreeData?.tree)
    const rawName = node?.display_path || node?.name || allTagsFlat.value.find(t => t.id === mediaStore.selectedLensTagId)?.name || `#${mediaStore.selectedLensTagId}`
    return {
      title: tData(rawName),
      is_unassigned: false,
      tag_id: mediaStore.selectedLensTagId
    }
  }
  return null
})

const handleSelectCollection = (colId) => {
  mediaStore.selectedCollectionId = colId
  mediaStore.selectedSupersetId = null
  mediaStore.selectedLensTagId = null
  mediaStore.selectedMissingFacet = null
  collectionMediaType.value = 'all'
  selectedIds.value = new Set()
  mediaStore.loadWorkplaceItems()
}

const handleSelectSuperset = (supersetId) => {
  mediaStore.selectedSupersetId = supersetId
  mediaStore.selectedCollectionId = null
  mediaStore.selectedLensTagId = null
  mediaStore.selectedMissingFacet = null
  collectionMediaType.value = 'all'
  selectedIds.value = new Set()
  mediaStore.loadWorkplaceItems()
}

const handleSelectAllRoot = () => {
  mediaStore.selectedCollectionId = null
  mediaStore.selectedSupersetId = null
  mediaStore.selectedLensTagId = null
  mediaStore.selectedMissingFacet = null
  collectionMediaType.value = 'all'
  selectedIds.value = new Set()
  mediaStore.loadWorkplaceItems()
}

const handleSwitchLens = async (lensKey) => {
  collectionMediaType.value = 'all'
  selectedIds.value = new Set()
  await mediaStore.switchLens(lensKey)
}

const handleSelectLensNode = async (node) => {
  collectionMediaType.value = 'all'
  selectedIds.value = new Set()
  await mediaStore.selectLensNode(node)
}

const handleToggleMissingFacet = async (facetCode) => {
  collectionMediaType.value = 'all'
  selectedIds.value = new Set()
  await mediaStore.toggleMissingFacet(facetCode)
}

const currentSuperset = computed(() => {
  return mediaStore.supersets.find(s => s.id === mediaStore.selectedSupersetId)
})

const currentCollection = computed(() => {
  return mediaStore.collections.find(c => c.id === mediaStore.selectedCollectionId)
})

const handlePlayCollectionAll = () => {
  if (!displayItems.value.length) return
  const audioTracks = displayItems.value.filter(u => isAudioUnit(u))
  const videoTracks = displayItems.value.filter(u => u.unit_type === 'video' || u.unit_type === 'bundle')
  const imageTracks = displayItems.value.filter(u => u.unit_type === 'image')

  if (audioTracks.length > 0) {
    playerStore.openAudioModal(audioTracks[0], audioTracks, true, imageTracks)
  } else if (videoTracks.length > 0) {
    playerStore.openVideo(videoTracks[0], videoTracks, true)
  } else if (imageTracks.length > 0) {
    playerStore.openImage(imageTracks[0], imageTracks, true)
  }
}

const handleEnqueueCollection = () => {
  const audioTracks = displayItems.value.filter(u => isAudioUnit(u))
  const toAdd = audioTracks.length > 0 ? audioTracks : displayItems.value
  playerStore.addMultipleToBgQueue(toAdd)
  const colName = currentCollection.value?.name ? tData(currentCollection.value.name) : ''
  playerStore.showToast(t('workplace.toastEnqueuedCollection', { name: colName, count: toAdd.length }))
}

const handleCreateSuperset = async () => {
  if (!newSupersetName.value.trim()) return
  try {
    const created = await createSuperset({ name: newSupersetName.value.trim() })
    playerStore.showToast(t('workplace.toastSupersetCreated', { name: tData(created.name) }))
    newSupersetName.value = ''
    showNewSupersetInput.value = false
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast(t('workplace.toastSupersetCreateFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleAddToSuperset = async (supersetId) => {
  if (!selectedItem.value) return
  try {
    await addItemToSuperset(supersetId, selectedItem.value.id)
    playerStore.showToast(t('workplace.toastAddedToSuperset', { title: tData(selectedItem.value.title) }))
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast(t('workplace.toastAddSupersetFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleDeleteSuperset = async (sup, e) => {
  e?.stopPropagation()
  if (!confirm(t('workplace.confirmDeleteSuperset', { name: tData(sup.name) }))) return
  try {
    await deleteSuperset(sup.id)
    playerStore.showToast(t('workplace.toastSupersetDeleted', { name: tData(sup.name) }))
    if (mediaStore.selectedSupersetId === sup.id) {
      mediaStore.selectedSupersetId = null
      await mediaStore.loadWorkplaceItems()
    }
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast(t('workplace.toastSupersetDeleteFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleRemoveFromCurrentSuperset = async (item, e) => {
  e?.stopPropagation()
  if (!mediaStore.selectedSupersetId) return
  try {
    await removeItemFromSuperset(mediaStore.selectedSupersetId, item.id)
    playerStore.showToast(t('workplace.toastRemovedFromSuperset', { title: tData(item.title) }))
    await Promise.all([
      mediaStore.loadWorkplaceItems(),
      mediaStore.loadSupersets()
    ])
    if (selectedItem.value?.id === item.id) {
      selectedItem.value = null
    }
  } catch (err) {
    playerStore.showToast(t('workplace.toastRemoveSupersetFailed') + (err.response?.data?.detail || err.message))
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
    playerStore.showToast(t('workplace.toastBatchAddedSuperset', { count: ids.length, name: tData(superset.name) }))
    await mediaStore.loadSupersets()
    showBatchSupersetModal.value = false
    selectedIds.value = new Set()
    isBatchMode.value = false
  } catch (err) {
    playerStore.showToast(t('workplace.toastBatchAddFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleBatchCreateAndAddSuperset = async () => {
  if (!batchNewSupersetName.value.trim() || !selectedIds.value.size) return
  try {
    const newSup = await createSuperset({ name: batchNewSupersetName.value.trim() })
    const ids = Array.from(selectedIds.value)
    await addItemsBatchToSuperset(newSup.id, ids)
    playerStore.showToast(t('workplace.toastBatchCreatedSuperset', { name: tData(newSup.name), count: ids.length }))
    batchNewSupersetName.value = ''
    showBatchSupersetModal.value = false
    selectedIds.value = new Set()
    isBatchMode.value = false
    await mediaStore.loadSupersets()
  } catch (err) {
    playerStore.showToast(t('workplace.toastSupersetCreateFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleSearch = () => {
  mediaStore.loadWorkplaceItems()
}

const displayItems = computed(() => {
  let items = mediaStore.workplaceItems
  if (currentCollection.value && collectionMediaType.value !== 'all') {
    if (collectionMediaType.value === 'audio') {
      items = items.filter(u => isAudioUnit(u))
    } else if (collectionMediaType.value === 'video') {
      items = items.filter(u => u.unit_type === 'video' || u.unit_type === 'bundle')
    } else if (collectionMediaType.value === 'image') {
      items = items.filter(u => u.unit_type === 'image')
    }
  }
  if (!mediaStore.searchQuery.trim()) return items
  const q = mediaStore.searchQuery.trim().toLowerCase()
  return items.filter(u =>
    (u.title && u.title.toLowerCase().includes(q)) ||
    (u.title && tData(u.title).toLowerCase().includes(q)) ||
    (u.collection_name && u.collection_name.toLowerCase().includes(q)) ||
    (u.collection_name && tData(u.collection_name).toLowerCase().includes(q))
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
  if (item.dynamic_attributes?.tracks?.length > 1 || item.dynamic_attributes?.is_atomic_work) {
    if (isAudioUnit(item)) {
      playerStore.openAudioModal(item, [item], false)
    } else if (item.unit_type === 'video' || item.unit_type === 'bundle') {
      playerStore.openVideo(item, [item], false)
    } else if (item.unit_type === 'image') {
      playerStore.openImage(item, [item], false)
    }
    return
  }
  let seriesPlaylist = []
  if (item.collection_id) {
    seriesPlaylist = displayItems.value.filter(u => u.collection_id === item.collection_id)
  } else if (mediaStore.selectedCollectionId) {
    seriesPlaylist = displayItems.value.filter(u => u.collection_id === mediaStore.selectedCollectionId)
  }
  if (!seriesPlaylist.length) {
    seriesPlaylist = displayItems.value.length > 0 ? displayItems.value : [item]
  }
  seriesPlaylist.sort((a, b) => (a.title || '').localeCompare(b.title || '', undefined, { numeric: true, sensitivity: 'base' }))

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

const handleBackFromTaxonomy = async () => {
  mediaStore.workplaceView = 'assets'
  await handleTagChanged()
}

const handleJumpFromTaxonomyToTag = async ({ classCode, tagNode }) => {
  mediaStore.workplaceView = 'assets'
  await handleTagChanged()
  if (classCode && mediaStore.activeLens !== classCode) {
    await mediaStore.switchLens(classCode)
  }
  if (tagNode) {
    await mediaStore.selectLensNode(tagNode)
  }
}

const handleJumpFromTaxonomyToMissing = async (facetCode) => {
  mediaStore.workplaceView = 'assets'
  await handleTagChanged()
  if (facetCode) {
    if (mediaStore.activeLens !== facetCode) {
      await mediaStore.switchLens(facetCode)
    }
    await mediaStore.toggleMissingFacet(facetCode)
  }
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 lg:px-8 py-6">
    <!-- Dedicated Full-Page Taxonomy & Tag Management Workspace -->
    <TaxonomyWorkspaceView
      v-if="mediaStore.workplaceView === 'taxonomy'"
      :initialClassCode="mediaStore.taxonomyInitialClassCode"
      :initialTagId="mediaStore.taxonomyInitialTagId"
      @back-to-assets="handleBackFromTaxonomy"
      @jump-to-tag="handleJumpFromTaxonomyToTag"
      @jump-to-missing="handleJumpFromTaxonomyToMissing"
    />

    <!-- Standard 3-Column Asset Browser Workspace -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[700px]">
      <!-- Left Sidebar: Collections, Supersets & Virtual Lens -->
      <aside
        class="lg:col-span-3 border rounded-2xl p-4 flex flex-col gap-4 transition-colors"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Mode Switch: 物理目录 vs 分类透镜 -->
        <div class="flex items-center bg-black/25 p-1 rounded-xl border border-white/5 select-none">
          <button
            @click="handleSwitchLens('physical')"
            :class="[
              'flex-1 py-1.5 px-2 text-xs font-medium rounded-lg transition-all flex items-center justify-center gap-1.5 cursor-pointer whitespace-nowrap',
              mediaStore.activeLens === 'physical'
                ? 'bg-purple-600/30 text-purple-200 border border-purple-500/30 shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            :title="t('workplace.foldersTip')"
          >
            <Folder class="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span>{{ t('workplace.folders') }}</span>
          </button>

          <button
            @click="handleSwitchLens(mediaStore.activeLens === 'physical' ? (projectableFacets[0]?.code || 'domain') : mediaStore.activeLens)"
            :class="[
              'flex-1 py-1.5 px-2 text-xs font-medium rounded-lg transition-all flex items-center justify-center gap-1.5 cursor-pointer whitespace-nowrap',
              mediaStore.activeLens !== 'physical'
                ? 'bg-purple-600/30 text-purple-200 border border-purple-500/30 shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            ]"
            :title="t('workplace.taxonomyTip')"
          >
            <Tag class="w-3.5 h-3.5 text-purple-400 shrink-0" />
            <span>{{ t('workplace.taxonomy') }}</span>
          </button>
        </div>

        <!-- If Lens mode: 2-Column Grid Facet Selector -->
        <div v-if="mediaStore.activeLens !== 'physical'" class="space-y-1.5">
          <div class="flex items-center justify-between px-1">
            <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              {{ t('workplace.dimensions', { count: projectableFacets.length }) }}
            </label>
            <button
              @click="mediaStore.openTaxonomyWorkspace(mediaStore.activeLens)"
              class="text-[10px] text-purple-400 hover:text-purple-300 font-medium cursor-pointer"
            >
              {{ t('workplace.manageCenter') }}
            </button>
          </div>
          <div class="grid grid-cols-2 gap-1.5 py-0.5">
            <button
              v-for="facet in projectableFacets"
              :key="facet.code"
              @click="handleSwitchLens(facet.code)"
              :class="[
                'px-2.5 py-1.5 text-xs rounded-xl font-medium truncate transition-all border cursor-pointer flex items-center justify-between gap-1.5',
                mediaStore.activeLens === facet.code
                  ? 'bg-purple-600/30 text-purple-200 border-purple-500/40 shadow-xs'
                  : 'bg-white/5 border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10'
              ]"
              :title="`${tFacet(facet.code, facet.display_name)} (${facet.tag_count || 0})`"
            >
              <div class="flex items-center gap-1.5 min-w-0 truncate">
                <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: facet.color || '#a855f7' }" />
                <span class="truncate">{{ tFacet(facet.code, facet.display_name) }}</span>
              </div>
              <span class="text-[10px] font-mono opacity-60 shrink-0">{{ facet.tag_count || '' }}</span>
            </button>
          </div>
        </div>

        <!-- All Root Items & Untagged Quick Filter -->
        <div class="space-y-1">
          <button
            data-testid="workplace-all-media-btn"
            @click="handleSelectAllRoot"
            :class="[
              'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-colors text-left cursor-pointer',
              !mediaStore.selectedCollectionId && !mediaStore.selectedSupersetId && !mediaStore.selectedLensTagId && !mediaStore.selectedMissingFacet
                ? 'bg-purple-600/30 text-purple-200 border border-purple-500/30'
                : 'text-gray-300 hover:bg-white/5'
            ]"
          >
            <span class="flex items-center gap-2 whitespace-nowrap">
              <HardDrive class="w-4 h-4 text-purple-400 shrink-0" />
              <span>{{ t('workplace.allMedia') }}</span>
            </span>
            <span class="text-[10px] text-gray-400 bg-white/5 px-2 py-0.5 rounded-full font-mono">
              {{ mediaStore.facetSummary?.[0]?.total_units || mediaStore.workplaceItems.length }}
            </span>
          </button>

          <!-- Needs Triage / Untagged (待整理作品) -->
          <button
            v-if="totalUntaggedCount > 0"
            @click="handleToggleMissingFacet(vacuumFacets[0]?.code)"
            :class="[
              'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-colors text-left cursor-pointer',
              mediaStore.selectedMissingFacet
                ? 'bg-amber-500/25 text-amber-200 border border-amber-500/40 shadow-sm'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
            ]"
            :title="t('workplace.unorganizedTip')"
          >
            <span class="flex items-center gap-2 whitespace-nowrap">
              <Clock class="w-4 h-4 text-amber-400 shrink-0" />
              <span>{{ t('workplace.unorganized') }}</span>
            </span>
            <span class="text-[10px] text-amber-300 bg-amber-500/20 px-2 py-0.5 rounded-full font-mono font-semibold">
              {{ totalUntaggedCount }}
            </span>
          </button>
        </div>

        <!-- IF Physical Directory Mode -->
        <template v-if="mediaStore.activeLens === 'physical'">
          <!-- Collections / Folders Tree -->
          <div>
            <div class="flex items-center justify-between text-xs font-semibold text-gray-400 mb-2.5 px-1">
              <span class="flex items-center gap-1.5 uppercase tracking-wider text-[11px] whitespace-nowrap">
                <Folder class="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span>{{ t('workplace.collections') }}</span>
              </span>
              <span class="text-[11px] text-gray-500">{{ mediaStore.collections.length }}</span>
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
                  class="flex-grow min-w-0 flex items-center justify-between px-2.5 py-1.5 text-xs"
                  :title="tData(col.name)"
                >
                  <span class="truncate flex items-center gap-2 min-w-0">
                    <FolderOpen class="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span class="truncate">{{ tData(col.name) }}</span>
                  </span>
                  <span class="text-[10px] text-gray-500 shrink-0 bg-white/5 px-1.5 py-0.5 rounded-full ml-1.5">
                    {{ col.unit_count }}
                  </span>
                </button>

                <button
                  v-if="col.folder_path"
                  @click.stop="mediaStore.openPhysicalOrganizer(col.folder_path)"
                  class="p-1.5 text-amber-400 hidden group-hover/col:inline-flex hover:text-amber-200 transition-opacity shrink-0"
                >
                  <FolderCog class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          <!-- Virtual Supersets -->
          <div>
            <div class="flex items-center justify-between text-xs font-semibold text-gray-400 mb-2.5 px-1">
              <span class="flex items-center gap-1.5 uppercase tracking-wider text-[11px] whitespace-nowrap">
                <Sparkles class="w-3.5 h-3.5 text-pink-400 shrink-0" />
                <span>{{ t('workplace.supersets') }}</span>
              </span>
              <button
                @click="showNewSupersetInput = !showNewSupersetInput"
                class="p-1 hover:text-white text-gray-400 rounded transition-colors"
                :title="t('workplace.newSupersetTip')"
              >
                <Plus class="w-3.5 h-3.5" />
              </button>
            </div>

            <!-- New Superset input -->
            <div v-if="showNewSupersetInput" class="mb-2 flex items-center gap-1.5">
              <input
                v-model="newSupersetName"
                type="text"
                :placeholder="t('workplace.newSupersetPlaceholder')"
                class="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500/50"
                @keyup.enter="handleCreateSuperset"
              />
              <button
                @click="handleCreateSuperset"
                class="bg-pink-600 hover:bg-pink-500 text-white text-xs px-2 py-1 rounded-lg shrink-0"
              >
                {{ t('workplace.confirmBtn') }}
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
                  class="flex-grow min-w-0 flex items-center justify-between px-2.5 py-1.5 text-xs"
                  :title="tData(sup.name)"
                >
                  <span class="truncate flex items-center gap-2 min-w-0">
                    <Tag class="w-3.5 h-3.5 text-pink-400 shrink-0" />
                    <span class="truncate">{{ tData(sup.name) }}</span>
                  </span>
                  <span class="text-[10px] text-gray-500 shrink-0 bg-white/5 px-1.5 py-0.5 rounded-full ml-1.5">
                    {{ sup.unit_count }}
                  </span>
                </button>

                <!-- Quick Play / Slideshow actions on hover -->
                <div class="hidden group-hover/sup:flex items-center gap-0.5 pr-1 shrink-0">
                  <button
                    @click.stop="playerStore.loadSuperset(sup.id, 'bg', true)"
                    class="p-1 text-purple-300 hover:text-white hover:bg-white/10 rounded transition-colors"
                  >
                    <Play class="w-3 h-3 fill-current" />
                  </button>
                  <button
                    @click.stop="playerStore.loadSuperset(sup.id, 'fg', true)"
                    class="p-1 text-pink-300 hover:text-white hover:bg-white/10 rounded transition-colors"
                  >
                    <Tv class="w-3 h-3" />
                  </button>
                  <button
                    @click.stop="handleDeleteSuperset(sup, $event)"
                    class="p-1 text-red-400 hover:text-red-200 hover:bg-red-500/20 rounded transition-colors"
                  >
                    <Trash2 class="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- IF Dynamic Virtual Lens Mode (domain / creator / workflow) -->
        <template v-else>
          <div class="flex flex-col flex-grow min-h-0">
            <!-- Lens Metadata & Coverage Header -->
            <div class="flex items-center justify-between text-xs font-semibold text-gray-300 mb-2.5 px-1">
              <div class="flex items-center gap-2 min-w-0">
                <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: mediaStore.lensTreeData?.color || '#a855f7' }" />
                <span class="truncate font-semibold">{{ tFacet(mediaStore.activeLens, mediaStore.lensTreeData?.display_name || t('workplace.taxonomy')) }}</span>
              </div>
              <div class="flex items-center gap-1.5 shrink-0">
                <span
                  class="text-[10px] px-2 py-0.5 rounded-full font-mono whitespace-nowrap"
                  :class="[
                    (mediaStore.lensTreeData?.coverage_percent || 0) >= 80
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  ]"
                >
                  {{ t('workplace.coverage', { pct: mediaStore.lensTreeData?.coverage_percent ?? 0 }) }}
                </span>
                <button
                  @click="mediaStore.loadLensTree(mediaStore.activeLens)"
                  class="text-gray-400 hover:text-white p-1 rounded transition-colors"
                >
                  <RefreshCw :class="['w-3.5 h-3.5', mediaStore.lensTreeLoading ? 'animate-spin' : '']" />
                </button>
              </div>
            </div>

            <!-- Loading Spinner -->
            <div v-if="mediaStore.lensTreeLoading" class="py-8 flex justify-center items-center text-xs text-purple-300">
              <RefreshCw class="w-4 h-4 animate-spin mr-2" />
              <span>{{ t('workplace.buildingLens') }}</span>
            </div>

            <div v-else class="flex flex-col gap-2 flex-grow overflow-y-auto max-h-[560px] pr-1">
              <!-- Unassigned / Untagged Node (待整理分类节点) -->
              <div
                v-if="mediaStore.lensTreeData?.unassigned_node && mediaStore.lensTreeData.unassigned_node.direct_count > 0"
                class="mb-1"
              >
                <LensTreeNode
                  :node="mediaStore.lensTreeData.unassigned_node"
                  :depth="0"
                  :selectedTagId="mediaStore.selectedLensTagId"
                  :selectedMissingFacet="mediaStore.selectedMissingFacet"
                  :activeClassCode="mediaStore.activeLens"
                  @select="handleSelectLensNode"
                />
              </div>

              <!-- Hierarchical Tag Tree Nodes -->
              <div class="space-y-0.5">
                <LensTreeNode
                  v-for="rootNode in (mediaStore.lensTreeData?.tree || [])"
                  :key="rootNode.id"
                  :node="rootNode"
                  :depth="0"
                  :selectedTagId="mediaStore.selectedLensTagId"
                  :selectedMissingFacet="mediaStore.selectedMissingFacet"
                  :activeClassCode="mediaStore.activeLens"
                  @select="handleSelectLensNode"
                />
              </div>
            </div>
          </div>
        </template>
      </aside>

      <!-- Main Explorer Area -->
      <main
        :class="selectedItem ? 'lg:col-span-6' : 'lg:col-span-9'"
        class="border rounded-2xl p-4 flex flex-col transition-all duration-200"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Top Toolbar (极简纯净、自解释图标 + Tooltip、响应式留白) -->
        <div class="flex items-center gap-2 sm:gap-3 mb-4 select-none">
          <!-- Search input with clear button -->
          <div class="relative flex-grow min-w-[160px]">
            <Search class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              v-model="mediaStore.searchQuery"
              @input="handleSearch"
              type="text"
              :placeholder="t('workplace.searchPlaceholder')"
              class="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-8 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 transition-colors"
            />
            <button
              v-if="mediaStore.searchQuery"
              @click="mediaStore.searchQuery = ''; handleSearch()"
              class="absolute right-2.5 top-2.5 text-gray-400 hover:text-white transition-colors"
              :title="t('workplace.clearSearch')"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Quick Filter Segment: 全部 vs 待整理 -->
          <div class="flex items-center bg-black/25 p-1 rounded-xl border border-white/5 shrink-0">
            <button
              @click="handleSelectAllRoot"
              :class="[
                'px-2.5 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
                !mediaStore.selectedMissingFacet
                  ? 'bg-purple-600/30 text-purple-200 shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              ]"
              :title="t('workplace.filterAllTip')"
            >
              {{ t('workplace.filterAll') }}
            </button>
            <button
              v-if="totalUntaggedCount > 0"
              @click="handleToggleMissingFacet(vacuumFacets[0]?.code)"
              :class="[
                'px-2.5 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 whitespace-nowrap',
                mediaStore.selectedMissingFacet
                  ? 'bg-amber-500/30 text-amber-200 border border-amber-500/40 shadow-sm'
                  : 'text-amber-400/80 hover:text-amber-300 hover:bg-white/5'
              ]"
              :title="t('workplace.filterInboxTip')"
            >
              <span>{{ t('workplace.filterInbox') }}</span>
              <span class="text-[10px] font-mono px-1 rounded-full bg-amber-500/20 text-amber-300">
                {{ totalUntaggedCount }}
              </span>
            </button>
          </div>

          <!-- Action Icons Cluster -->
          <div class="flex items-center gap-1 shrink-0">
            <!-- Batch Mode Toggle -->
            <button
              @click="toggleBatchMode"
              :class="[
                'p-2 rounded-xl text-xs font-medium transition-all border select-none',
                isBatchMode
                  ? 'bg-purple-600 text-white border-purple-500 shadow-sm'
                  : 'bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10'
              ]"
              :title="isBatchMode ? t('workplace.batchModeExit') : t('workplace.batchModeEnter')"
            >
              <CheckSquare class="w-4 h-4" />
            </button>

            <!-- Sync Library Changes -->
            <button
              @click="handleSyncChanges"
              :disabled="isSyncing"
              class="p-2 rounded-xl bg-white/5 hover:bg-emerald-500/15 border border-white/10 hover:border-emerald-500/30 text-emerald-300 transition-all text-xs disabled:opacity-50"
              :title="t('workplace.syncChangesTip')"
            >
              <RefreshCw :class="['w-4 h-4 text-emerald-400', isSyncing ? 'animate-spin' : '']" />
            </button>

            <!-- Tag Center (Dedicated Workspace Page) -->
            <button
              @click="mediaStore.openTaxonomyWorkspace(mediaStore.activeLens !== 'physical' ? mediaStore.activeLens : null)"
              class="p-2 rounded-xl bg-white/5 hover:bg-teal-500/15 border border-white/10 hover:border-teal-500/30 text-teal-300 transition-all text-xs cursor-pointer"
              :title="t('workplace.tagCenterTip')"
            >
              <Tag class="w-4 h-4 text-teal-400" />
            </button>

            <!-- Pipeline Organizer -->
            <button
              data-testid="workplace-pipeline-btn"
              @click="showPipelineModal = true"
              class="p-2 rounded-xl bg-white/5 hover:bg-blue-500/15 border border-white/10 hover:border-blue-500/30 text-blue-300 transition-all text-xs"
              :title="t('workplace.pipelineTip')"
            >
              <FolderCog class="w-4 h-4 text-blue-400" />
            </button>

            <!-- More Tools Menu Dropdown -->
            <div class="relative">
              <button
                @click="showMoreTools = !showMoreTools"
                :class="[
                  'p-2 rounded-xl border transition-all text-xs',
                  showMoreTools
                    ? 'bg-white/15 border-purple-500/50 text-white'
                    : 'bg-white/5 border-white/10 text-gray-400 hover:text-white hover:bg-white/10'
                ]"
                :title="t('workplace.moreToolsTip')"
              >
                <MoreHorizontal class="w-4 h-4" />
              </button>

              <!-- Dropdown Menu -->
              <div
                v-if="showMoreTools"
                class="absolute right-0 mt-2 w-56 rounded-xl bg-gray-950/95 border border-white/10 shadow-2xl backdrop-blur-xl p-1.5 z-50 space-y-1 text-xs"
                @click="showMoreTools = false"
              >
                <button
                  @click="showMCPModal = true"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-gray-200 hover:bg-purple-600/20 hover:text-purple-200 transition-colors"
                >
                  <Bot class="w-4 h-4 text-purple-400" />
                  <div class="flex-grow">
                    <div class="font-medium">{{ t('workplace.mcpMenuTitle') }}</div>
                    <div class="text-[10px] text-gray-400">Claude / Cursor / Antigravity</div>
                  </div>
                </button>
                <button
                  @click="handleReindexAll"
                  :disabled="isSyncing"
                  class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-gray-200 hover:bg-red-500/20 hover:text-red-300 transition-colors"
                >
                  <Trash2 class="w-4 h-4 text-red-400" />
                  <div class="flex-grow">
                    <div class="font-medium">{{ t('workplace.reindexMenuTitle') }}</div>
                    <div class="text-[10px] text-gray-400">{{ t('workplace.reindexMenuSub') }}</div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Filter Status Banner (当处于待整理筛选时显示温和提示) -->
        <div
          v-if="mediaStore.selectedMissingFacet"
          class="mb-3.5 px-3.5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-between transition-all"
        >
          <div class="flex items-center gap-2 text-xs text-amber-300 min-w-0 truncate">
            <Clock class="w-4 h-4 text-amber-400 shrink-0" />
            <span class="truncate">
              {{ t('workplace.currentFilter') }}<strong>{{ t('workplace.unorganized') }}</strong>
              <span class="text-[11px] text-amber-400/80 font-mono ml-1.5">{{ t('workplace.itemsCount', { count: displayItems.length }) }}</span>
            </span>
          </div>
          <button
            @click="handleToggleMissingFacet(mediaStore.selectedMissingFacet)"
            class="text-gray-400 hover:text-white px-2 py-1 rounded-lg hover:bg-white/5 transition-colors text-xs flex items-center gap-1 shrink-0 ml-2 whitespace-nowrap"
          >
            <X class="w-3.5 h-3.5" />
            <span>{{ t('workplace.backToAll') }}</span>
          </button>
        </div>

        <!-- Active Lens Context Banner -->
        <div
          v-if="currentLensContext"
          class="mb-3 px-3.5 py-2.5 rounded-xl border flex items-center justify-between transition-all"
          :class="currentLensContext.is_unassigned ? 'bg-amber-500/10 border-amber-500/30' : 'bg-purple-500/10 border-purple-500/30'"
        >
          <div class="flex items-center gap-2 text-xs min-w-0 truncate" :class="currentLensContext.is_unassigned ? 'text-amber-300' : 'text-purple-300'">
            <AlertCircle v-if="currentLensContext.is_unassigned" class="w-4 h-4 text-amber-400 shrink-0" />
            <Tag v-else class="w-4 h-4 text-purple-400 shrink-0" />
            <span class="truncate">
              {{ t('workplace.lensFilter') }} <strong>{{ currentLensContext.title }}</strong>
              <span class="text-[10px] ml-1.5 opacity-80 font-mono">{{ t('workplace.lensItemsCount', { count: displayItems.length }) }}</span>
            </span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="handleSelectAllRoot"
              class="text-gray-400 hover:text-white p-1 rounded transition-colors"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Active Superset Context Banner -->
        <div
          v-if="currentSuperset"
          class="mb-3 px-3.5 py-2.5 rounded-xl bg-pink-500/10 border border-pink-500/30 flex items-center justify-between transition-all"
        >
          <div class="flex items-center gap-2 text-xs text-pink-300 min-w-0 truncate">
            <Sparkles class="w-4 h-4 text-pink-400 shrink-0" />
            <span class="truncate">{{ t('workplace.activeSuperset') }} <strong>{{ tData(currentSuperset.name) }}</strong> ({{ displayItems.length }})</span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="playerStore.loadSuperset(currentSuperset.id, 'fg', true)"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-pink-600 hover:bg-pink-500 text-white text-[11px] font-medium transition-all active:scale-95 shadow-sm whitespace-nowrap"
            >
              <Play class="w-3 h-3 fill-current" />
              <span>{{ t('workplace.fullscreenSlideshow') }}</span>
            </button>
            <button
              @click="handleSelectSuperset(null)"
              class="text-gray-400 hover:text-white p-1 rounded transition-colors"
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
                <span>{{ tData(currentCollection.name) }}</span>
                <span class="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded font-mono">{{ displayItems.length }}</span>
              </div>
              <div class="flex items-center gap-2 mt-0.5">
                <span v-if="currentCollection.audio_count > 0" class="text-[10px] text-emerald-400 font-mono">
                  🎧 {{ t('stream.badgeAudioCount', { count: currentCollection.audio_count }) }}
                </span>
                <span v-if="currentCollection.image_count > 0" class="text-[10px] text-amber-400 font-mono">
                  🖼️ {{ t('stream.badgeImageCount', { count: currentCollection.image_count }) }}
                </span>
                <span v-if="currentCollection.video_count > 0" class="text-[10px] text-blue-400 font-mono">
                  🎬 {{ t('stream.badgeVideoCount', { count: currentCollection.video_count }) }}
                </span>
              </div>
              <p class="text-[11px] text-gray-400 truncate mt-0.5" v-if="currentCollection.description">
                {{ tData(currentCollection.description) }}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="handlePlayCollectionAll"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-medium transition-all active:scale-95 shadow-sm whitespace-nowrap"
            >
              <Play class="w-3 h-3 fill-current" />
              <span>{{ t('workplace.playCollection') }}</span>
            </button>
            <button
              v-if="currentCollection.folder_path"
              @click="mediaStore.openPhysicalOrganizer(currentCollection.folder_path)"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-200 text-[11px] font-medium transition-all shadow-sm whitespace-nowrap"
            >
              <FolderCog class="w-3.5 h-3.5 text-amber-400" />
              <span>{{ t('workplace.physicalOrganize') }}</span>
            </button>
            <button
              @click="handleEnqueueCollection"
              class="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-gray-200 text-[11px] font-medium transition-all whitespace-nowrap"
            >
              <ListPlus class="w-3.5 h-3.5 text-purple-300" />
              <span>{{ t('workplace.enqueue') }}</span>
            </button>
            <button
              @click="handleSelectCollection(null)"
              class="text-gray-400 hover:text-white p-1 rounded transition-colors"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Collection Media Type Tabs Filter -->
        <div v-if="currentCollection && (currentCollection.image_count > 0 || currentCollection.video_count > 0)" class="flex items-center gap-2 mb-3">
          <button
            @click="collectionMediaType = 'all'"
            :class="[
              'px-2.5 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
              collectionMediaType === 'all'
                ? 'bg-blue-600 text-white shadow'
                : 'bg-white/5 text-gray-400 hover:text-white hover:bg-white/10'
            ]"
          >
            {{ t('workplace.tabAll', { count: currentCollection.total_count || displayItems.length }) }}
          </button>
          <button
            v-if="currentCollection.audio_count > 0"
            @click="collectionMediaType = 'audio'"
            :class="[
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
              collectionMediaType === 'audio'
                ? 'bg-emerald-600 text-white shadow'
                : 'bg-white/5 text-emerald-400 hover:text-white hover:bg-white/10'
            ]"
          >
            <Music class="w-3.5 h-3.5" />
            <span>{{ t('workplace.tabAudio', { count: currentCollection.audio_count }) }}</span>
          </button>
          <button
            v-if="currentCollection.image_count > 0"
            @click="collectionMediaType = 'image'"
            :class="[
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
              collectionMediaType === 'image'
                ? 'bg-amber-600 text-white shadow'
                : 'bg-white/5 text-amber-400 hover:text-white hover:bg-white/10'
            ]"
          >
            <ImageIcon class="w-3.5 h-3.5" />
            <span>{{ t('workplace.tabGallery', { count: currentCollection.image_count }) }}</span>
          </button>
          <button
            v-if="currentCollection.video_count > 0"
            @click="collectionMediaType = 'video'"
            :class="[
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
              collectionMediaType === 'video'
                ? 'bg-blue-600 text-white shadow'
                : 'bg-white/5 text-blue-400 hover:text-white hover:bg-white/10'
            ]"
          >
            <Video class="w-3.5 h-3.5" />
            <span>{{ t('workplace.tabVideo', { count: currentCollection.video_count }) }}</span>
          </button>
        </div>

        <!-- Items Table / Grid -->
        <div class="flex-grow overflow-y-auto pr-1 space-y-2">
          <div
            v-if="displayItems.length === 0"
            class="text-center py-16 text-gray-500 text-xs"
          >
            {{ t('workplace.noMatchingUnits') }}
          </div>

          <div
            v-for="item in displayItems"
            :key="item.id"
            :data-testid="`workplace-item-row-${item.id}`"
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
            <div class="flex items-center gap-3 min-w-0 flex-1">
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

              <!-- Icon/Thumbnail with Fallback -->
              <div class="w-10 h-10 rounded-lg bg-black/40 overflow-hidden shrink-0 flex items-center justify-center border border-white/10 relative">
                <component
                  :is="isAudioUnit(item) ? Music : (item.unit_type === 'image' ? ImageIcon : Video)"
                  class="w-4 h-4 text-gray-500 absolute"
                />
                <img
                  :src="`/api/stream/thumbnail/${item.id}`"
                  class="relative z-10 w-full h-full object-cover"
                  loading="lazy"
                  @error="(e) => e.target.style.display = 'none'"
                />
              </div>

              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium flex items-center gap-2 min-w-0">
                  <span class="truncate">{{ tData(item.title) }}</span>
                  <span
                    v-if="item.dynamic_attributes?.track_count > 1"
                    class="bg-purple-500/20 text-purple-300 text-[10px] px-1.5 py-0.2 rounded border border-purple-500/30 shrink-0 whitespace-nowrap font-mono"
                  >
                    {{ t('workplace.tracksBadge', { tracks: item.dynamic_attributes.track_count }) }}<template v-if="item.dynamic_attributes?.image_count > 0">{{ t('workplace.artBadge', { images: item.dynamic_attributes.image_count }) }}</template>
                  </span>
                  <span
                    v-else-if="item.unit_type === 'bundle'"
                    class="bg-purple-500/20 text-purple-300 text-[10px] px-1.5 py-0.2 rounded border border-purple-500/30 shrink-0 whitespace-nowrap"
                  >
                    {{ t('workplace.bundleFilesBadge', { count: item.files?.length || 1 }) }}
                  </span>
                </div>
                <div class="text-[11px] text-gray-400 mt-0.5 flex items-center gap-2 overflow-hidden">
                  <span class="truncate max-w-[130px]">{{ tData(item.collection_name) || t('stream.uncategorized') }}</span>
                  <span v-if="item.width && item.height && !selectedItem" class="whitespace-nowrap shrink-0">{{ item.width }}x{{ item.height }}</span>
                  <span v-if="item.files?.length > 0" class="whitespace-nowrap shrink-0">{{ formatBytes(item.files[0]?.file_size) }}</span>

                  <!-- Star Rating with Decimal -->
                  <span
                    v-if="item.rating > 0"
                    class="flex items-center gap-0.5 text-amber-400 font-mono text-[10px] font-semibold bg-amber-400/10 px-1.5 py-0.2 rounded border border-amber-400/20 shrink-0 whitespace-nowrap"
                  >
                    ★ {{ Number(item.rating).toFixed(1) }}
                  </span>

                  <!-- Recommendation Composite Algorithm Score -->
                  <span
                    v-if="item.composite_score > 0 && !selectedItem"
                    class="flex items-center gap-1 text-purple-300 font-mono text-[10px] font-semibold bg-purple-500/15 px-1.5 py-0.2 rounded border border-purple-500/25 shrink-0 whitespace-nowrap"
                  >
                    <Sparkles class="w-2.5 h-2.5" />
                    <span>{{ t('workplace.scoreBadge', { score: Number(item.composite_score).toFixed(1) }) }}</span>
                  </span>
                </div>
              </div>
            </div>

            <!-- Right Tag Badges & Quick Actions -->
            <div class="flex items-center gap-2 shrink-0">
              <!-- Compact Tag Badges on Row (Hidden on extra-narrow viewports) -->
              <div v-if="getRowCleanTags(item).length > 0" class="hidden sm:flex items-center gap-1">
                <span
                  v-for="t in getRowCleanTags(item).slice(0, selectedItem ? 2 : 3)"
                  :key="t.id || t.name"
                  class="text-[10px] px-1.5 py-0.5 rounded-md font-medium border truncate max-w-[120px] whitespace-nowrap shrink-0"
                  :class="getTagBadgeStyle(t.class_code)"
                  :title="tData(t.display_path || t.name)"
                >
                  {{ tData(t.name) }}
                </span>
                <span
                  v-if="getRowCleanTags(item).length > (selectedItem ? 2 : 3)"
                  class="text-[9px] text-gray-500 font-mono whitespace-nowrap shrink-0"
                >
                  +{{ getRowCleanTags(item).length - (selectedItem ? 2 : 3) }}
                </span>
              </div>

              <!-- Remove from Current Superset (if viewing a superset) -->
              <button
                v-if="mediaStore.selectedSupersetId"
                @click.stop="handleRemoveFromCurrentSuperset(item, $event)"
                class="p-1.5 text-gray-400 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
              >
                <MinusCircle class="w-4 h-4" />
              </button>

              <button
                @click.stop="playerStore.addToBgQueue(item)"
                class="p-1.5 text-gray-400 hover:text-purple-300 rounded-lg hover:bg-white/10 transition-colors"
              >
                <ListPlus class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- Right Inspector Details Drawer -->
      <!-- Right Inspector Details Drawer (极简无噪点，现代设计系统) -->
      <aside
        v-if="selectedItem"
        class="lg:col-span-3 border rounded-2xl p-4 flex flex-col gap-4 transition-all duration-200 overflow-y-auto max-h-[calc(100vh-100px)]"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- 1. Header (导航与关闭) -->
        <div class="flex items-center justify-between pb-3 border-b border-white/5 text-xs select-none">
          <div class="flex items-center gap-1 text-gray-400">
            <button
              @click="handlePrevItem"
              class="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
              :title="t('workplace.prevItem')"
            >
              <ChevronLeft class="w-4 h-4" />
            </button>
            <button
              @click="handleNextItem"
              class="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
              :title="t('workplace.nextItem')"
            >
              <ChevronRight class="w-4 h-4" />
            </button>
          </div>

          <div class="flex items-center gap-2">
            <button
              v-if="mediaStore.selectedMissingFacet || totalUntaggedCount > 0"
              @click="handleNextUntaggedItem"
              class="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] text-amber-300/90 hover:text-amber-200 hover:bg-amber-500/10 transition-colors cursor-pointer"
              :title="t('workplace.nextUntaggedTitle')"
            >
              <ArrowRight class="w-3 h-3 text-amber-400" />
              <span>{{ t('workplace.untaggedBtn') }}</span>
            </button>
            <button
              @click="selectedItem = null"
              class="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              :title="t('workplace.closeInspector')"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- 2. Media Preview Thumbnail with Play Trigger -->
        <div
          @click="handleDoubleClick(selectedItem)"
          class="group relative w-full aspect-video rounded-xl bg-black/50 border border-white/10 overflow-hidden cursor-pointer flex items-center justify-center shadow-sm select-none"
        >
          <!-- Fallback icon behind image -->
          <component
            :is="isAudioUnit(selectedItem) ? Music : (selectedItem.unit_type === 'image' ? ImageIcon : Video)"
            class="w-10 h-10 text-white/10 absolute z-0"
          />
          <img
            :src="`/api/stream/thumbnail/${selectedItem.id}`"
            class="relative z-10 w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            @error="(e) => e.target.style.display = 'none'"
          />
          <div class="absolute inset-0 z-20 bg-black/25 group-hover:bg-black/10 transition-colors flex items-center justify-center">
            <div class="w-10 h-10 rounded-full bg-black/60 backdrop-blur-md border border-white/20 flex items-center justify-center text-white group-hover:scale-110 group-hover:bg-purple-600 transition-all shadow-lg">
              <Play class="w-4 h-4 fill-current ml-0.5" />
            </div>
          </div>
        </div>

        <!-- 3. Title & Concise Metadata Line -->
        <div>
          <h3 class="text-sm font-semibold text-white break-words leading-snug">
            {{ tData(selectedItem.title) }}
          </h3>
          <div class="flex items-center gap-2 text-[11px] text-gray-400 mt-1 font-mono whitespace-nowrap">
            <span class="capitalize">{{ selectedItem.unit_type === 'bundle' ? t('workplace.typeBundle') : selectedItem.unit_type }}</span>
            <span>·</span>
            <span>{{ t('workplace.filesCount', { count: selectedItem.files?.length || 1 }) }}</span>
            <span v-if="selectedItem.files?.[0]?.file_size">· {{ formatBytes(selectedItem.files[0].file_size) }}</span>
          </div>
        </div>

        <!-- 4. Action Bar (1 Primary Button + Compact Icon Cluster) -->
        <div class="flex items-center gap-2 select-none">
          <button
            @click="handleDoubleClick(selectedItem)"
            class="flex-1 flex items-center justify-center gap-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs py-2 px-3 rounded-xl shadow-sm transition-all font-medium active:scale-95 cursor-pointer"
          >
            <Play class="w-3.5 h-3.5 fill-current" />
            <span>{{ t('workplace.playMain') }}</span>
          </button>
          <button
            @click="playerStore.addToBgQueue(selectedItem)"
            class="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white border border-white/10 transition-colors cursor-pointer"
            :title="t('workplace.addToQueue')"
          >
            <ListPlus class="w-4 h-4" />
          </button>
          <button
            @click="revealInExplorer({ unit_id: selectedItem.id })"
            class="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white border border-white/10 transition-colors cursor-pointer"
            :title="t('workplace.revealInExplorer')"
          >
            <FolderOpen class="w-4 h-4" />
          </button>
          <button
            @click="openWithDefaultApp({ unit_id: selectedItem.id })"
            class="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white border border-white/10 transition-colors cursor-pointer"
            :title="t('workplace.openDefaultApp')"
          >
            <ExternalLink class="w-4 h-4" />
          </button>
          <button
            v-if="mediaStore.selectedSupersetId"
            @click="handleRemoveFromCurrentSuperset(selectedItem, $event)"
            class="p-2 rounded-xl bg-white/5 hover:bg-red-500/20 text-gray-400 hover:text-red-300 border border-white/10 transition-colors cursor-pointer"
            :title="t('workplace.removeFromSuperset')"
          >
            <MinusCircle class="w-4 h-4" />
          </button>
        </div>

        <!-- 5. Tags Section (极简标签胶囊流，彻底去除大号告警框与繁杂嵌套卡片) -->
        <div class="space-y-2 pt-2 border-t border-white/5">
          <div class="flex items-center justify-between text-xs text-gray-400 select-none">
            <span class="font-medium text-gray-300">{{ t('workplace.tagsSectionTitle') }}</span>
            <button
              @click="mediaStore.openTaxonomyWorkspace(mediaStore.activeLens !== 'physical' ? mediaStore.activeLens : null)"
              class="text-[11px] text-gray-500 hover:text-purple-300 transition-colors cursor-pointer"
              :title="t('workplace.manageTagsTitle')"
            >
              {{ t('workplace.manageTags') }}
            </button>
          </div>

          <!-- Clean Horizontal Pills Wrap (Color-coded by TagClass) -->
          <div class="flex flex-wrap items-center gap-1.5">
            <span
              v-for="tItem in selectedItemTags"
              :key="tItem.tag_id"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors select-none"
              :class="[
                getTagBadgeStyle(tItem.class_code),
                tItem.is_primary_landing ? 'ring-1 ring-purple-400/50 shadow-xs' : ''
              ]"
              :title="`[${tFacet(tItem.class_code, tItem.class_name)}] ${tData(tItem.display_path || tItem.name)}${tItem.is_primary_landing ? t('workplace.primaryTagSuffix') : ''}`"
            >
              <span v-if="tItem.is_primary_landing" class="text-[9px] opacity-80">★</span>
              <button
                @click="handleTogglePrimaryLanding(tItem)"
                class="hover:opacity-80 cursor-pointer"
                :title="tItem.is_primary_landing ? t('workplace.unsetPrimaryTitle') : t('workplace.setPrimaryTitle')"
              >
                {{ tData(tItem.name) }}
              </button>
              <button
                @click="handleRemoveTag(tItem)"
                class="opacity-60 hover:opacity-100 hover:text-red-300 transition-colors cursor-pointer ml-0.5"
                :title="t('workplace.removeTagTitle')"
              >
                <X class="w-3 h-3" />
              </button>
            </span>

            <!-- + Add Tag Button -->
            <button
              v-if="!isAddingTag"
              @click="openAddTagInput"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-gray-400 hover:text-white bg-white/[0.03] hover:bg-white/10 border border-dashed border-white/15 hover:border-purple-400/40 transition-colors cursor-pointer"
              :title="t('workplace.addTagBtnTitle')"
            >
              <Plus class="w-3 h-3" />
              <span>{{ t('workplace.addTagBtn') }}</span>
            </button>
          </div>

          <!-- Inline Input for Adding Tag -->
          <div v-if="isAddingTag" class="relative mt-2 p-2 bg-black/60 border border-purple-500/40 rounded-xl space-y-2">
            <div class="flex items-center gap-1.5">
              <input
                ref="tagInputRef"
                v-model="tagSearchQuery"
                type="text"
                :placeholder="t('workplace.searchNewTagPlaceholder')"
                class="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                @keyup.enter="handleCreateAndAssignTag"
              />
              <button
                @click="isAddingTag = false"
                class="text-gray-400 hover:text-white p-1 cursor-pointer"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>

            <div v-if="availableTagSuggestions.length > 0" class="max-h-32 overflow-y-auto space-y-1">
              <button
                v-for="sug in availableTagSuggestions"
                :key="sug.id"
                @click="handleAssignTag(sug)"
                class="w-full flex items-center justify-between px-2 py-1 rounded-md bg-white/5 hover:bg-purple-600/25 text-left text-xs text-gray-200 transition-colors cursor-pointer"
              >
                <span class="truncate">{{ tData(sug.display_path || sug.name) }}</span>
                <span class="text-[10px] text-gray-500 shrink-0 ml-1">{{ tFacet(sug.class_code, sug.class_name) }}</span>
              </button>
            </div>
            <div v-else-if="tagSearchQuery.trim()">
              <button
                @click="handleCreateAndAssignTag"
                class="w-full text-center py-1 text-xs text-purple-300 bg-purple-500/10 hover:bg-purple-500/20 rounded-lg transition-colors cursor-pointer"
              >
                {{ t('workplace.createNewTagBtn', { name: tagSearchQuery.trim() }) }}
              </button>
            </div>
          </div>

          <!-- Subtle Quick Suggestions (轻量秒标，仅展示极高置信度候选) -->
          <div v-if="unitSuggestions?.suggestions?.length > 0" class="flex flex-wrap items-center gap-1 pt-1 text-[11px]">
            <span class="text-[10px] text-gray-500">{{ t('workplace.suggestedPrefix') }}</span>
            <button
              v-for="sug in unitSuggestions.suggestions.slice(0, 4)"
              :key="sug.tag_id"
              @click="handleQuickAssignSuggestion(sug)"
              class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-purple-500/10 hover:bg-purple-500/25 text-purple-300 border border-purple-500/20 text-[10px] transition-colors cursor-pointer"
              :title="sug.reason"
            >
              <span>+ {{ tData(sug.tag_name) }}</span>
            </button>
          </div>
        </div>

        <!-- 6. Rating & Favorites (简洁星级交互) -->
        <div class="flex items-center justify-between pt-2 border-t border-white/5 text-xs select-none">
          <span class="font-medium text-gray-300">{{ t('workplace.ratingLabel') }}</span>
          <div class="flex items-center gap-1.5">
            <div class="flex items-center gap-0.5">
              <button
                v-for="s in 5"
                :key="s"
                @click="handleWorkplaceAppendRate(s)"
                class="p-0.5 hover:scale-110 transition-transform cursor-pointer"
                :title="t('workplace.rateStarTitle', { s })"
              >
                <Star
                  :class="[
                    'w-3.5 h-3.5 transition-colors',
                    s <= Math.round(selectedItem.rating || 0)
                      ? 'text-amber-400 fill-amber-400'
                      : 'text-gray-600 hover:text-amber-400/50'
                  ]"
                />
              </button>
            </div>
            <span class="font-mono text-gray-400 text-[11px]">
              {{ Number(selectedItem.rating || 0).toFixed(1) }}
            </span>
          </div>
        </div>

        <!-- 7. Attached Files (仅多文件复合包时展开展示，单文件直接在元数据呈现不冗余) -->
        <div v-if="selectedItem.files && selectedItem.files.length > 1" class="space-y-1.5 pt-2 border-t border-white/5">
          <div class="text-xs font-medium text-gray-300 select-none">
            {{ t('workplace.attachedFilesCount', { count: selectedItem.files.length }) }}
          </div>
          <div class="space-y-1 max-h-36 overflow-y-auto pr-1">
            <div
              v-for="f in selectedItem.files"
              :key="f.id"
              class="flex items-center justify-between px-2 py-1 rounded-lg bg-white/5 text-[11px] text-gray-300"
            >
              <span class="truncate font-mono text-[10px] min-w-0 flex-1 mr-2" :title="f.file_name">{{ f.file_name }}</span>
              <div class="flex items-center gap-1.5 shrink-0">
                <span class="text-[9px] text-gray-500 font-mono">{{ formatBytes(f.file_size) }}</span>
                <button
                  @click="revealInExplorer({ file_id: f.id })"
                  class="text-blue-400 hover:underline text-[10px] cursor-pointer"
                >
                  {{ t('workplace.revealBtn') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 8. Supersets Quick Link (如有虚拟超集) -->
        <div v-if="mediaStore.supersets.length > 0" class="pt-2 border-t border-white/5 space-y-1.5 select-none">
          <div class="text-xs font-medium text-gray-300">{{ t('workplace.addToSupersetSection') }}</div>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="sup in mediaStore.supersets"
              :key="sup.id"
              @click="handleAddToSuperset(sup.id)"
              class="text-[10px] bg-pink-500/10 hover:bg-pink-500/20 text-pink-300 border border-pink-500/25 px-2 py-0.5 rounded-full transition-colors flex items-center gap-1 cursor-pointer"
            >
              <Plus class="w-2.5 h-2.5" />
              <span>{{ tData(sup.name) }}</span>
            </button>
          </div>
        </div>

        <!-- 9. Collapsible Developer / Advanced Algorithm Metrics (默认折叠收起，绝不打扰普通用户) -->
        <div v-if="itemAlgorithmStats" class="pt-2 border-t border-white/5 select-none">
          <button
            @click="showAlgoDetails = !showAlgoDetails"
            class="w-full flex items-center justify-between text-[10px] text-gray-500 hover:text-gray-300 transition-colors py-1 cursor-pointer"
          >
            <span>{{ t('workplace.algoMetricsBtn', { score: Number(selectedItem.composite_score || itemAlgorithmStats.composite_score || 0).toFixed(1) }) }}</span>
            <ChevronDown :class="['w-3 h-3 transition-transform', showAlgoDetails ? 'rotate-180' : '']" />
          </button>
          
          <div v-if="showAlgoDetails" class="mt-2 p-2.5 rounded-xl bg-black/40 border border-white/5 text-[10px] space-y-1.5 font-mono text-gray-400">
            <div class="flex justify-between">
              <span>{{ t('workplace.explicitScore') }}</span>
              <span class="text-purple-300">+{{ itemAlgorithmStats.explicit.total }} pts</span>
            </div>
            <div class="flex justify-between">
              <span>{{ t('workplace.implicitScore') }}</span>
              <span class="text-blue-300">+{{ itemAlgorithmStats.implicit.total }} pts ({{ Math.round(itemAlgorithmStats.implicit.dwell_seconds) }}s)</span>
            </div>
            <div class="flex justify-between text-gray-500 pt-1 border-t border-white/5">
              <span>{{ t('workplace.statusLabel') }}</span>
              <span>{{ itemAlgorithmStats.is_in_cooldown ? t('workplace.statusCooldown') : (itemAlgorithmStats.is_fatigued ? t('workplace.statusFatigued') : t('workplace.statusActive')) }}</span>
            </div>
          </div>
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
          <span class="font-semibold text-white">{{ t('batch.selectedCount', { count: selectedIds.size }) }}</span>
          <button
            @click="toggleSelectAll"
            class="px-2 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-gray-200 hover:text-white transition-colors text-[11px]"
          >
            {{ isAllSelected ? t('batch.deselectAll') : t('batch.selectAll') }}
          </button>
        </div>

        <!-- Batch Actions -->
        <div class="flex items-center gap-2 shrink-0">
          <!-- Add to Superset -->
          <button
            @click="openBatchSupersetModal"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-pink-600 hover:bg-pink-500 text-white font-medium shadow-md shadow-pink-600/30 transition-all active:scale-95"
            :title="t('batch.addToSuperset')"
          >
            <BookmarkPlus class="w-3.5 h-3.5" />
            <span>{{ t('batch.addToSuperset') }}</span>
          </button>

          <!-- Add to Background Queue -->
          <button
            @click="handleBatchAddToQueue"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium shadow-md shadow-purple-600/30 transition-all active:scale-95"
            :title="t('batch.addToQueue')"
          >
            <ListPlus class="w-3.5 h-3.5" />
            <span>{{ t('batch.addToQueue') }}</span>
          </button>

          <!-- Batch Tagging Button -->
          <button
            @click="openBatchTagModal"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium shadow-md shadow-purple-600/30 transition-all active:scale-95"
            :title="t('batch.batchTag')"
          >
            <Tag class="w-3.5 h-3.5" />
            <span>{{ t('batch.batchTag') }}</span>
          </button>

          <!-- Batch Continuous Slideshow -->
          <button
            @click="handleBatchPlaySlideshow"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-md shadow-indigo-600/30 transition-all active:scale-95"
            :title="t('batch.playSelected')"
          >
            <Play class="w-3.5 h-3.5 fill-current" />
            <span>{{ t('batch.playSelected') }}</span>
          </button>

          <!-- Exit / Cancel -->
          <button
            @click="selectedIds = new Set(); isBatchMode = false"
            class="p-1.5 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-colors ml-1"
            :title="t('batch.cancelSelection')"
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
              <span>{{ t('batch.batchSupersetTitle', { count: selectedIds.size }) }}</span>
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
              {{ t('batch.selectExistingSuperset') }}
            </label>
            <div v-if="mediaStore.supersets.length > 0" class="max-h-48 overflow-y-auto space-y-1.5 pr-1">
              <button
                v-for="sup in mediaStore.supersets"
                :key="sup.id"
                @click="handleBatchAddToSuperset(sup)"
                class="w-full flex items-center justify-between p-2.5 rounded-xl bg-white/5 hover:bg-pink-600/20 hover:border-pink-500/30 border border-transparent text-gray-200 hover:text-pink-200 transition-all text-xs font-medium"
              >
                <span>{{ tData(sup.name) }}</span>
                <span class="text-[11px] text-gray-500 font-mono">{{ sup.unit_count }}</span>
              </button>
            </div>
            <div v-else class="text-xs text-gray-400 py-2">
              {{ t('batch.noSupersetYet') }}
            </div>
          </div>

          <!-- Create New Superset and Batch Add -->
          <div class="pt-3 border-t border-white/10">
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-2">
              {{ t('batch.createAndAddSuperset') }}
            </label>
            <div class="flex items-center gap-2">
              <input
                v-model="batchNewSupersetName"
                type="text"
                :placeholder="t('batch.newSupersetPlaceholder')"
                class="flex-grow bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
                @keyup.enter="handleBatchCreateAndAddSuperset"
              />
              <button
                @click="handleBatchCreateAndAddSuperset"
                class="bg-pink-600 hover:bg-pink-500 text-white text-xs font-medium px-4 py-2 rounded-xl transition-all shrink-0"
              >
                {{ t('batch.createAndSaveBtn') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Batch Tagging Modal in Workplace -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="showBatchTagModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
        @click.self="showBatchTagModal = false"
      >
        <div
          class="w-full max-w-md bg-gray-900 border border-purple-500/30 rounded-2xl p-5 shadow-2xl text-left"
          style="background-color: var(--bg-surface-elevated);"
        >
          <div class="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
            <h3 class="text-sm font-semibold text-white flex items-center gap-2">
              <Tag class="w-4 h-4 text-purple-400" />
              <span>{{ t('batch.batchTagModalTitle', { count: selectedIds.size }) }}</span>
            </h3>
            <button
              @click="showBatchTagModal = false"
              class="text-gray-400 hover:text-white p-1 rounded-lg"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Category Selector Tabs -->
          <div class="mb-3">
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1.5">
              {{ t('batch.step1SelectCategory') }}
            </label>
            <div class="grid grid-cols-4 gap-1 p-1 bg-black/30 rounded-xl border border-white/5 text-xs">
              <button
                v-for="cat in batchCategoryTabs"
                :key="cat.code"
                @click="batchTagCategory = cat.code; batchSelectedTagId = null"
                :class="[
                  'py-1 px-1.5 rounded-lg text-center font-medium truncate transition-colors cursor-pointer',
                  batchTagCategory === cat.code
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                ]"
                :title="cat.label"
              >
                {{ cat.label }}
              </button>
            </div>
          </div>

          <!-- Tag Search & Selection List -->
          <div class="mb-4">
            <label class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block mb-1.5">
              {{ t('batch.step2SelectTag') }}
            </label>
            <input
              v-model="batchTagSearchQuery"
              type="text"
              :placeholder="t('batch.searchTagPlaceholder')"
              class="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 mb-2"
            />
            <div class="max-h-48 overflow-y-auto space-y-1 pr-1">
              <button
                v-for="tItem in batchFilteredTags"
                :key="tItem.id"
                @click="batchSelectedTagId = tItem.id"
                :class="[
                  'w-full flex items-center justify-between p-2 rounded-xl text-xs transition-all text-left border',
                  batchSelectedTagId === tItem.id
                    ? 'bg-purple-600/30 text-purple-200 border-purple-500/50 font-semibold'
                    : 'bg-white/5 border-white/5 text-gray-300 hover:bg-white/10 hover:text-white'
                ]"
              >
                <span class="truncate">{{ tData(tItem.display_path || tItem.name) }}</span>
                <span class="text-[10px] text-gray-400 font-mono">{{ tFacet(tItem.class_code, tItem.class_name) }}</span>
              </button>
              <div v-if="batchFilteredTags.length === 0" class="text-xs text-gray-500 text-center py-4">
                {{ t('batch.noMatchingTag') }}
              </div>
            </div>
          </div>

          <!-- Primary Landing Checkbox -->
          <div class="flex items-center gap-2 mb-4 p-2.5 rounded-xl bg-black/30 border border-white/5">
            <input
              id="batchPrimaryLanding"
              v-model="batchIsPrimaryLanding"
              type="checkbox"
              class="rounded bg-white/10 border-white/20 text-purple-600 focus:ring-purple-500"
            />
            <label for="batchPrimaryLanding" class="text-xs text-gray-300 cursor-pointer select-none">
              {{ t('batch.setPrimaryCheckbox') }}
            </label>
          </div>

          <!-- Confirm Action -->
          <div class="flex items-center justify-end gap-2">
            <button
              @click="showBatchTagModal = false"
              class="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 text-xs transition-colors"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              @click="handleConfirmBatchTag"
              :disabled="!batchSelectedTagId"
              class="px-4 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white font-medium text-xs shadow-md shadow-purple-600/30 transition-all active:scale-95"
            >
              {{ t('batch.confirmBatchTag') }}
            </button>
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

    <!-- Agent MCP Modal -->
    <AgentMCPModal
      :isOpen="showMCPModal"
      @close="showMCPModal = false"
    />
  </div>
</template>
