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

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const folderPath = ref('')
const selectedRule = ref('metadata_normalization_and_dates')
const renameTemplate = ref('{title}')
const updateMtime = ref(true)
const untranslatedFolder = ref('待整理')
const customMappingStr = ref('{\n  "视觉摄影": ["*.png", "*.jpg"],\n  "视频归档": ["*.mp4", "*.mkv"]\n}')

const loadingPlan = ref(false)
const executing = ref(false)
const planResult = ref(null)
const executionResult = ref(null)
const errorMsg = ref('')

watch(() => mediaStore.physicalOrganizerModalOpen, (isOpen) => {
  if (isOpen) {
    folderPath.value = mediaStore.physicalOrganizerTargetFolder || ''
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
    errorMsg.value = '请输入目标文件夹路径'
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
    options.untranslated_subfolder_name = untranslatedFolder.value.trim() || '待整理'
  } else if (selectedRule.value === 'custom_topology') {
    try {
      options.topology_mapping = JSON.parse(customMappingStr.value)
    } catch (e) {
      errorMsg.value = '自定义拓扑 JSON 格式有误'
      loadingPlan.value = false
      return
    }
  }

  try {
    const res = await planTriage(folderPath.value.trim(), selectedRule.value, options)
    planResult.value = res
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message || '生成预演方案失败'
  } finally {
    loadingPlan.value = false
  }
}

const handleExecutePlan = async () => {
  if (!planResult.value) return
  if (!confirm(`确定执行共 ${planResult.value.total_actions} 项物理整理操作吗？数据库索引与收藏评分将自动同步保留。`)) {
    return
  }

  executing.value = true
  errorMsg.value = ''

  try {
    const res = await executeTriagePlan(planResult.value, false)
    executionResult.value = res
    playerStore.showToast(`已完成 ${res.executed_count} 项物理整理`)
    await Promise.all([
      mediaStore.loadCollections(),
      mediaStore.loadFeed(),
      mediaStore.loadWorkplaceItems(),
      mediaStore.checkMaintenance()
    ])
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message || '执行物理整理失败'
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
    case 'rename_dir': return '目录改名'
    case 'move_dir': return '目录迁移'
    case 'set_mtime': return '日期对齐'
    case 'create_dir': return '新建目录'
    case 'move_file': return '文件归档'
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
            title="受控目录物理整理，自动同步数据库索引、标签关联与评分记录"
          >
            <div class="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300">
              <FolderCog class="w-4 h-4" />
            </div>
            <h3 class="text-sm font-semibold text-white">物理目录整理</h3>
          </div>
          <button
            @click="closeModal"
            class="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
            title="关闭"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-5 space-y-4 overflow-y-auto flex-grow text-xs">
          <!-- Target Scope Input -->
          <div class="relative" title="仅整理此路径下的文件与子目录，其他目录绝不触碰">
            <input
              v-model="folderPath"
              type="text"
              placeholder="目标文件夹路径 (例如: /mnt/media/Unsorted)"
              class="w-full bg-black/30 border border-white/10 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-amber-500/50 font-mono"
            />
            <FolderInput class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          </div>

          <!-- Single-Line Strategy Segmented Tabs -->
          <div class="grid grid-cols-3 gap-2">
            <button
              @click="selectedRule = 'metadata_normalization_and_dates'"
              title="按命名模版规范作品目录名，并将文件夹修改时间对齐至发布日期"
              class="px-3 py-2 rounded-xl border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
              :class="[
                selectedRule === 'metadata_normalization_and_dates'
                  ? 'bg-amber-500/15 border-amber-500/40 text-amber-200'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
              ]"
            >
              <Calendar class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">命名与日期对齐</span>
            </button>

            <button
              @click="selectedRule = 'workflow_subfolder_isolation'"
              title="将尚未附加字幕或待处理的作品集中移入指定子目录"
              class="px-3 py-2 rounded-xl border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
              :class="[
                selectedRule === 'workflow_subfolder_isolation'
                  ? 'bg-purple-500/15 border-purple-500/40 text-purple-200'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
              ]"
            >
              <FolderOutput class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">待处理子目录分流</span>
            </button>

            <button
              @click="selectedRule = 'custom_topology'"
              title="根据文件通配符规则将散落文件归档至对应子目录"
              class="px-3 py-2 rounded-xl border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer"
              :class="[
                selectedRule === 'custom_topology'
                  ? 'bg-blue-500/15 border-blue-500/40 text-blue-200'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
              ]"
            >
              <Layers class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">通配符规则归档</span>
            </button>
          </div>

          <!-- Strategy Options -->
          <div class="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 space-y-2.5">
            <div v-if="selectedRule === 'metadata_normalization_and_dates'" class="space-y-2.5">
              <div class="flex items-center gap-2">
                <span
                  class="text-[11px] text-gray-400 shrink-0"
                  title="支持变量：{title} (作品标题)、{code} (作品编号)"
                >
                  命名模版
                </span>
                <input
                  v-model="renameTemplate"
                  type="text"
                  title="支持变量：{title}、{code}（如：{title} 或 [{code}] {title}）"
                  class="flex-1 bg-black/30 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-amber-500/50"
                  placeholder="例如: {title} 或 [{code}] {title}"
                />
              </div>
              <label class="flex items-center gap-2 text-xs text-gray-300 select-none cursor-pointer">
                <input
                  type="checkbox"
                  v-model="updateMtime"
                  class="rounded bg-black/40 border-white/20 text-amber-500 focus:ring-0"
                />
                <span>将文件夹物理修改时间对齐至作品发布日期</span>
              </label>
            </div>

            <div v-else-if="selectedRule === 'workflow_subfolder_isolation'" class="flex items-center gap-2">
              <span class="text-[11px] text-gray-400 shrink-0">目标子目录</span>
              <input
                v-model="untranslatedFolder"
                type="text"
                class="flex-1 bg-black/30 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500/50"
                placeholder="待整理"
              />
            </div>

            <div v-else-if="selectedRule === 'custom_topology'" class="space-y-1.5">
              <span class="text-[11px] text-gray-400 block" title="JSON 格式：目标子目录 ➔ 通配符数组">
                归档映射 (JSON)
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
            <div class="flex items-center justify-between" :title="planResult.summary">
              <div class="flex items-center gap-1.5">
                <FileCheck class="w-3.5 h-3.5 text-emerald-400" />
                <span class="font-semibold text-gray-200">预演清单 ({{ planResult.total_actions }})</span>
              </div>
              <span class="text-[11px] text-gray-500">执行后自动更新数据库索引</span>
            </div>

            <div class="border border-white/10 rounded-xl overflow-hidden max-h-52 overflow-y-auto">
              <table class="w-full text-left text-[11px]">
                <thead class="bg-white/5 border-b border-white/10 text-gray-400 font-medium">
                  <tr>
                    <th class="py-2 px-3">动作</th>
                    <th class="py-2 px-3">原项</th>
                    <th class="py-2 px-3">目标变更</th>
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
                        <span>{{ act.description }}</span>
                      </div>
                      <div v-else-if="act.dst_path" class="flex items-center gap-1.5">
                        <ArrowRight class="w-3 h-3 text-gray-500 shrink-0" />
                        <span class="text-white truncate" :title="act.dst_path">{{ act.dst_path.split('/').pop() }}</span>
                      </div>
                      <div v-else class="text-gray-400">
                        {{ act.description }}
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
              <span>已完成 {{ executionResult.executed_count }} 项物理操作</span>
            </div>
            <button
              @click="closeModal"
              class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-all cursor-pointer"
            >
              完成
            </button>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-5 py-3.5 border-t border-white/5 flex items-center justify-end gap-2">
          <button
            @click="handleGeneratePlan"
            :disabled="loadingPlan || executing || !folderPath.trim()"
            class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-white font-medium transition-all disabled:opacity-40 text-xs cursor-pointer"
            title="预演计算物理整理变更，不修改磁盘文件"
          >
            <RefreshCw v-if="loadingPlan" class="w-3.5 h-3.5 animate-spin" />
            <FileCheck v-else class="w-3.5 h-3.5 text-amber-400" />
            <span>预演</span>
          </button>

          <button
            v-if="planResult && planResult.total_actions > 0"
            @click="handleExecutePlan"
            :disabled="executing || loadingPlan"
            class="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium transition-all disabled:opacity-40 text-xs cursor-pointer"
          >
            <RefreshCw v-if="executing" class="w-3.5 h-3.5 animate-spin" />
            <Check v-else class="w-3.5 h-3.5" />
            <span>确认执行</span>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
