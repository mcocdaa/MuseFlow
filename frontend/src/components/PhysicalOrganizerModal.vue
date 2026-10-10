<script setup>
import { ref, watch, computed } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import {
  X,
  FolderCog,
  Calendar,
  Languages,
  Layers,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  FileCheck,
  RefreshCw,
  FolderInput
} from 'lucide-vue-next'
import { planTriage, executeTriagePlan } from '../api'

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const folderPath = ref('')
const selectedRule = ref('rj_normalization_and_dates')
const renameTemplate = ref('[{rj_code}] {title}')
const updateMtime = ref(true)
const untranslatedFolder = ref('待翻译')
const customMappingStr = ref('{\n  "壁纸/二次元": ["*wallpaper*", "*anime*"],\n  "插画/散落": ["*.png", "*.jpg"]\n}')

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
    errorMsg.value = '请输入需要进行物理整理的目标文件夹路径'
    return
  }

  errorMsg.value = ''
  loadingPlan.value = true
  planResult.value = null
  executionResult.value = null

  const options = {}
  if (selectedRule.value === 'rj_normalization_and_dates') {
    options.rename_template = renameTemplate.value.trim() || '[{rj_code}] {title}'
    options.update_mtime_to_release = updateMtime.value
  } else if (selectedRule.value === 'rj_separate_untranslated') {
    options.untranslated_subfolder_name = untranslatedFolder.value.trim() || '待翻译'
  } else if (selectedRule.value === 'custom_topology') {
    try {
      options.topology_mapping = JSON.parse(customMappingStr.value)
    } catch (e) {
      errorMsg.value = '自定义拓扑 JSON 格式有误，请检查语法'
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
  if (!confirm(`确定要执行此物理整理方案吗？\n\n共 ${planResult.value.total_actions} 项磁盘操作。\n系统将在操作期间设置维护锁，并自动同步更新数据库索引与播放记录。`)) {
    return
  }

  executing.value = true
  errorMsg.value = ''

  try {
    const res = await executeTriagePlan(planResult.value, false)
    executionResult.value = res
    playerStore.showToast(`物理整理成功！已安全完成 ${res.executed_count} 项磁盘与索引同步。`)
    // 刷新媒体库与系列
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
    case 'rename_dir': return '目录规范改名'
    case 'move_dir': return '目录物理迁移'
    case 'set_mtime': return '发售日期对齐'
    case 'create_dir': return '创建目标目录'
    case 'move_file': return '散落文件归类'
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
        class="w-full max-w-3xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[90vh] transition-all my-auto"
        style="background-color: var(--bg-surface-elevated);"
      >
        <!-- Modal Header -->
        <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300 shadow-inner">
              <FolderCog class="w-5 h-5" />
            </div>
            <div>
              <h3 class="text-base font-semibold text-white flex items-center gap-2">
                <span>物理磁盘整理向导</span>
                <span class="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">
                  Physical Triage
                </span>
              </h3>
              <p class="text-xs text-gray-400 mt-0.5">
                受控作用域物理重组 · 真实发布时间戳对齐 · 数据库索引与打分原子自愈
              </p>
            </div>
          </div>
          <button
            @click="closeModal"
            class="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-6 space-y-5 overflow-y-auto flex-grow text-xs">
          <!-- Target Scope Input -->
          <div>
            <label class="block text-xs font-semibold text-gray-300 mb-1.5 flex items-center justify-between">
              <span>整理作用域文件夹路径 (其他目录绝不触碰)：</span>
            </label>
            <div class="relative">
              <input
                v-model="folderPath"
                type="text"
                placeholder="例如: /mnt/z/mcoc/音声/待分类 或 D:\Media\Unsorted"
                class="w-full bg-black/40 border border-white/10 rounded-xl pl-9 pr-3.5 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-amber-500/50 font-mono"
              />
              <FolderInput class="w-4 h-4 text-gray-400 absolute left-3 top-3" />
            </div>
          </div>

          <!-- Strategy Selection Cards -->
          <div>
            <label class="block text-xs font-semibold text-gray-300 mb-2">选择整理策略方案：</label>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <!-- Strategy 1: RJ Normalization & Dates -->
              <div
                @click="selectedRule = 'rj_normalization_and_dates'"
                class="p-3.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between"
                :class="[
                  selectedRule === 'rj_normalization_and_dates'
                    ? 'bg-amber-500/10 border-amber-500/40 text-white shadow-md'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
                ]"
              >
                <div>
                  <div class="flex items-center gap-2 font-semibold text-xs text-amber-300">
                    <Calendar class="w-4 h-4" />
                    <span>RJ规范化与发售时间</span>
                  </div>
                  <p class="text-[11px] text-gray-400 mt-1 leading-snug">
                    格式化为 [RJxxxx] 标题，并将文件夹真实修改时间修改为官方发售日期。
                  </p>
                </div>
              </div>

              <!-- Strategy 2: Untranslated Isolation -->
              <div
                @click="selectedRule = 'rj_separate_untranslated'"
                class="p-3.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between"
                :class="[
                  selectedRule === 'rj_separate_untranslated'
                    ? 'bg-purple-500/10 border-purple-500/40 text-white shadow-md'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
                ]"
              >
                <div>
                  <div class="flex items-center gap-2 font-semibold text-xs text-purple-300">
                    <Languages class="w-4 h-4" />
                    <span>未汉化音声隔离</span>
                  </div>
                  <p class="text-[11px] text-gray-400 mt-1 leading-snug">
                    自动探测中文字幕与汉化标，将生肉作品物理隔离移动至「待翻译」目录。
                  </p>
                </div>
              </div>

              <!-- Strategy 3: Custom / Loose Media Topology -->
              <div
                @click="selectedRule = 'custom_topology'"
                class="p-3.5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between"
                :class="[
                  selectedRule === 'custom_topology'
                    ? 'bg-blue-500/10 border-blue-500/40 text-white shadow-md'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200 hover:bg-white/5'
                ]"
              >
                <div>
                  <div class="flex items-center gap-2 font-semibold text-xs text-blue-300">
                    <Layers class="w-4 h-4" />
                    <span>自定义规则拓扑</span>
                  </div>
                  <p class="text-[11px] text-gray-400 mt-1 leading-snug">
                    与 Agent 商讨规划出的文件夹规则结构，将散落文件归入目标子目录。
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Strategy Options Details -->
          <div class="p-3.5 rounded-xl bg-white/[0.03] border border-white/5 space-y-3">
            <!-- Options for RJ Normalization -->
            <div v-if="selectedRule === 'rj_normalization_and_dates'" class="space-y-2.5">
              <div>
                <label class="block text-[11px] font-medium text-gray-400 mb-1">
                  目标文件夹重命名模版：
                </label>
                <input
                  v-model="renameTemplate"
                  type="text"
                  class="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-amber-500/50"
                  placeholder="[{rj_code}] {title}"
                />
              </div>
              <div class="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="updateMtimeCheck"
                  v-model="updateMtime"
                  class="rounded bg-black/40 border-white/20 text-amber-500 focus:ring-0"
                />
                <label for="updateMtimeCheck" class="text-xs text-gray-300 select-none cursor-pointer">
                  修改文件夹物理时间戳为 DLsite / asmr.one 官方发售日期（便于系统文件管理器按时间精准排列）
                </label>
              </div>
            </div>

            <!-- Options for Untranslated -->
            <div v-else-if="selectedRule === 'rj_separate_untranslated'" class="space-y-2">
              <label class="block text-[11px] font-medium text-gray-400 mb-1">
                生肉/未翻译作品的目标子目录名称：
              </label>
              <input
                v-model="untranslatedFolder"
                type="text"
                class="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500/50"
                placeholder="待翻译"
              />
            </div>

            <!-- Options for Custom Topology -->
            <div v-else-if="selectedRule === 'custom_topology'" class="space-y-2">
              <label class="block text-[11px] font-medium text-gray-400 mb-1">
                分类映射配置 (JSON 格式：子目录 ➔ 匹配文件模式通配符)：
              </label>
              <textarea
                v-model="customMappingStr"
                rows="4"
                class="w-full bg-black/40 border border-white/10 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          <!-- Error Feedback -->
          <div v-if="errorMsg" class="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex items-start gap-2">
            <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
            <div class="leading-relaxed">{{ errorMsg }}</div>
          </div>

          <!-- Dry-Run Preview Table -->
          <div v-if="planResult" class="space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <FileCheck class="w-4 h-4 text-emerald-400" />
                <span class="font-semibold text-gray-200">预演清单：共规划 {{ planResult.total_actions }} 项物理动作</span>
              </div>
              <span class="text-[11px] text-gray-400 font-mono">
                {{ planResult.summary }}
              </span>
            </div>

            <div class="border border-white/10 rounded-xl overflow-hidden max-h-56 overflow-y-auto">
              <table class="w-full text-left text-[11px]">
                <thead class="bg-white/5 border-b border-white/10 text-gray-400 font-medium">
                  <tr>
                    <th class="py-2 px-3">操作类型</th>
                    <th class="py-2 px-3">原路径 / 目标项</th>
                    <th class="py-2 px-3">计划变更</th>
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

            <!-- Execution Safeguard Notice -->
            <div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 flex items-start gap-2">
              <AlertTriangle class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div class="text-[11px] leading-relaxed">
                <span class="font-semibold text-amber-200">数据安全自愈保障：</span>
                执行物理改名或迁移后，系统会自动更新 SQLite 数据库索引。您的评分星级、收藏状态、播放历史与停留统计将无缝延续，绝不会因文件移动而丢失。
              </div>
            </div>
          </div>

          <!-- Execution Success Notice -->
          <div v-if="executionResult" class="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <CheckCircle2 class="w-5 h-5 text-emerald-400" />
              <div>
                <div class="font-semibold text-xs text-white">整理执行成功！</div>
                <div class="text-[11px] text-emerald-300/80 mt-0.5">
                  已完成 {{ executionResult.executed_count }} 项物理操作，相关媒体数据库路径已自动更新。
                </div>
              </div>
            </div>
            <button
              @click="closeModal"
              class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-all"
            >
              完成并关闭
            </button>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-6 py-4 border-t border-white/10 flex items-center justify-between bg-white/[0.02]">
          <span class="text-[11px] text-gray-500 font-mono">
            {{ planResult ? `预演完成 (${planResult.actions.length} 动向待确认)` : '请配置规则并点击预演分析' }}
          </span>

          <div class="flex items-center gap-2.5">
            <button
              @click="closeModal"
              :disabled="executing"
              class="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white font-medium transition-all text-xs"
            >
              取消
            </button>

            <!-- Dry Run Button -->
            <button
              @click="handleGeneratePlan"
              :disabled="loadingPlan || executing || !folderPath.trim()"
              class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white font-medium transition-all disabled:opacity-40 text-xs shadow-sm"
            >
              <RefreshCw v-if="loadingPlan" class="w-3.5 h-3.5 animate-spin" />
              <FileCheck v-else class="w-3.5 h-3.5 text-amber-400" />
              <span>{{ loadingPlan ? '正在计算预演方案...' : '🔍 预演分析 (Dry-Run)' }}</span>
            </button>

            <!-- Real Execute Button -->
            <button
              v-if="planResult && planResult.total_actions > 0"
              @click="handleExecutePlan"
              :disabled="executing || loadingPlan"
              class="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium transition-all disabled:opacity-40 text-xs shadow-md active:scale-95"
            >
              <RefreshCw v-if="executing" class="w-3.5 h-3.5 animate-spin" />
              <Sparkles v-else class="w-3.5 h-3.5" />
              <span>{{ executing ? '正在安全搬迁中...' : '🚀 确认执行物理整理' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
