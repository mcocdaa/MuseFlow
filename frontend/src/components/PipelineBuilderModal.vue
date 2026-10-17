<template>
  <div v-if="isOpen" @click.self="close" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
    <div 
      class="w-full max-w-5xl max-h-[90vh] flex flex-col rounded-2xl shadow-2xl border overflow-hidden"
      style="background: var(--bg-surface-elevated); border-color: var(--border-color);"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b shrink-0" style="border-color: var(--border-color);">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-xl text-white shadow-md" style="background: linear-gradient(135deg, var(--accent-color), #8b5cf6);">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div>
            <h3 class="text-lg font-bold" style="color: var(--text-main);">{{ t('pipeline.title') }}</h3>
            <p class="text-xs" style="color: var(--text-muted);">
              {{ t('pipeline.subtitle') }}
            </p>
          </div>
        </div>

        <button 
          @click="close"
          class="p-2 rounded-xl transition-colors hover:bg-white/10"
          style="color: var(--text-muted);"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Main Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-5">
        <!-- 1. 预设选择器与目标根目录 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl border space-y-2 md:col-span-2" style="background: var(--bg-surface); border-color: var(--border-color);">
            <label class="text-xs font-semibold tracking-wider block" style="color: var(--text-muted);">
              {{ t('pipeline.presetsLabel') }}
            </label>
            <div class="flex flex-wrap gap-2">
              <button 
                v-for="p in presets" 
                :key="p.id"
                @click="applyPreset(p)"
                class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-all flex items-center gap-1.5 whitespace-nowrap"
                :style="activePresetId === p.id 
                  ? 'background: var(--accent-color); color: #fff; border-color: var(--accent-color);' 
                  : 'background: var(--bg-surface-elevated); color: var(--text-main); border-color: var(--border-color);'"
              >
                <span>{{ tData(p.name) }}</span>
              </button>
            </div>
            <p class="text-[11px]" style="color: var(--text-muted);">{{ tData(activePresetDesc) }}</p>
          </div>

          <div class="p-4 rounded-xl border space-y-2" style="background: var(--bg-surface); border-color: var(--border-color);">
            <label class="text-xs font-semibold tracking-wider block" style="color: var(--text-muted);">
              {{ t('pipeline.scopeLabel') }}
            </label>
            <select 
              v-model="selectedCollectionId" 
              class="w-full text-xs px-3 py-2 rounded-lg border outline-none font-medium"
              style="background: var(--bg-surface-elevated); border-color: var(--border-color); color: var(--text-main);"
            >
              <option :value="null">{{ t('pipeline.allIndexedOption') }}</option>
              <option v-for="col in collections" :key="col.id" :value="col.id">
                {{ tData(col.name) }} ({{ col.unit_count || 0 }})
              </option>
            </select>
          </div>
        </div>

        <!-- 2. 卡槽式流水线积木 (Level Slots) -->
        <div class="p-4 rounded-xl border space-y-3" style="background: var(--bg-surface); border-color: var(--border-color);">
          <div class="flex items-center justify-between">
            <label class="text-xs font-semibold tracking-wider flex items-center gap-2" style="color: var(--text-muted);">
              <span>{{ t('pipeline.blueprintLabel') }}</span>
            </label>
            <button 
              @click="addLevel"
              class="px-2.5 py-1 text-xs rounded-lg border transition-colors flex items-center gap-1 whitespace-nowrap"
              style="background: var(--bg-surface-elevated); border-color: var(--border-color); color: var(--accent-color);"
            >
              <span>{{ t('pipeline.addLevelBtn') }}</span>
            </button>
          </div>

          <div class="flex items-center gap-2 overflow-x-auto pb-2">
            <template v-for="(lvl, idx) in pipelineLevels" :key="idx">
              <!-- 卡槽卡片 -->
              <div 
                class="shrink-0 w-64 p-3 rounded-xl border relative shadow-sm transition-all"
                style="background: var(--bg-surface-elevated); border-color: var(--border-color);"
              >
                <div class="flex items-center justify-between mb-2">
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap" style="background: rgba(99, 102, 241, 0.15); color: var(--accent-color);">
                    {{ idx === pipelineLevels.length - 1 && lvl.naming ? t('pipeline.leafRuleBadge') : t('pipeline.levelBadge', { level: idx + 1 }) }}
                  </span>
                  <div class="flex items-center gap-1">
                    <button 
                      v-if="idx > 0 && !lvl.naming" 
                      @click="moveLevel(idx, -1)" 
                      class="p-1 hover:text-white text-gray-400 text-xs"
                    >◀</button>
                    <button 
                      v-if="idx < pipelineLevels.length - 2 && !lvl.naming" 
                      @click="moveLevel(idx, 1)" 
                      class="p-1 hover:text-white text-gray-400 text-xs"
                    >▶</button>
                    <button 
                      v-if="pipelineLevels.length > 2 && !lvl.naming" 
                      @click="removeLevel(idx)" 
                      class="p-1 hover:text-red-400 text-gray-400 text-xs"
                    >×</button>
                  </div>
                </div>

                <!-- 命名模式 -->
                <div v-if="lvl.naming" class="space-y-1">
                  <span class="text-xs font-medium block" style="color: var(--text-main);">{{ t('pipeline.namingTemplateLabel') }}</span>
                  <input 
                    v-model="lvl.naming" 
                    type="text" 
                    class="w-full text-xs px-2.5 py-1.5 rounded border outline-none font-mono"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-main);"
                  />
                </div>

                <!-- 条件分支模式 -->
                <div v-else-if="lvl.condition !== undefined && lvl.folder_name !== undefined" class="space-y-2">
                  <span class="text-xs font-medium block" style="color: var(--text-main);">{{ t('pipeline.conditionalBranchLabel') }}</span>
                  <input 
                    v-model="lvl.folder_name" 
                    type="text" 
                    class="w-full text-xs px-2.5 py-1.5 rounded border outline-none"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-main);"
                  />
                  <input 
                    v-model="lvl.condition" 
                    type="text" 
                    class="w-full text-[11px] px-2.5 py-1 rounded border outline-none font-mono text-gray-400"
                    style="background: var(--bg-surface); border-color: var(--border-color);"
                  />
                </div>

                <!-- 标签族提取模式 -->
                <div v-else class="space-y-2">
                  <span class="text-xs font-medium block" style="color: var(--text-main);">{{ t('pipeline.facetMappingLabel') }}</span>
                  <select 
                    v-model="lvl.facet" 
                    class="w-full text-xs px-2.5 py-1.5 rounded border outline-none"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-main);"
                  >
                    <option v-for="tc in projectableTagClasses" :key="tc.code" :value="`tag.${tc.code}`">
                      {{ tFacet(tc.code, tc.display_name) }}
                    </option>
                    <option value="collection.name">{{ t('pipeline.collectionNameOption') }}</option>
                  </select>
                  <input 
                    :value="tData(lvl.fallback)"
                    @input="lvl.fallback = $event.target.value"
                    :placeholder="t('pipeline.fallbackPlaceholder')"
                    type="text" 
                    class="w-full text-[11px] px-2.5 py-1 rounded border outline-none"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-muted);"
                  />
                </div>
              </div>

              <!-- 连接箭头 -->
              <div v-if="idx < pipelineLevels.length - 1" class="text-gray-500 font-bold shrink-0">➔</div>
            </template>
          </div>
        </div>

        <!-- 3. 动态目录树效果图例 -->
        <div class="p-4 rounded-xl border space-y-2" style="background: var(--bg-surface); border-color: var(--border-color);">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold tracking-wider" style="color: var(--text-muted);">
              {{ t('pipeline.livePreviewLabel') }}
            </span>
            <button 
              data-testid="pipeline-dryrun-btn"
              @click="runEvaluation" 
              :disabled="evaluating"
              class="px-4 py-1.5 rounded-lg text-xs font-bold text-white shadow-md transition-all flex items-center gap-1.5 whitespace-nowrap"
              style="background: var(--accent-color);"
            >
              <svg v-if="evaluating" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
              <span>{{ evaluating ? t('pipeline.runningDryRun') : t('pipeline.runDryRunBtn') }}</span>
            </button>
          </div>
          <div class="font-mono text-xs p-3 rounded-lg border overflow-x-auto space-y-1" style="background: rgba(0, 0, 0, 0.3); border-color: var(--border-color); color: var(--text-main);">
            <div>{{ t('pipeline.libraryRoot') }}</div>
            <div class="pl-4">├── 📁 {{ previewSampleSegment(0) }}/</div>
            <div class="pl-8">└── 📁 {{ previewSampleSegment(1) }}/</div>
            <div class="pl-12">└── 🎬 {{ previewSampleLeaf() }}</div>
          </div>
        </div>

        <!-- 4. 三色风险体检看板 (Dry-run Inspector) -->
        <div v-if="evaluationResult" ref="dryRunSectionRef" class="space-y-3 animate-fade-in">
          <!-- 统计指标卡 -->
          <div class="grid grid-cols-3 gap-3">
            <div class="p-3 rounded-xl border flex items-center justify-between" style="background: rgba(34, 197, 94, 0.08); border-color: rgba(34, 197, 94, 0.3);">
              <div>
                <span class="text-xs text-green-400 font-bold block whitespace-nowrap">{{ t('pipeline.safeLabel') }}</span>
                <span class="text-lg font-extrabold text-green-300 whitespace-nowrap">{{ t('pipeline.itemsUnit', { count: evaluationResult.stats?.safe_count || 0 }) }}</span>
              </div>
              <span class="text-xs text-green-500 font-mono whitespace-nowrap">{{ t('pipeline.safeSub') }}</span>
            </div>

            <div class="p-3 rounded-xl border flex items-center justify-between" style="background: rgba(234, 179, 8, 0.08); border-color: rgba(234, 179, 8, 0.3);">
              <div>
                <span class="text-xs text-yellow-400 font-bold block whitespace-nowrap">{{ t('pipeline.fallbackLabel') }}</span>
                <span class="text-lg font-extrabold text-yellow-300 whitespace-nowrap">{{ t('pipeline.itemsUnit', { count: evaluationResult.stats?.warning_count || 0 }) }}</span>
              </div>
              <span class="text-xs text-yellow-500 font-mono whitespace-nowrap">{{ t('pipeline.fallbackSub') }}</span>
            </div>

            <div class="p-3 rounded-xl border flex items-center justify-between" style="background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.3);">
              <div>
                <span class="text-xs text-red-400 font-bold block whitespace-nowrap">{{ t('pipeline.conflictsLabel') }}</span>
                <span class="text-lg font-extrabold text-red-300 whitespace-nowrap">{{ t('pipeline.itemsUnit', { count: evaluationResult.stats?.conflict_count || 0 }) }}</span>
              </div>
              <span class="text-xs text-red-500 font-mono whitespace-nowrap">{{ t('pipeline.conflictsSub') }}</span>
            </div>
          </div>

          <!-- 缺失分面降级提示条 (未分类资产降级提醒) -->
          <div v-if="evaluationResult.stats?.degraded_count > 0" class="p-2.5 rounded-xl border flex items-center justify-between text-xs bg-amber-500/10 border-amber-500/30 text-amber-200 gap-2">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-amber-400 font-bold text-sm shrink-0">⚠️</span>
              <span class="truncate">{{ t('pipeline.degradedNotice', { count: evaluationResult.stats.degraded_count }) }}</span>
            </div>
            <span class="text-[11px] text-amber-300/80 shrink-0 whitespace-nowrap">{{ t('pipeline.degradedHint') }}</span>
          </div>

          <!-- 详细对比表格 -->
          <div class="rounded-xl border overflow-hidden" style="border-color: var(--border-color);">
            <div class="max-h-56 overflow-y-auto">
              <table class="w-full text-left text-xs">
                <thead class="sticky top-0 border-b font-semibold" style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-muted);">
                  <tr>
                    <th class="p-2.5 w-14 text-center whitespace-nowrap">{{ t('pipeline.colStatus') }}</th>
                    <th class="p-2.5 whitespace-nowrap">{{ t('pipeline.colFileName') }}</th>
                    <th class="p-2.5 whitespace-nowrap">{{ t('pipeline.colSourcePath') }}</th>
                    <th class="p-2.5 whitespace-nowrap">{{ t('pipeline.colTargetPath') }}</th>
                  </tr>
                </thead>
                <tbody class="divide-y" style="divide-color: var(--border-color);">
                  <tr 
                    v-for="(act, aIdx) in evaluationResult.actions" 
                    :key="aIdx"
                    class="hover:bg-white/5 transition-colors"
                  >
                    <td class="p-2 text-center">
                      <span v-if="act.risk_level === 'safe'" class="text-green-400 font-bold">🟢</span>
                      <span v-else-if="act.risk_level === 'warning'" class="text-yellow-400 font-bold cursor-help" :title="act.risk_messages?.join(';\n')">🟡</span>
                      <span v-else class="text-red-400 font-bold cursor-help" :title="act.risk_messages?.join(';\n')">🔴</span>
                    </td>
                    <td class="p-2 font-medium max-w-[160px]" style="color: var(--text-main);" :title="act.file_name">
                      <div class="truncate">{{ act.file_name }}</div>
                      <div v-if="act.missing_facets?.length > 0" class="flex flex-wrap gap-1 mt-0.5">
                        <span v-for="mf in act.missing_facets" :key="mf" class="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 whitespace-nowrap">
                          {{ t('pipeline.missingFacetPrefix') }}{{ formatFacetName(mf) }}
                        </span>
                      </div>
                    </td>
                    <td class="p-2 font-mono text-[11px] max-w-[220px] truncate" style="color: var(--text-muted);" :title="act.src_path">
                      {{ formatDisplayPath(act.src_path) }}
                    </td>
                    <td class="p-2 font-mono text-[11px] max-w-[280px] truncate font-semibold" style="color: var(--accent-color);" :title="act.dst_path">
                      {{ formatDisplayPath(act.dst_path) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="flex items-center justify-between px-6 py-4 border-t shrink-0" style="border-color: var(--border-color); background: var(--bg-surface);">
        <div class="text-xs" style="color: var(--text-muted);">
          <span>{{ t('pipeline.footerSafeHint') }}</span>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          <button 
            @click="close"
            class="px-4 py-2 rounded-xl text-xs font-medium border hover:bg-white/10 transition-colors cursor-pointer whitespace-nowrap"
            style="border-color: var(--border-color); color: var(--text-main);"
          >
            {{ t('pipeline.cancelBtn') }}
          </button>

          <button 
            @click="confirmExecution"
            :disabled="executing || !evaluationResult || evaluationResult.stats?.conflict_count > 0 || evaluationResult.total_actions === 0"
            class="px-5 py-2 rounded-xl text-xs font-bold text-white shadow-lg transition-all flex items-center gap-2 cursor-pointer whitespace-nowrap"
            :style="!evaluationResult || evaluationResult.stats?.conflict_count > 0 || evaluationResult.total_actions === 0
              ? 'background: #6b7280; opacity: 0.5; cursor: not-allowed;' 
              : 'background: linear-gradient(135deg, var(--accent-color), #10b981);'"
          >
            <svg v-if="executing" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span>{{ executing ? t('pipeline.executingBtn') : t('pipeline.applyOrganizeBtn', { count: evaluationResult?.total_actions || 0 }) }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { fetchPipelinePresets, evaluatePipeline, executeTriagePlan, fetchCollections, fetchTagClasses } from '../api'
import { useMediaStore } from '../stores/mediaStore'
import { locale, t, tData, tFacet, tPath } from '../i18n'

const mediaStore = useMediaStore()
const dryRunSectionRef = ref(null)

const props = defineProps({
  isOpen: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'executed'])

const handleKeyDown = (e) => {
  if (e.key === 'Escape' && props.isOpen) {
    close()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

const presets = ref([])
const activePresetId = ref('category_standard')
const collections = ref([])
const selectedCollectionId = ref(null)
const tagClasses = ref([])

const projectableTagClasses = computed(() => {
  return tagClasses.value.filter(tc => tc.is_projectable !== false)
})

const pipelineLevels = ref([])
const evaluating = ref(false)
const executing = ref(false)
const evaluationResult = ref(null)

const activePresetDesc = computed(() => {
  const p = presets.value.find(item => item.id === activePresetId.value)
  return p?.description || ''
})

onMounted(async () => {
  try {
    const [pList, cList, tcList] = await Promise.all([
      fetchPipelinePresets(),
      fetchCollections(),
      fetchTagClasses()
    ])
    presets.value = pList || []
    collections.value = cList || []
    tagClasses.value = tcList || []
    if (presets.value.length > 0) {
      applyPreset(presets.value[0])
    }
  } catch (e) {
    console.error('Failed to load presets or collections:', e)
  }
})

function applyPreset(preset) {
  activePresetId.value = preset.id
  pipelineLevels.value = JSON.parse(JSON.stringify(preset.levels || []))
  evaluationResult.value = null
}

function addLevel() {
  const insertIdx = Math.max(0, pipelineLevels.value.length - 1)
  const defaultFacet = projectableTagClasses.value[0]?.code ? `tag.${projectableTagClasses.value[0].code}` : 'tag.domain'
  pipelineLevels.value.splice(insertIdx, 0, {
    level_index: insertIdx,
    facet: defaultFacet,
    fallback: '未分类'
  })
  evaluationResult.value = null
}

function removeLevel(idx) {
  pipelineLevels.value.splice(idx, 1)
  evaluationResult.value = null
}

function moveLevel(idx, offset) {
  const target = idx + offset
  if (target < 0 || target >= pipelineLevels.value.length - 1) return
  const temp = pipelineLevels.value[idx]
  pipelineLevels.value[idx] = pipelineLevels.value[target]
  pipelineLevels.value[target] = temp
  evaluationResult.value = null
}

function previewSampleSegment(idx) {
  if (idx >= pipelineLevels.value.length) return '...'
  const lvl = pipelineLevels.value[idx]
  if (lvl.folder_name) return tData(lvl.folder_name)
  if (lvl.facet?.startsWith('tag.')) {
    const code = lvl.facet.split('.')[1]
    const tc = tagClasses.value.find(c => c.code === code)
    const name = tFacet(code, tc?.display_name || code)
    return locale.value === 'en' ? `Sample ${name}` : `示例${name}`
  }
  if (lvl.facet === 'collection.name') return locale.value === 'en' ? 'Collection Folder' : '原系列目录'
  return locale.value === 'en' ? 'Category Folder' : '分类目录'
}

function previewSampleLeaf() {
  const sampleWork = locale.value === 'en' ? 'Sample_Media_Unit' : '示例作品'
  const last = pipelineLevels.value[pipelineLevels.value.length - 1]
  if (last?.naming) {
    return last.naming
      .replace(/%unique\{[^}]*\}/g, '')
      .replace(/\{unit\.title\}/g, sampleWork)
      .replace(/\{title\}/g, sampleWork)
      .replace(/\{meta\.code\}/g, 'ID001')
      .replace(/\{unit\.id\}/g, '101')
      .trim() || sampleWork
  }
  return sampleWork
}

function formatFacetName(code) {
  const tc = tagClasses.value.find(c => c.code === code)
  return tFacet(code, tc?.display_name || code)
}

function formatDisplayPath(fullPath) {
  if (!fullPath) return ''
  const root = evaluationResult.value?.target_root
  let formatted = fullPath
  if (root && fullPath.startsWith(root)) {
    const rel = fullPath.slice(root.length).replace(/^\/+/, '')
    formatted = `/媒体库/${rel}`
  } else {
    formatted = fullPath.replace(/^\/mnt\/media\/library\/?/, '/媒体库/')
  }
  return tPath(formatted)
}

async function runEvaluation() {
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
        name: '自定义整理流水线',
        target_root: targetRoot,
        levels: pipelineLevels.value
      },
      collection_id: selectedCollectionId.value
    }
    const res = await evaluatePipeline(payload)
    evaluationResult.value = res
    nextTick(() => {
      dryRunSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  } catch (err) {
    alert(`体检预演失败: ${err?.response?.data?.detail || err.message}`)
  } finally {
    evaluating.value = false
  }
}

async function confirmExecution() {
  if (!evaluationResult.value || evaluationResult.value.total_actions === 0) return
  if (!confirm(`确认要将这 ${evaluationResult.value.total_actions} 项资产按照当前流水线进行物理位移与数据库自愈吗？`)) {
    return
  }

  executing.value = true
  try {
    const triagePlan = {
      plan_id: `plan_${Date.now()}`,
      target_folder: evaluationResult.value.target_root,
      summary: `管线整理：${evaluationResult.value.pipeline_name}`,
      actions: evaluationResult.value.actions.map(act => ({
        action_type: 'move_file',
        src_path: act.src_path,
        dst_path: act.dst_path,
        description: `流水线归档：${act.file_name}`
      }))
    }
    const res = await executeTriagePlan(triagePlan, false)
    alert(`🎉 整理执行成功！已安全完成 ${res.executed_count} 项物理操作，数据库路径已自愈！`)
    emit('executed')
    close()
  } catch (err) {
    alert(`执行失败: ${err?.response?.data?.detail || err.message}`)
  } finally {
    executing.value = false
  }
}

function close() {
  emit('close')
}
</script>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}
.animate-fade-in {
  animation: fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
