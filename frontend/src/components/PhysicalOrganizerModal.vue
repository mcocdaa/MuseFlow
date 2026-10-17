<script setup>
import { ref, watch } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import {
  X,
  FolderCog,
  Calendar,
  FolderOutput,
  Layers,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Check,
  FileCheck,
  RefreshCw,
  FolderInput
} from 'lucide-vue-next'
import { planTriage, executeTriagePlan } from '../api'
import { t, tData } from '../i18n'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const folderPath = ref('')
const selectedRule = ref('metadata_normalization_and_dates')
const renameTemplate = ref('{title}')
const updateMtime = ref(true)
const untranslatedFolder = ref(t('physOrg.defaultUntranslated'))
const customMappingStr = ref('{\n  "Photography": ["*.png", "*.jpg"],\n  "Video Archive": ["*.mp4", "*.mkv"]\n}')

const loadingPlan = ref(false)
const executing = ref(false)
const planResult = ref(null)
const executionResult = ref(null)
const errorMsg = ref('')

watch(() => mediaStore.physicalOrganizerModalOpen, (isOpen) => {
  if (isOpen) {
    folderPath.value = mediaStore.physicalOrganizerTargetFolder || ''
    untranslatedFolder.value = t('physOrg.defaultUntranslated')
    planResult.value = null
    executionResult.value = null
    errorMsg.value = ''
  }
})

const closeModal = () => {
  if (executing.value) return
  mediaStore.physicalOrganizerModalOpen = false
}

const handleGeneratePlan = async () => {
  if (!folderPath.value.trim()) {
    errorMsg.value = t('physOrg.errEmptyFolder')
    return
  }

  errorMsg.value = ''
  loadingPlan.value = true
  planResult.value = null
  executionResult.value = null

  const options = {}
  if (selectedRule.value === 'metadata_normalization_and_dates') {
    options.rename_template = renameTemplate.value.trim() || '{title}'
    options.update_mtime_to_release = updateMtime.value
  } else if (selectedRule.value === 'workflow_subfolder_isolation') {
    options.untranslated_subfolder_name = untranslatedFolder.value.trim() || t('physOrg.defaultUntranslated')
  } else if (selectedRule.value === 'custom_topology') {
    try {
      options.topology_mapping = JSON.parse(customMappingStr.value)
    } catch (e) {
      errorMsg.value = t('physOrg.errInvalidJson')
      loadingPlan.value = false
      return
    }
  }

  try {
    const res = await planTriage(folderPath.value.trim(), selectedRule.value, options)
    planResult.value = res
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message || t('physOrg.errPlanFailed')
  } finally {
    loadingPlan.value = false
  }
}

const handleExecutePlan = async () => {
  if (!planResult.value) return
  if (!confirm(t('physOrg.confirmExecute', { count: planResult.value.total_actions }))) {
    return
  }

  executing.value = true
  errorMsg.value = ''

  try {
    const res = await executeTriagePlan(planResult.value, false)
    executionResult.value = res
    playerStore.showToast(t('physOrg.toastExecuted', { count: res.executed_count }))
    await Promise.all([
      mediaStore.loadCollections(),
      mediaStore.loadFeed(),
      mediaStore.loadWorkplaceItems(),
      mediaStore.checkMaintenance()
    ])
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message || t('physOrg.errExecuteFailed')
  } finally {
    executing.value = false
  }
}

const getActionBadgeClass = (actionType) => {
  switch (actionType) {
    case 'rename_dir':
      return 'bg-blue-500/20 text-blue-300 border-blue-500/30'
    case 'move_dir':
      return 'bg-purple-500/20 text-purple-300 border-purple-500/30'
    case 'set_mtime':
      return 'bg-amber-500/20 text-amber-300 border-amber-500/30'
    case 'create_dir':
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
    case 'move_file':
      return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
    default:
      return 'bg-gray-500/20 text-gray-300 border-gray-500/30'
  }
}

const getActionTypeName = (actionType) => {
  switch (actionType) {
    case 'rename_dir': return t('physOrg.actRenameDir')
    case 'move_dir': return t('physOrg.actMoveDir')
    case 'set_mtime': return t('physOrg.actSetMtime')
    case 'create_dir': return t('physOrg.actCreateDir')
    case 'move_file': return t('physOrg.actMoveFile')
    default: return actionType
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="mediaStore.physicalOrganizerModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md overflow-y-auto"
      @click.self="closeModal"
    >
      <div
        class="w-full max-w-2xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[88vh] transition-all my-auto"
        style="background-color: var(--bg-surface-elevated);"
      >
        <!-- Single-Line Minimalist Header -->
        <div class="px-5 py-3.5 border-b border-white/5 flex items-center justify-between">
          <div
            class="flex items-center gap-2.5"
            :title="t('physOrg.headerTip')"
          >
            <div class="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300">
              <FolderCog class="w-4 h-4" />
            </div>
            <h3 class="text-sm font-semibold text-white">{{ t('physOrg.title') }}</h3>
          </div>
          <button
            @click="closeModal"
            class="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
            :title="t('common.close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-5 space-y-4 overflow-y-auto flex-grow text-xs">
          <!-- Target Scope Input -->
          <div class="relative" :title="t('physOrg.scopeTip')">
            <input
              v-model="folderPath"
              type="text"
              :placeholder="t('physOrg.folderPlaceholder')"
              class="w-full bg-black/30 border border-white/10 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-amber-500/50 font-mono"
            />
            <FolderInput class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          </div>

          <!-- Single-Line Strategy Segmented Tabs -->
          <div class="grid grid-cols-3 gap-2">
            <button
              @click="selectedRule = 'metadata_normalization_and_dates'"
              :title="t('physOrg.ruleDatesTip')"
              class="px-3 py-2 rounded-xl border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
              :class="[
                selectedRule === 'metadata_normalization_and_dates'
                  ? 'bg-amber-500/15 border-amber-500/40 text-amber-200'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
              ]"
            >
              <Calendar class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{{ t('physOrg.ruleDates') }}</span>
            </button>

            <button
              @click="selectedRule = 'workflow_subfolder_isolation'"
              :title="t('physOrg.ruleWorkflowTip')"
              class="px-3 py-2 rounded-xl border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
              :class="[
                selectedRule === 'workflow_subfolder_isolation'
                  ? 'bg-purple-500/15 border-purple-500/40 text-purple-200'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
              ]"
            >
              <FolderOutput class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{{ t('physOrg.ruleWorkflow') }}</span>
            </button>

            <button
              @click="selectedRule = 'custom_topology'"
              :title="t('physOrg.ruleWildcardTip')"
              class="px-3 py-2 rounded-xl border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
              :class="[
                selectedRule === 'custom_topology'
                  ? 'bg-blue-500/15 border-blue-500/40 text-blue-200'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
              ]"
            >
              <Layers class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{{ t('physOrg.ruleWildcard') }}</span>
            </button>
          </div>

          <!-- Strategy Options -->
          <div class="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 space-y-2.5">
            <div v-if="selectedRule === 'metadata_normalization_and_dates'" class="space-y-2.5">
              <div class="flex items-center gap-2">
                <span
                  class="text-[11px] text-gray-400 shrink-0"
                  :title="t('physOrg.templateVarsTip')"
                >
                  {{ t('physOrg.templateLabel') }}
                </span>
                <input
                  v-model="renameTemplate"
                  type="text"
                  :title="t('physOrg.templateInputTip')"
                  class="flex-1 bg-black/30 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-amber-500/50"
                  :placeholder="t('physOrg.templatePlaceholder')"
                />
              </div>
              <label class="flex items-center gap-2 text-xs text-gray-300 select-none cursor-pointer">
                <input
                  type="checkbox"
                  v-model="updateMtime"
                  class="rounded bg-black/40 border-white/20 text-amber-500 focus:ring-0"
                />
                <span>{{ t('physOrg.alignMtimeCheckbox') }}</span>
              </label>
            </div>

            <div v-else-if="selectedRule === 'workflow_subfolder_isolation'" class="flex items-center gap-2">
              <span class="text-[11px] text-gray-400 shrink-0">{{ t('physOrg.targetSubdirLabel') }}</span>
              <input
                v-model="untranslatedFolder"
                type="text"
                class="flex-1 bg-black/30 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500/50"
                :placeholder="t('physOrg.defaultUntranslated')"
              />
            </div>

            <div v-else-if="selectedRule === 'custom_topology'" class="space-y-1.5">
              <span class="text-[11px] text-gray-400 block" :title="t('physOrg.mappingJsonTip')">
                {{ t('physOrg.mappingJsonLabel') }}
              </span>
              <textarea
                v-model="customMappingStr"
                rows="3"
                class="w-full bg-black/30 border border-white/10 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          <!-- Error Feedback -->
          <div v-if="errorMsg" class="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex items-start gap-2">
            <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
            <div class="leading-relaxed">{{ errorMsg }}</div>
          </div>

          <!-- Dry-Run Preview Table -->
          <div v-if="planResult" class="space-y-2.5">
            <div class="flex items-center justify-between" :title="tData(planResult.summary)">
              <div class="flex items-center gap-1.5">
                <FileCheck class="w-3.5 h-3.5 text-emerald-400" />
                <span class="font-semibold text-gray-200">{{ t('physOrg.previewListTitle', { count: planResult.total_actions }) }}</span>
              </div>
              <span class="text-[11px] text-gray-500">{{ t('physOrg.autoSyncNote') }}</span>
            </div>

            <div class="border border-white/10 rounded-xl overflow-hidden max-h-52 overflow-y-auto">
              <table class="w-full text-left text-[11px]">
                <thead class="bg-white/5 border-b border-white/10 text-gray-400 font-medium">
                  <tr>
                    <th class="py-2 px-3">{{ t('physOrg.colAction') }}</th>
                    <th class="py-2 px-3">{{ t('physOrg.colSource') }}</th>
                    <th class="py-2 px-3">{{ t('physOrg.colTarget') }}</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-white/5 font-mono">
                  <tr v-for="(act, idx) in planResult.actions" :key="idx" class="hover:bg-white/[0.02]">
                    <td class="py-2 px-3 whitespace-nowrap">
                      <span class="px-1.5 py-0.5 rounded border text-[10px]" :class="getActionBadgeClass(act.action_type)">
                        {{ getActionTypeName(act.action_type) }}
                      </span>
                    </td>
                    <td class="py-2 px-3 text-gray-300 truncate max-w-xs" :title="act.src_path">
                      {{ act.src_path.split('/').pop() }}
                    </td>
                    <td class="py-2 px-3 text-amber-300/90 truncate max-w-sm">
                      <div v-if="act.action_type === 'set_mtime'" class="flex items-center gap-1 text-amber-400">
                        <Clock class="w-3 h-3" />
                        <span>{{ tData(act.description) }}</span>
                      </div>
                      <div v-else-if="act.dst_path" class="flex items-center gap-1.5">
                        <ArrowRight class="w-3 h-3 text-gray-500 shrink-0" />
                        <span class="text-white truncate" :title="act.dst_path">{{ act.dst_path.split('/').pop() }}</span>
                      </div>
                      <div v-else class="text-gray-400">
                        {{ tData(act.description) }}
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Execution Success Notice -->
          <div v-if="executionResult" class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <CheckCircle2 class="w-4 h-4 text-emerald-400" />
              <span>{{ t('physOrg.executedSuccess', { count: executionResult.executed_count }) }}</span>
            </div>
            <button
              @click="closeModal"
              class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-all cursor-pointer"
            >
              {{ t('common.done') }}
            </button>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-5 py-3.5 border-t border-white/5 flex items-center justify-end gap-2">
          <button
            @click="handleGeneratePlan"
            :disabled="loadingPlan || executing || !folderPath.trim()"
            class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-white font-medium transition-all disabled:opacity-40 text-xs cursor-pointer"
            :title="t('physOrg.dryRunBtnTip')"
          >
            <RefreshCw v-if="loadingPlan" class="w-3.5 h-3.5 animate-spin" />
            <FileCheck v-else class="w-3.5 h-3.5 text-amber-400" />
            <span>{{ t('physOrg.dryRunBtn') }}</span>
          </button>

          <button
            v-if="planResult && planResult.total_actions > 0"
            @click="handleExecutePlan"
            :disabled="executing || loadingPlan"
            class="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium transition-all disabled:opacity-40 text-xs cursor-pointer"
          >
            <RefreshCw v-if="executing" class="w-3.5 h-3.5 animate-spin" />
            <Check v-else class="w-3.5 h-3.5" />
            <span>{{ t('physOrg.executeBtn') }}</span>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
