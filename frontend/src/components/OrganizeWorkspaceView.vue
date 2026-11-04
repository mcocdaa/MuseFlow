<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  Workflow,
  FolderCog,
  FolderSync,
  Layers,
  Plus,
  Play,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Sparkles,
  RefreshCw,
  FolderTree,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  X,
  HardDrive,
  Search,
  Database
} from 'lucide-vue-next'
import {
  fetchTagClasses,
  fetchPipelinePresets,
  fetchCollections,
  evaluatePipeline,
  executeTriagePlan,
  inspectFolderScope,
  planTriage,
  fetchMountStatus,
  syncLibraryChanges,
  reindexLibrary
} from '../api'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import { t, tData, tFacet, tPath } from '../i18n'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const activeTab = ref(mediaStore.organizeInitialTab || 'pipeline')

watch(
  () => mediaStore.organizeInitialTab,
  (val) => {
    if (val) activeTab.value = val
  }
)

// ==================== 1. Projection Pipeline State ====================
const tagClasses = ref([])
const presets = ref([])
const collections = ref([])
const selectedCollectionId = ref(null)
const selectedPresetId = ref('category_standard')
const pipelineLevels = ref([
  { level_index: 0, facet: 'tag.domain', fallback: '通用分类' },
  { level_index: 1, facet: 'tag.creator', fallback: '独立创作者' },
  { level_index: 2, naming: '{unit.title}%unique{}' }
])
const evaluating = ref(false)
const evaluationResult = ref(null)
const executingPipeline = ref(false)
const filterRisk = ref('all')

const projectableTagClasses = computed(() =>
  tagClasses.value.filter(c => c.is_projectable !== false)
)

const activePresetDesc = computed(() => {
  const p = presets.value.find(item => item.id === selectedPresetId.value)
  return p?.description || ''
})

const filteredPreviewActions = computed(() => {
  if (!evaluationResult.value || !evaluationResult.value.actions) return []
  if (filterRisk.value === 'all') return evaluationResult.value.actions
  return evaluationResult.value.actions.filter(a => a.risk_level === filterRisk.value)
})

const selectPreset = (preset) => {
  selectedPresetId.value = preset.id
  pipelineLevels.value = JSON.parse(JSON.stringify(preset.levels || []))
  evaluationResult.value = null
}

const addLevel = () => {
  const insertIdx = Math.max(0, pipelineLevels.value.length - 1)
  pipelineLevels.value.splice(insertIdx, 0, {
    level_index: insertIdx,
    facet: 'tag.domain',
    fallback: '未分类'
  })
  reindexLevels()
  evaluationResult.value = null
}

const removeLevel = (idx) => {
  pipelineLevels.value.splice(idx, 1)
  reindexLevels()
  evaluationResult.value = null
}

const moveLevel = (idx, dir) => {
  const target = idx + dir
  if (target < 0 || target >= pipelineLevels.value.length - 1) return
  const temp = pipelineLevels.value[idx]
  pipelineLevels.value[idx] = pipelineLevels.value[target]
  pipelineLevels.value[target] = temp
  reindexLevels()
  evaluationResult.value = null
}

const reindexLevels = () => {
  pipelineLevels.value.forEach((l, i) => { l.level_index = i })
}

const getFacetLabel = (facetToken) => {
  if (facetToken === 'collection.name') return t('pipeline.collectionNameOption')
  const code = (facetToken || '').replace('tag.', '')
  const found = tagClasses.value.find(c => c.code === code)
  return found ? tFacet(found.code, found.display_name || found.name) : code
}

const liveFormulaPreview = computed(() => {
  const dirLevels = pipelineLevels.value.filter(l => !l.naming)
  const leafLevel = pipelineLevels.value.find(l => l.naming)
  const dirs = dirLevels
    .map(l => `[${getFacetLabel(l.facet)} | ${tData(l.fallback || '通用分类')}]`)
    .join(' / ')
  const leaf = leafLevel?.naming || '{unit.title}%unique{}'
  return `${t('pipeline.libraryRoot')} / ${dirs} / ${leaf}`
})

const formatFacetName = (code) => {
  const tc = tagClasses.value.find(c => c.code === code)
  return tFacet(code, tc?.display_name || code)
}

const formatDisplayPath = (fullPath) => {
  if (!fullPath) return ''
  const root = evaluationResult.value?.target_root
  let formatted = fullPath
  if (root && fullPath.startsWith(root)) {
    const rel = fullPath.slice(root.length).replace(/^\/+/, '')
    formatted = `/Library/${rel}`
  } else {
    formatted = fullPath.replace(/^\/mnt\/media\/library\/?/, '/Library/')
  }
  return tPath(formatted)
}

const runPipelineDryRun = async () => {
  evaluating.value = true
  try {
    const targetCol = collections.value.find(c => c.id === selectedCollectionId.value)
    const fallbackCol = collections.value.find(c => c.folder_path)
    const baseFolder = targetCol?.folder_path || fallbackCol?.folder_path
    const targetRoot = baseFolder
      ? baseFolder.split('/').slice(0, -1).join('/')
      : '/mnt/media/library'

    const payload = {
      pipeline: {
        name: t('pipeline.customPipelineName'),
        target_root: targetRoot,
        levels: pipelineLevels.value
      },
      collection_id: selectedCollectionId.value
    }
    evaluationResult.value = await evaluatePipeline(payload)
  } catch (e) {
    console.error('Failed to evaluate pipeline', e)
  } finally {
    evaluating.value = false
  }
}

const applyPipelineChanges = async () => {
  if (!evaluationResult.value || !evaluationResult.value.total_actions) return
  if (!confirm(t('pipeline.confirmExec', { count: evaluationResult.value.total_actions }))) return
  executingPipeline.value = true
  try {
    const planPayload = {
      plan_id: `plan_${Date.now()}`,
      target_folder: evaluationResult.value.target_root,
      summary: `${t('pipeline.planSummaryPrefix')}${evaluationResult.value.pipeline_name}`,
      actions: evaluationResult.value.actions.map(act => ({
        action_type: 'move_file',
        src_path: act.src_path,
        dst_path: act.dst_path,
        description: `${t('pipeline.actionDescPrefix')}${act.file_name}`
      }))
    }
    const res = await executeTriagePlan(planPayload, false)
    playerStore.showToast(t('pipeline.execSuccessAlert', { count: res.executed_count || 0 }))
    await Promise.all([
      mediaStore.loadCollections(),
      mediaStore.loadWorkplaceItems(),
      mediaStore.loadFeed()
    ])
    await runPipelineDryRun()
  } catch (e) {
    alert(t('pipeline.execFailedPrefix') + ' ' + (e.response?.data?.detail || e.message))
  } finally {
    executingPipeline.value = false
  }
}

// ==================== 2. Physical Folder Triage State ====================
const folderPath = ref(mediaStore.organizeTargetFolder || '')
const selectedRule = ref('normalize_names')
const untrackSubfolder = ref(t('physOrg.defaultUntrackFolder'))
const customMappingJson = ref('{\n  "精选归档": ["*精选*", "*特辑*"]\n}')
const inspecting = ref(false)
const planning = ref(false)
const executingPhysical = ref(false)
const scopeInfo = ref(null)
const triagePlan = ref(null)
const executeResult = ref(null)
const physicalError = ref('')

const rules = computed(() => [
  {
    id: 'normalize_names',
    title: t('physOrg.ruleNormalizeTitle'),
    desc: t('physOrg.ruleNormalizeDesc'),
  },
  {
    id: 'isolate_untranslated',
    title: t('physOrg.ruleIsolateTitle'),
    desc: t('physOrg.ruleIsolateDesc'),
  },
  {
    id: 'custom_mapping',
    title: t('physOrg.ruleMappingTitle'),
    desc: t('physOrg.ruleMappingDesc'),
  }
])

const handleInspectFolder = async () => {
  if (!folderPath.value.trim()) return
  inspecting.value = true
  physicalError.value = ''
  try {
    scopeInfo.value = await inspectFolderScope(folderPath.value.trim())
  } catch (e) {
    physicalError.value = e.response?.data?.detail || e.message || t('physOrg.errInspectFailed')
  } finally {
    inspecting.value = false
  }
}

const handlePreviewTriage = async () => {
  if (!folderPath.value.trim()) {
    physicalError.value = t('physOrg.errEmptyPath')
    return
  }
  planning.value = true
  physicalError.value = ''
  triagePlan.value = null
  executeResult.value = null

  try {
    const options = {}
    if (selectedRule.value === 'isolate_untranslated') {
      options.untranslated_subfolder = untrackSubfolder.value.trim() || t('physOrg.defaultUntrackFolder')
    } else if (selectedRule.value === 'custom_mapping') {
      try {
        options.category_mapping = JSON.parse(customMappingJson.value)
      } catch {
        physicalError.value = t('physOrg.errInvalidJson')
        planning.value = false
        return
      }
    }
    const res = await planTriage(folderPath.value.trim(), selectedRule.value, options)
    triagePlan.value = res
  } catch (e) {
    physicalError.value = e.response?.data?.detail || e.message || t('physOrg.errPlanFailed')
  } finally {
    planning.value = false
  }
}

const handleExecutePhysical = async () => {
  if (!triagePlan.value || !triagePlan.value.actions?.length) return
  executingPhysical.value = true
  physicalError.value = ''
  try {
    const res = await executeTriagePlan(triagePlan.value, false)
    executeResult.value = res
    await mediaStore.checkMaintenance()
    await Promise.all([
      mediaStore.loadCollections(),
      mediaStore.loadFeed(),
      mediaStore.loadWorkplaceItems()
    ])
  } catch (e) {
    physicalError.value = e.response?.data?.detail || e.message || t('physOrg.errExecFailed')
  } finally {
    executingPhysical.value = false
  }
}

// ==================== 3. Ingest & Sync State ====================
const scanPathInput = ref('')
const scanStatus = ref(null)
const mountRoots = ref([])
const syncingChanges = ref(false)
const reindexingAll = ref(false)

const loadMountRoots = async () => {
  try {
    const res = await fetchMountStatus()
    mountRoots.value = res?.roots || []
    if (!folderPath.value && mountRoots.value.length > 0) {
      folderPath.value = mountRoots.value[0].path
    }
    if (!scanPathInput.value && mountRoots.value.length > 0) {
      scanPathInput.value = mountRoots.value[0].path
    }
  } catch {
    // ignore
  }
}

const handleStartScan = async () => {
  if (!scanPathInput.value.trim()) return
  scanStatus.value = 'scanning'
  try {
    const res = await mediaStore.scanFolder(scanPathInput.value.trim())
    scanStatus.value = { type: 'success', data: res }
    playerStore.showToast(
      t('scanModal.statCollections', { count: res.created_collections }) +
      ' · ' +
      t('scanModal.statUnits', { count: res.created_units })
    )
  } catch (err) {
    scanStatus.value = {
      type: 'error',
      msg: err.response?.data?.detail || t('scanModal.scanFailedFallback')
    }
  }
}

const handleSyncLibrary = async () => {
  if (syncingChanges.value) return
  syncingChanges.value = true
  try {
    const res = await syncLibraryChanges()
    if (res.status === 'success') {
      playerStore.showToast(
        t('workplace.toastSyncSuccess', { added: res.added_units || 0, pruned: res.pruned_units || 0 })
      )
      await Promise.all([
        mediaStore.loadCollections(),
        mediaStore.loadWorkplaceItems(),
        mediaStore.loadFeed(),
        mediaStore.loadTags()
      ])
    } else {
      playerStore.showToast(t('workplace.toastSyncFailed') + (res.message || ''))
    }
  } catch (e) {
    playerStore.showToast(t('workplace.toastSyncError') + (e.response?.data?.detail || e.message))
  } finally {
    syncingChanges.value = false
  }
}

const handleReindexLibrary = async () => {
  if (reindexingAll.value) return
  if (!confirm(t('workplace.confirmReindex'))) return
  reindexingAll.value = true
  try {
    const res = await reindexLibrary()
    if (res.status === 'success') {
      playerStore.showToast(t('workplace.toastReindexSuccess', { added: res.added_units || 0 }))
      await Promise.all([
        mediaStore.loadCollections(),
        mediaStore.loadSupersets(),
        mediaStore.loadWorkplaceItems(),
        mediaStore.loadFeed(),
        mediaStore.loadTags()
      ])
    } else {
      playerStore.showToast(t('workplace.toastReindexFailed') + (res.message || ''))
    }
  } catch (e) {
    playerStore.showToast(t('workplace.toastReindexError') + (e.response?.data?.detail || e.message))
  } finally {
    reindexingAll.value = false
  }
}

onMounted(async () => {
  const [classesData, presetsData, colsData] = await Promise.all([
    fetchTagClasses().catch(() => []),
    fetchPipelinePresets().catch(() => []),
    fetchCollections().catch(() => []),
    loadMountRoots()
  ])
  tagClasses.value = classesData || []
  presets.value = presetsData || []
  collections.value = colsData || []
  if (presets.value.length > 0) {
    selectPreset(presets.value[0])
  }
})
</script>

<template>
  <div class="max-w-[1600px] mx-auto px-2 py-2 flex flex-col gap-5">
    <!-- Top Header & Task Switcher -->
    <div
      class="rounded-xl p-5 border flex flex-col md:flex-row md:items-center justify-between gap-4"
      style="background-color: var(--bg-surface); border-color: var(--border-color);"
    >
      <div>
        <h1 class="text-base font-semibold tracking-tight flex items-center gap-2.5" style="color: var(--text-primary);">
          <Workflow class="w-4 h-4" style="color: var(--accent-text);" />
          <span>{{ t('organize.pageTitle') }}</span>
        </h1>
        <p class="text-xs mt-1" style="color: var(--text-muted);">
          {{ t('organize.pageSubtitle') }}
        </p>
      </div>

      <!-- 3 Clear Task Tabs -->
      <div
        class="inline-flex items-center p-1 rounded-lg border gap-1 self-start md:self-auto"
        style="background-color: var(--bg-app); border-color: var(--border-color);"
      >
        <button
          data-testid="organize-tab-pipeline"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
          :style="activeTab === 'pipeline'
            ? 'background-color: var(--accent-color); color: #ffffff;'
            : 'color: var(--text-secondary);'"
          @click="activeTab = 'pipeline'"
        >
          <Layers class="w-3.5 h-3.5" :style="activeTab === 'pipeline' ? 'color: #ffffff;' : 'color: var(--accent-text);'" />
          <span>{{ t('organize.tabPipeline') }}</span>
        </button>

        <button
          data-testid="organize-tab-physical"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
          :style="activeTab === 'physical'
            ? 'background-color: var(--accent-color); color: #ffffff;'
            : 'color: var(--text-secondary);'"
          @click="activeTab = 'physical'"
        >
          <FolderCog class="w-3.5 h-3.5" :style="activeTab === 'physical' ? 'color: #ffffff;' : 'color: var(--accent-text);'" />
          <span>{{ t('organize.tabPhysical') }}</span>
        </button>

        <button
          data-testid="organize-tab-ingest"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer"
          :style="activeTab === 'ingest'
            ? 'background-color: var(--accent-color); color: #ffffff;'
            : 'color: var(--text-secondary);'"
          @click="activeTab = 'ingest'"
        >
          <FolderSync class="w-3.5 h-3.5" :style="activeTab === 'ingest' ? 'color: #ffffff;' : 'color: var(--accent-text);'" />
          <span>{{ t('organize.tabIngest') }}</span>
        </button>
      </div>
    </div>

    <!-- ==================== TAB 1: PROJECTION PIPELINE ==================== -->
    <div v-if="activeTab === 'pipeline'" class="flex flex-col gap-5">
      <div
        class="rounded-xl p-5 border flex flex-col gap-5"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Presets & Scope Row -->
        <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
          <div class="md:col-span-8 flex flex-col gap-1.5">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs font-medium mr-1" style="color: var(--text-muted);">{{ t('pipeline.presetsLabel') }}</span>
              <button
                v-for="p in presets"
                :key="p.id"
                class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border cursor-pointer"
                :style="selectedPresetId === p.id
                  ? 'background-color: var(--accent-light); color: var(--text-primary); border-color: var(--accent-border);'
                  : 'background-color: var(--bg-app); color: var(--text-secondary); border-color: var(--border-color);'"
                @click="selectPreset(p)"
              >
                {{ tData(p.name) }}
              </button>
            </div>
            <p v-if="activePresetDesc" class="text-[11px]" style="color: var(--text-muted);">
              {{ tData(activePresetDesc) }}
            </p>
          </div>

          <div class="md:col-span-4 flex items-center gap-2">
            <span class="text-xs font-medium shrink-0" style="color: var(--text-muted);">{{ t('pipeline.scopeLabel') }}</span>
            <select
              v-model="selectedCollectionId"
              class="w-full text-xs px-3 py-1.5 rounded-lg border outline-none"
              style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-primary);"
              @change="evaluationResult = null"
            >
              <option :value="null">{{ t('pipeline.allIndexedOption') }}</option>
              <option v-for="col in collections" :key="col.id" :value="col.id">
                {{ tData(col.name) }} ({{ col.unit_count || 0 }})
              </option>
            </select>
          </div>
        </div>

        <!-- Layer Chain Editor -->
        <div class="flex items-center gap-2.5 overflow-x-auto pb-1">
          <div
            class="px-3 py-2.5 rounded-lg border text-xs font-mono shrink-0 flex items-center gap-1.5"
            style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-secondary);"
          >
            <FolderTree class="w-3.5 h-3.5" style="color: var(--accent-text);" />
            <span>{{ t('pipeline.libraryRoot') }}</span>
          </div>

          <template v-for="(lvl, idx) in pipelineLevels" :key="idx">
            <ArrowRight class="w-4 h-4 shrink-0" style="color: var(--accent-text); opacity: 0.7;" />

            <div
              class="p-3 rounded-lg border min-w-[180px] shrink-0 flex flex-col gap-2"
              style="background-color: var(--bg-app); border-color: var(--border-color);"
            >
              <div class="flex items-center justify-between">
                <span class="text-[11px] font-semibold tracking-wider" style="color: var(--text-secondary);">
                  {{ idx === pipelineLevels.length - 1 && lvl.naming ? t('pipeline.leafRuleBadge') : t('pipeline.levelBadge', { level: idx + 1 }) }}
                </span>
                <div class="flex items-center gap-1">
                  <button
                    v-if="idx > 0 && !lvl.naming"
                    class="p-1 rounded hover:bg-white/5 cursor-pointer"
                    style="color: var(--text-muted);"
                    @click="moveLevel(idx, -1)"
                  >
                    <ChevronLeft class="w-3.5 h-3.5" />
                  </button>
                  <button
                    v-if="idx < pipelineLevels.length - 2 && !lvl.naming"
                    class="p-1 rounded hover:bg-white/5 cursor-pointer"
                    style="color: var(--text-muted);"
                    @click="moveLevel(idx, 1)"
                  >
                    <ChevronRight class="w-3.5 h-3.5" />
                  </button>
                  <button
                    v-if="pipelineLevels.length > 2 && !lvl.naming"
                    class="p-1 rounded hover:bg-white/5 cursor-pointer"
                    style="color: var(--text-muted);"
                    @click="removeLevel(idx)"
                  >
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <!-- Leaf Naming Mode -->
              <div v-if="lvl.naming" class="flex flex-col gap-1.5">
                <span class="text-[11px]" style="color: var(--text-muted);">{{ t('pipeline.namingTemplateLabel') }}</span>
                <input
                  v-model="lvl.naming"
                  type="text"
                  class="w-full rounded-md px-2.5 py-1.5 text-xs font-mono border focus:outline-none"
                  style="background-color: var(--bg-surface); border-color: var(--border-color); color: var(--text-primary);"
                  @input="evaluationResult = null"
                >
              </div>

              <!-- Facet Layer Mode -->
              <div v-else class="flex flex-col gap-2">
                <select
                  v-model="lvl.facet"
                  class="w-full rounded-md px-2.5 py-1.5 text-xs border focus:outline-none"
                  style="background-color: var(--bg-surface); border-color: var(--border-color); color: var(--text-primary);"
                  @change="evaluationResult = null"
                >
                  <option
                    v-for="fc in projectableTagClasses"
                    :key="fc.code"
                    :value="`tag.${fc.code}`"
                  >
                    {{ tFacet(fc.code, fc.display_name) }}
                  </option>
                  <option value="collection.name">{{ t('pipeline.collectionNameOption') }}</option>
                </select>

                <input
                  :value="tData(lvl.fallback)"
                  type="text"
                  class="w-full rounded px-2 py-1 text-[11px] border focus:outline-none"
                  style="background-color: var(--bg-surface); border-color: var(--border-color); color: var(--text-secondary);"
                  :placeholder="t('pipeline.fallbackPlaceholder')"
                  @input="lvl.fallback = $event.target.value; evaluationResult = null"
                >
              </div>
            </div>
          </template>

          <button
            class="px-3 py-2 rounded-lg border border-dashed text-xs flex items-center gap-1.5 shrink-0 transition-colors cursor-pointer"
            style="border-color: var(--border-hover); color: var(--text-secondary);"
            @click="addLevel"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>{{ t('pipeline.addLevelBtn').replace(/^\+\s*/, '') }}</span>
          </button>
        </div>

        <!-- Formula Preview & Dry-Run Action Bar -->
        <div
          class="flex flex-wrap items-center justify-between gap-4 pt-3 border-t"
          style="border-color: var(--border-color);"
        >
          <div class="flex items-center gap-2 text-xs font-mono" style="color: var(--text-secondary);">
            <span>{{ t('pipeline.livePreviewLabel') }}</span>
            <span
              class="px-2.5 py-1 rounded border"
              style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-primary);"
            >
              {{ liveFormulaPreview }}
            </span>
          </div>

          <div class="flex items-center gap-3">
            <button
              data-testid="pipeline-dryrun-btn"
              :disabled="evaluating"
              class="px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
              style="background-color: var(--accent-color); color: #ffffff;"
              @click="runPipelineDryRun"
            >
              <Sparkles class="w-3.5 h-3.5" :class="{ 'animate-spin': evaluating }" />
              <span>{{ evaluating ? t('pipeline.runningDryRun') : t('pipeline.runDryRunBtn') }}</span>
            </button>

            <button
              v-if="evaluationResult && evaluationResult.total_actions > 0"
              :disabled="executingPipeline || evaluationResult.stats?.conflict_count > 0"
              class="px-4 py-2 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
              style="background-color: var(--bg-surface-elevated); border-color: var(--border-hover); color: var(--text-primary);"
              @click="applyPipelineChanges"
            >
              <Play class="w-3.5 h-3.5" />
              <span>{{ executingPipeline ? t('pipeline.executingBtn') : t('pipeline.applyOrganizeBtn', { count: evaluationResult.total_actions }) }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Dry-Run Inspection Table -->
      <div
        class="rounded-xl border overflow-hidden"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div v-if="!evaluationResult" class="py-14 flex flex-col items-center justify-center text-center px-4">
          <Layers class="w-8 h-8 mb-2.5 opacity-30" style="color: var(--text-muted);" />
          <p class="text-xs font-medium" style="color: var(--text-secondary);">
            {{ t('pipeline.footerSafeHint') }}
          </p>
        </div>

        <div v-else class="flex flex-col">
          <div
            class="px-5 py-3 border-b flex items-center justify-between flex-wrap gap-3"
            style="border-color: var(--border-color); background-color: var(--bg-app);"
          >
            <div class="flex items-center gap-2">
              <button
                class="px-3 py-1 rounded-md text-xs font-medium transition-colors border cursor-pointer"
                :style="filterRisk === 'all'
                  ? 'background-color: var(--bg-surface-elevated); color: var(--text-primary); border-color: var(--border-hover);'
                  : 'color: var(--text-secondary); border-color: transparent;'"
                @click="filterRisk = 'all'"
              >
                {{ t('pipeline.itemsUnit', { count: evaluationResult.total_actions || 0 }) }}
              </button>
              <button
                class="px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 border cursor-pointer"
                :style="filterRisk === 'safe'
                  ? 'background-color: var(--bg-surface-elevated); color: var(--text-primary); border-color: var(--border-hover);'
                  : 'color: var(--text-secondary); border-color: transparent;'"
                @click="filterRisk = 'safe'"
              >
                <CheckCircle2 class="w-3.5 h-3.5" />
                <span>{{ t('pipeline.safeLabel') }} ({{ evaluationResult.stats?.safe_count || 0 }})</span>
              </button>
              <button
                class="px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 border cursor-pointer"
                :style="filterRisk === 'warning'
                  ? 'background-color: var(--bg-surface-elevated); color: var(--text-primary); border-color: var(--border-hover);'
                  : 'color: var(--text-secondary); border-color: transparent;'"
                @click="filterRisk = 'warning'"
              >
                <AlertTriangle class="w-3.5 h-3.5" />
                <span>{{ t('pipeline.fallbackLabel') }} ({{ evaluationResult.stats?.warning_count || 0 }})</span>
              </button>
              <button
                class="px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 border cursor-pointer"
                :style="filterRisk === 'conflict'
                  ? 'background-color: var(--bg-surface-elevated); color: var(--text-primary); border-color: var(--border-hover);'
                  : 'color: var(--text-secondary); border-color: transparent;'"
                @click="filterRisk = 'conflict'"
              >
                <XCircle class="w-3.5 h-3.5" />
                <span>{{ t('pipeline.conflictsLabel') }} ({{ evaluationResult.stats?.conflict_count || 0 }})</span>
              </button>
            </div>
            <span v-if="evaluationResult.stats?.degraded_count > 0" class="text-xs" style="color: var(--text-muted);">
              {{ t('pipeline.degradedNotice', { count: evaluationResult.stats.degraded_count }) }}
            </span>
          </div>

          <div class="overflow-x-auto max-h-[520px] overflow-y-auto">
            <table class="w-full text-left border-collapse text-xs">
              <thead>
                <tr class="border-b" style="border-color: var(--border-color); color: var(--text-muted);">
                  <th class="py-2.5 px-4 w-24 font-medium">{{ t('pipeline.colStatus') }}</th>
                  <th class="py-2.5 px-4 w-56 font-medium">{{ t('pipeline.colFileName') }}</th>
                  <th class="py-2.5 px-4 font-medium">{{ t('pipeline.colSourcePath') }}</th>
                  <th class="py-2.5 px-4 font-medium">{{ t('pipeline.colTargetPath') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y" style="border-color: var(--border-color);">
                <tr
                  v-for="(act, aIdx) in filteredPreviewActions"
                  :key="aIdx"
                  class="hover:bg-white/[0.02] transition-colors"
                >
                  <td class="py-2.5 px-4">
                    <span
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border"
                      style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-secondary);"
                    >
                      <CheckCircle2 v-if="act.risk_level === 'safe'" class="w-3 h-3" />
                      <AlertTriangle v-else-if="act.risk_level === 'warning'" class="w-3 h-3" />
                      <XCircle v-else class="w-3 h-3" />
                      <span>{{ act.risk_level }}</span>
                    </span>
                  </td>
                  <td class="py-2.5 px-4 font-medium" style="color: var(--text-primary);">
                    <div class="truncate max-w-[200px]">{{ act.file_name }}</div>
                    <div v-if="act.missing_facets?.length > 0" class="flex flex-wrap gap-1 mt-0.5">
                      <span
                        v-for="mf in act.missing_facets"
                        :key="mf"
                        class="text-[10px] px-1.5 py-0.2 rounded border"
                        style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-muted);"
                      >
                        {{ t('pipeline.missingFacetPrefix') }}{{ formatFacetName(mf) }}
                      </span>
                    </div>
                  </td>
                  <td class="py-2.5 px-4 font-mono text-[11px] break-all" style="color: var(--text-muted);">
                    {{ formatDisplayPath(act.src_path) }}
                  </td>
                  <td class="py-2.5 px-4 font-mono text-[11px] break-all" style="color: var(--text-primary);">
                    {{ formatDisplayPath(act.dst_path) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== TAB 2: PHYSICAL FOLDER TRIAGE ==================== -->
    <div v-else-if="activeTab === 'physical'" class="grid grid-cols-1 lg:grid-cols-12 gap-5">
      <!-- Left Configuration Column -->
      <div
        class="lg:col-span-5 rounded-xl p-5 border flex flex-col gap-5"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div>
          <label class="block text-xs font-medium mb-2" style="color: var(--text-secondary);">
            {{ t('physOrg.scopeLabel') }}
          </label>
          <div class="flex gap-2">
            <input
              v-model="folderPath"
              type="text"
              :placeholder="t('physOrg.scopePlaceholder')"
              class="flex-1 px-3 py-2 rounded-lg text-xs border font-mono focus:outline-none"
              style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-primary);"
              @keyup.enter="handleInspectFolder"
            >
            <button
              class="px-3 py-2 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-colors cursor-pointer"
              style="background-color: var(--bg-surface-elevated); border-color: var(--border-color); color: var(--text-primary);"
              :disabled="inspecting"
              @click="handleInspectFolder"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': inspecting }" />
              <span>{{ t('physOrg.inspectBtn') }}</span>
            </button>
          </div>

          <!-- Quick Mount Root Chips -->
          <div v-if="mountRoots.length > 0" class="flex items-center gap-1.5 flex-wrap mt-2.5">
            <button
              v-for="r in mountRoots"
              :key="r.path"
              class="px-2 py-1 rounded text-[11px] font-mono border transition-colors cursor-pointer"
              style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-secondary);"
              @click="folderPath = r.path; handleInspectFolder()"
            >
              {{ r.path }}
            </button>
          </div>

          <div
            v-if="scopeInfo"
            class="mt-3 px-3 py-2 rounded-lg border flex items-center justify-between text-xs"
            style="background-color: var(--bg-app); border-color: var(--border-color);"
          >
            <span class="font-mono truncate" style="color: var(--text-secondary);">{{ scopeInfo.folder_path }}</span>
            <span class="shrink-0 font-medium" style="color: var(--text-primary);">
              {{ t('physOrg.workFolderCount', { count: scopeInfo.work_folder_count }) }}
            </span>
          </div>
        </div>

        <!-- Strategy Cards -->
        <div class="flex flex-col gap-2.5">
          <label class="block text-xs font-medium" style="color: var(--text-secondary);">
            {{ t('physOrg.selectStrategyLabel') }}
          </label>
          <button
            v-for="r in rules"
            :key="r.id"
            class="p-3.5 rounded-lg border text-left transition-colors cursor-pointer"
            :style="selectedRule === r.id
              ? 'background-color: var(--accent-light); border-color: var(--accent-border);'
              : 'background-color: var(--bg-app); border-color: var(--border-color);'"
            @click="selectedRule = r.id; triagePlan = null; executeResult = null"
          >
            <div class="text-xs font-semibold" style="color: var(--text-primary);">{{ r.title }}</div>
            <div class="text-[11px] mt-1 leading-relaxed" style="color: var(--text-muted);">{{ r.desc }}</div>
          </button>
        </div>

        <!-- Rule-Specific Options -->
        <div
          v-if="selectedRule === 'isolate_untranslated'"
          class="p-3.5 rounded-lg border flex flex-col gap-2"
          style="background-color: var(--bg-app); border-color: var(--border-color);"
        >
          <label class="text-xs font-medium" style="color: var(--text-secondary);">
            {{ t('physOrg.untrackSubfolderLabel') }}
          </label>
          <input
            v-model="untrackSubfolder"
            type="text"
            class="px-3 py-1.5 rounded-md text-xs border focus:outline-none"
            style="background-color: var(--bg-surface); border-color: var(--border-color); color: var(--text-primary);"
          >
          <span class="text-[11px]" style="color: var(--text-muted);">{{ t('physOrg.untrackRuleTip') }}</span>
        </div>

        <div
          v-if="selectedRule === 'custom_mapping'"
          class="p-3.5 rounded-lg border flex flex-col gap-2"
          style="background-color: var(--bg-app); border-color: var(--border-color);"
        >
          <div class="flex items-center justify-between">
            <label class="text-xs font-medium" style="color: var(--text-secondary);">
              {{ t('physOrg.mappingRuleLabel') }}
            </label>
            <span class="text-[10px]" style="color: var(--text-muted);">{{ t('physOrg.mappingJsonTip') }}</span>
          </div>
          <textarea
            v-model="customMappingJson"
            rows="4"
            class="w-full p-2.5 rounded-md text-xs font-mono border focus:outline-none"
            style="background-color: var(--bg-surface); border-color: var(--border-color); color: var(--text-primary);"
          />
        </div>

        <div class="flex items-center gap-3 pt-2">
          <button
            :disabled="planning || !folderPath.trim()"
            class="flex-1 py-2.5 px-4 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
            style="background-color: var(--accent-color); color: #ffffff;"
            @click="handlePreviewTriage"
          >
            <RefreshCw v-if="planning" class="w-3.5 h-3.5 animate-spin" />
            <Play v-else class="w-3.5 h-3.5" />
            <span>{{ planning ? t('physOrg.planningBtn') : t('physOrg.generateDryRunBtn') }}</span>
          </button>

          <button
            v-if="triagePlan && triagePlan.actions?.length > 0 && !executeResult"
            :disabled="executingPhysical"
            class="py-2.5 px-4 rounded-lg text-xs font-medium border flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
            style="background-color: var(--bg-surface-elevated); border-color: var(--border-hover); color: var(--text-primary);"
            @click="handleExecutePhysical"
          >
            <CheckCircle2 class="w-3.5 h-3.5" />
            <span>{{ executingPhysical ? t('physOrg.executingBtn') : t('physOrg.confirmExecuteBtn', { count: triagePlan.actions.length }) }}</span>
          </button>
        </div>

        <div
          v-if="physicalError"
          class="p-3 rounded-lg border text-xs flex items-center gap-2"
          style="background-color: var(--bg-app); border-color: var(--border-hover); color: var(--text-primary);"
        >
          <AlertTriangle class="w-4 h-4 shrink-0" />
          <span>{{ physicalError }}</span>
        </div>
      </div>

      <!-- Right Dry-Run Preview Column -->
      <div
        class="lg:col-span-7 rounded-xl border p-5 flex flex-col"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div v-if="executeResult" class="py-12 flex flex-col items-center justify-center text-center">
          <CheckCircle2 class="w-8 h-8 mb-2" style="color: var(--text-primary);" />
          <div class="text-sm font-semibold" style="color: var(--text-primary);">
            {{ t('physOrg.execDoneTitle', { executed: executeResult.executed_count, skipped: executeResult.skipped_count }) }}
          </div>
          <p class="text-xs mt-1" style="color: var(--text-muted);">{{ t('physOrg.execDoneSubtitle') }}</p>
        </div>

        <div v-else-if="triagePlan" class="flex flex-col gap-3 flex-1">
          <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--border-color);">
            <span class="text-xs font-medium" style="color: var(--text-primary);">{{ tData(triagePlan.summary) }}</span>
            <span class="text-xs font-mono" style="color: var(--text-muted);">
              {{ t('physOrg.pendingActionsCount', { count: triagePlan.actions?.length || 0 }) }}
            </span>
          </div>

          <div v-if="triagePlan.actions?.length === 0" class="py-16 text-center text-xs" style="color: var(--text-muted);">
            {{ t('physOrg.allCompliantMsg') }}
          </div>

          <div v-else class="space-y-2 max-h-[480px] overflow-y-auto pr-1">
            <div
              v-for="(act, idx) in triagePlan.actions"
              :key="idx"
              class="p-3 rounded-lg border text-xs flex flex-col gap-1"
              style="background-color: var(--bg-app); border-color: var(--border-color);"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="font-medium" style="color: var(--text-primary);">{{ tData(act.reason) }}</span>
                <span class="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border" style="border-color: var(--border-color); color: var(--text-muted);">
                  {{ act.action }}
                </span>
              </div>
              <div v-if="act.source" class="font-mono text-[11px] truncate" style="color: var(--text-muted);">
                {{ act.source }}
              </div>
              <div v-if="act.target" class="font-mono text-[11px] truncate flex items-center gap-1.5" style="color: var(--text-secondary);">
                <ArrowRight class="w-3 h-3 shrink-0" />
                <span class="truncate">{{ act.target }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="py-20 flex flex-col items-center justify-center text-center">
          <FolderCog class="w-10 h-10 mb-3 opacity-30" style="color: var(--text-muted);" />
          <p class="text-sm font-medium" style="color: var(--text-secondary);">{{ t('organize.tabPhysical') }}</p>
          <p class="text-xs mt-1 max-w-md" style="color: var(--text-muted);">{{ t('organize.tabPhysicalDesc') }}</p>
        </div>
      </div>
    </div>

    <!-- ==================== TAB 3: SCAN & INDEX SYNC ==================== -->
    <div v-else-if="activeTab === 'ingest'" class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- Card 1: Scan Local Directory -->
      <div
        class="rounded-xl p-5 border flex flex-col justify-between gap-4"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div class="flex flex-col gap-3">
          <div class="flex items-center gap-2.5">
            <div class="p-2 rounded-lg border" style="background-color: var(--bg-app); border-color: var(--border-color);">
              <Search class="w-4 h-4" style="color: var(--text-primary);" />
            </div>
            <div>
              <h3 class="text-sm font-semibold" style="color: var(--text-primary);">{{ t('organize.ingestScanTitle') }}</h3>
            </div>
          </div>
          <p class="text-xs leading-relaxed" style="color: var(--text-muted);">
            {{ t('organize.ingestScanDesc') }}
          </p>

          <div class="mt-1">
            <label class="block text-[11px] font-medium mb-1.5" style="color: var(--text-secondary);">
              {{ t('organize.ingestPathLabel') }}
            </label>
            <input
              v-model="scanPathInput"
              type="text"
              :placeholder="t('organize.ingestPathPlaceholder')"
              class="w-full px-3 py-2 rounded-lg text-xs font-mono border focus:outline-none"
              style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-primary);"
              @keyup.enter="handleStartScan"
            >
          </div>

          <div v-if="scanStatus && scanStatus !== 'scanning'" class="p-3 rounded-lg border text-xs" style="background-color: var(--bg-app); border-color: var(--border-color);">
            <div v-if="scanStatus.type === 'success'" class="flex items-center justify-between" style="color: var(--text-primary);">
              <span>{{ t('scanModal.statCollections', { count: scanStatus.data.created_collections }) }}</span>
              <span>{{ t('scanModal.statUnits', { count: scanStatus.data.created_units }) }}</span>
              <span>{{ t('scanModal.statFiles', { count: scanStatus.data.created_files }) }}</span>
            </div>
            <div v-else style="color: var(--text-secondary);">
              {{ scanStatus.msg }}
            </div>
          </div>
        </div>

        <button
          :disabled="scanStatus === 'scanning' || !scanPathInput.trim()"
          class="w-full py-2.5 px-4 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
          style="background-color: var(--accent-color); color: #ffffff;"
          @click="handleStartScan"
        >
          <RefreshCw v-if="scanStatus === 'scanning'" class="w-3.5 h-3.5 animate-spin" />
          <Search v-else class="w-3.5 h-3.5" />
          <span>{{ scanStatus === 'scanning' ? t('organize.ingestScanningBtn') : t('organize.ingestStartBtn') }}</span>
        </button>
      </div>

      <!-- Card 2: Incremental Sync -->
      <div
        class="rounded-xl p-5 border flex flex-col justify-between gap-4"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div class="flex flex-col gap-3">
          <div class="flex items-center gap-2.5">
            <div class="p-2 rounded-lg border" style="background-color: var(--bg-app); border-color: var(--border-color);">
              <RefreshCw class="w-4 h-4" style="color: var(--text-primary);" />
            </div>
            <div>
              <h3 class="text-sm font-semibold" style="color: var(--text-primary);">{{ t('organize.ingestSyncTitle') }}</h3>
            </div>
          </div>
          <p class="text-xs leading-relaxed" style="color: var(--text-muted);">
            {{ t('organize.ingestSyncDesc') }}
          </p>

          <!-- Mounted Roots Status List -->
          <div class="mt-1 flex flex-col gap-1.5">
            <span class="text-[11px] font-medium" style="color: var(--text-secondary);">
              {{ t('organize.mountRootsTitle') }}
            </span>
            <div
              v-for="r in mountRoots"
              :key="r.path"
              class="px-3 py-2 rounded-lg border flex items-center justify-between text-xs"
              style="background-color: var(--bg-app); border-color: var(--border-color);"
            >
              <div class="flex items-center gap-2 min-w-0">
                <HardDrive class="w-3.5 h-3.5 shrink-0" style="color: var(--text-muted);" />
                <span class="font-mono truncate" style="color: var(--text-primary);">{{ r.path }}</span>
              </div>
              <button
                class="text-[11px] px-2 py-0.5 rounded border shrink-0 cursor-pointer"
                style="border-color: var(--border-color); color: var(--text-secondary);"
                @click="scanPathInput = r.path"
              >
                {{ t('organize.quickSelectRoot') }}
              </button>
            </div>
          </div>
        </div>

        <button
          :disabled="syncingChanges"
          class="w-full py-2.5 px-4 rounded-lg text-xs font-medium border flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
          style="background-color: var(--bg-surface-elevated); border-color: var(--border-hover); color: var(--text-primary);"
          @click="handleSyncLibrary"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': syncingChanges }" />
          <span>{{ syncingChanges ? t('organize.ingestSyncingBtn') : t('organize.ingestSyncBtn') }}</span>
        </button>
      </div>

      <!-- Card 3: Full Library Reindex -->
      <div
        class="rounded-xl p-5 border flex flex-col justify-between gap-4"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <div class="flex flex-col gap-3">
          <div class="flex items-center gap-2.5">
            <div class="p-2 rounded-lg border" style="background-color: var(--bg-app); border-color: var(--border-color);">
              <Database class="w-4 h-4" style="color: var(--text-primary);" />
            </div>
            <div>
              <h3 class="text-sm font-semibold" style="color: var(--text-primary);">{{ t('organize.ingestReindexTitle') }}</h3>
            </div>
          </div>
          <p class="text-xs leading-relaxed" style="color: var(--text-muted);">
            {{ t('organize.ingestReindexDesc') }}
          </p>
        </div>

        <button
          :disabled="reindexingAll"
          class="w-full py-2.5 px-4 rounded-lg text-xs font-medium border flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
          style="background-color: var(--bg-app); border-color: var(--border-color); color: var(--text-secondary);"
          @click="handleReindexLibrary"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': reindexingAll }" />
          <span>{{ reindexingAll ? t('organize.ingestReindexingBtn') : t('organize.ingestReindexBtn') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
