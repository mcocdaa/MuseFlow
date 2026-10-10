<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
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
            <h3 class="text-lg font-bold" style="color: var(--text-main);">智能文件夹整理流水线 (Pipeline Builder)</h3>
            <p class="text-xs" style="color: var(--text-muted);">
              将多维标签投影至规范文件树 · 自动落点锚定 · Beets 级 %unique{} 自适应消歧
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
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- 1. 预设选择器与目标根目录 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl border space-y-2 md:col-span-2" style="background: var(--bg-surface); border-color: var(--border-color);">
            <label class="text-xs font-semibold uppercase tracking-wider block" style="color: var(--text-muted);">
              ⭐ 快速套用收纳预设模板
            </label>
            <div class="flex flex-wrap gap-2">
              <button 
                v-for="p in presets" 
                :key="p.id"
                @click="applyPreset(p)"
                class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-all flex items-center gap-1.5"
                :style="activePresetId === p.id 
                  ? 'background: var(--accent-color); color: #fff; border-color: var(--accent-color);' 
                  : 'background: var(--bg-surface-elevated); color: var(--text-main); border-color: var(--border-color);'"
              >
                <span>{{ p.name }}</span>
              </button>
            </div>
            <p class="text-[11px]" style="color: var(--text-muted);">{{ activePresetDesc }}</p>
          </div>

          <div class="p-4 rounded-xl border space-y-2" style="background: var(--bg-surface); border-color: var(--border-color);">
            <label class="text-xs font-semibold uppercase tracking-wider block" style="color: var(--text-muted);">
              🎯 整理目标作用域 (Collection)
            </label>
            <select 
              v-model="selectedCollectionId" 
              class="w-full text-xs px-3 py-2 rounded-lg border outline-none font-medium"
              style="background: var(--bg-surface-elevated); border-color: var(--border-color); color: var(--text-main);"
            >
              <option :value="null">全部已纳管资产 (前 300 部)</option>
              <option v-for="col in collections" :key="col.id" :value="col.id">
                {{ col.name }} ({{ col.unit_count || 0 }}项)
              </option>
            </select>
          </div>
        </div>

        <!-- 2. 卡槽式流水线积木 (Level Slots) -->
        <div class="p-4 rounded-xl border space-y-3" style="background: var(--bg-surface); border-color: var(--border-color);">
          <div class="flex items-center justify-between">
            <label class="text-xs font-semibold uppercase tracking-wider flex items-center gap-2" style="color: var(--text-muted);">
              <span>🔨 文件夹层级卡槽链 (从左至右代表从外向内的子目录)</span>
            </label>
            <button 
              @click="addLevel"
              class="px-2.5 py-1 text-xs rounded-lg border transition-colors flex items-center gap-1"
              style="background: var(--bg-surface-elevated); border-color: var(--border-color); color: var(--accent-color);"
            >
              <span>+ 添加中间层级</span>
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
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background: rgba(99, 102, 241, 0.15); color: var(--accent-color);">
                    {{ idx === pipelineLevels.length - 1 && lvl.naming ? 'Leaf (最终命名)' : `Level ${idx} 目录` }}
                  </span>
                  <div class="flex items-center gap-1">
                    <button 
                      v-if="idx > 0 && !lvl.naming" 
                      @click="moveLevel(idx, -1)" 
                      title="左移层级"
                      class="p-1 hover:text-white text-gray-400 text-xs"
                    >◀</button>
                    <button 
                      v-if="idx < pipelineLevels.length - 2 && !lvl.naming" 
                      @click="moveLevel(idx, 1)" 
                      title="右移层级"
                      class="p-1 hover:text-white text-gray-400 text-xs"
                    >▶</button>
                    <button 
                      v-if="pipelineLevels.length > 2 && !lvl.naming" 
                      @click="removeLevel(idx)" 
                      title="删除此层"
                      class="p-1 hover:text-red-400 text-gray-400 text-xs"
                    >×</button>
                  </div>
                </div>

                <!-- 命名模式 -->
                <div v-if="lvl.naming" class="space-y-1">
                  <span class="text-xs font-medium block" style="color: var(--text-main);">实体命名模版</span>
                  <input 
                    v-model="lvl.naming" 
                    type="text" 
                    class="w-full text-xs px-2.5 py-1.5 rounded border outline-none font-mono"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-main);"
                  />
                  <p class="text-[10px]" style="color: var(--text-muted);">
                    支持 %unique{} 自适应消歧、{unit.title}、[{meta.rj_code}]
                  </p>
                </div>

                <!-- 条件分支模式 -->
                <div v-else-if="lvl.condition !== undefined && lvl.folder_name !== undefined" class="space-y-2">
                  <span class="text-xs font-medium block" style="color: var(--text-main);">条件分支分流</span>
                  <input 
                    v-model="lvl.folder_name" 
                    placeholder="如: 待翻译"
                    type="text" 
                    class="w-full text-xs px-2.5 py-1.5 rounded border outline-none"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-main);"
                  />
                  <input 
                    v-model="lvl.condition" 
                    placeholder="条件表达式 (如 not unit['has_translation'])"
                    type="text" 
                    class="w-full text-[11px] px-2.5 py-1 rounded border outline-none font-mono text-gray-400"
                    style="background: var(--bg-surface); border-color: var(--border-color);"
                  />
                </div>

                <!-- 标签族提取模式 -->
                <div v-else class="space-y-2">
                  <span class="text-xs font-medium block" style="color: var(--text-main);">标签族属性映射</span>
                  <select 
                    v-model="lvl.facet" 
                    class="w-full text-xs px-2.5 py-1.5 rounded border outline-none"
                    style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-main);"
                  >
                    <option value="tag.domain">✨ 题材流派 (Domain: 助眠/催眠等)</option>
                    <option value="tag.creator">👥 创作者/社团 (Creator)</option>
                    <option value="tag.media_kind">🎬 媒体形态 (MediaKind: 音频/视频)</option>
                    <option value="tag.workflow">🌿 状态分流 (Workflow)</option>
                    <option value="collection.name">📁 原系列合集名</option>
                  </select>
                  <input 
                    v-model="lvl.fallback" 
                    placeholder="缺失备选 (如: 未分类)"
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
            <span class="text-xs font-semibold uppercase tracking-wider" style="color: var(--text-muted);">
              🌲 实时收纳蓝图图例 (Live Blueprint Tree)
            </span>
            <button 
              @click="runEvaluation" 
              :disabled="evaluating"
              class="px-4 py-1.5 rounded-lg text-xs font-bold text-white shadow-md transition-all flex items-center gap-1.5"
              style="background: var(--accent-color);"
            >
              <svg v-if="evaluating" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
              <span>{{ evaluating ? '体检演算中...' : '🔍 执行整理体检预演 (Evaluate)' }}</span>
            </button>
          </div>
          <div class="font-mono text-xs p-3 rounded-lg border overflow-x-auto space-y-1" style="background: rgba(0, 0, 0, 0.3); border-color: var(--border-color); color: var(--text-main);">
            <div>📁 目标根目录/</div>
            <div class="pl-4">├── 📁 {{ previewSampleSegment(0) }}/</div>
            <div class="pl-8">└── 📁 {{ previewSampleSegment(1) }}/</div>
            <div class="pl-12">└── 📁 {{ previewSampleSegment(2) }} ({{ previewSampleLeaf() }})</div>
          </div>
        </div>

        <!-- 4. 三色风险体检看板 (Dry-run Inspector) -->
        <div v-if="evaluationResult" class="space-y-4 animate-fade-in">
          <!-- 统计指标卡 -->
          <div class="grid grid-cols-3 gap-3">
            <div class="p-3 rounded-xl border flex items-center justify-between" style="background: rgba(34, 197, 94, 0.08); border-color: rgba(34, 197, 94, 0.3);">
              <div>
                <span class="text-xs text-green-400 font-bold block">🟢 完全安全 (Safe)</span>
                <span class="text-lg font-extrabold text-green-300">{{ evaluationResult.stats?.safe_count || 0 }} 项</span>
              </div>
              <span class="text-xs text-green-500 font-mono">毫秒级原子迁移</span>
            </div>

            <div class="p-3 rounded-xl border flex items-center justify-between" style="background: rgba(234, 179, 8, 0.08); border-color: rgba(234, 179, 8, 0.3);">
              <div>
                <span class="text-xs text-yellow-400 font-bold block">🟡 风险提示 (Warning)</span>
                <span class="text-lg font-extrabold text-yellow-300">{{ evaluationResult.stats?.warning_count || 0 }} 项</span>
              </div>
              <span class="text-xs text-yellow-500 font-mono">长路径/跨盘预警</span>
            </div>

            <div class="p-3 rounded-xl border flex items-center justify-between" style="background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.3);">
              <div>
                <span class="text-xs text-red-400 font-bold block">🔴 冲突阻断 (Conflict)</span>
                <span class="text-lg font-extrabold text-red-300">{{ evaluationResult.stats?.conflict_count || 0 }} 项</span>
              </div>
              <span class="text-xs text-red-500 font-mono">禁止覆盖</span>
            </div>
          </div>

          <!-- 详细对比表格 -->
          <div class="rounded-xl border overflow-hidden" style="border-color: var(--border-color);">
            <div class="max-h-60 overflow-y-auto">
              <table class="w-full text-left text-xs">
                <thead class="sticky top-0 border-b font-semibold" style="background: var(--bg-surface); border-color: var(--border-color); color: var(--text-muted);">
                  <tr>
                    <th class="p-2.5 w-12 text-center">状态</th>
                    <th class="p-2.5">文件</th>
                    <th class="p-2.5">整理前物理位置 (Before)</th>
                    <th class="p-2.5">➔ 整理后目标位置 (After)</th>
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
                      <span v-else-if="act.risk_level === 'warning'" class="text-yellow-400 font-bold" :title="act.risk_messages?.join(';')">🟡</span>
                      <span v-else class="text-red-400 font-bold" :title="act.risk_messages?.join(';')">🔴</span>
                    </td>
                    <td class="p-2 font-medium max-w-[140px] truncate" style="color: var(--text-main);" :title="act.file_name">
                      {{ act.file_name }}
                    </td>
                    <td class="p-2 font-mono text-[11px] max-w-[200px] truncate" style="color: var(--text-muted);" :title="act.src_path">
                      {{ act.src_path }}
                    </td>
                    <td class="p-2 font-mono text-[11px] max-w-[260px] truncate font-semibold" style="color: var(--accent-color);" :title="act.dst_path">
                      {{ act.dst_path }}
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
          <span>🛡️ 采用两阶段意图日志预写与原子短事务自愈，杜绝锁库与数据丢失。</span>
        </div>

        <div class="flex items-center gap-3">
          <button 
            @click="close"
            class="px-4 py-2 rounded-xl text-xs font-medium border hover:bg-white/10 transition-colors"
            style="border-color: var(--border-color); color: var(--text-main);"
          >
            取消
          </button>

          <button 
            @click="confirmExecution"
            :disabled="executing || !evaluationResult || evaluationResult.stats?.conflict_count > 0 || evaluationResult.total_actions === 0"
            class="px-5 py-2 rounded-xl text-xs font-bold text-white shadow-lg transition-all flex items-center gap-2"
            :style="!evaluationResult || evaluationResult.stats?.conflict_count > 0 || evaluationResult.total_actions === 0
              ? 'background: #6b7280; opacity: 0.5; cursor: not-allowed;' 
              : 'background: linear-gradient(135deg, var(--accent-color), #10b981);'"
          >
            <svg v-if="executing" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span>{{ executing ? '物理迁移与自愈中...' : `🚀 确认安全执行整理 (${evaluationResult?.total_actions || 0})` }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { fetchPipelinePresets, evaluatePipeline, executeTriagePlan, fetchCollections } from '../api'

const props = defineProps({
  isOpen: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'executed'])

const presets = ref([])
const activePresetId = ref('asmr_standard')
const collections = ref([])
const selectedCollectionId = ref(null)

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
    const [pList, cList] = await Promise.all([
      fetchPipelinePresets(),
      fetchCollections()
    ])
    presets.value = pList || []
    collections.value = cList || []
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
  pipelineLevels.value.splice(insertIdx, 0, {
    level_index: insertIdx,
    facet: 'tag.domain',
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
  if (lvl.folder_name) return lvl.folder_name
  if (lvl.facet === 'tag.domain') return '助眠'
  if (lvl.facet === 'tag.creator') return '秋姐社'
  if (lvl.facet === 'tag.media_kind') return '音声'
  return '分类目录'
}

function previewSampleLeaf() {
  const last = pipelineLevels.value[pipelineLevels.value.length - 1]
  if (last?.naming) return '[RJ390418] 甜蜜耳语'
  return '作品名'
}

async function runEvaluation() {
  evaluating.value = true
  try {
    const payload = {
      pipeline: {
        name: '自定义整理流水线',
        target_root: '/mnt/z/mcoc/音声',
        levels: pipelineLevels.value
      },
      collection_id: selectedCollectionId.value
    }
    const res = await evaluatePipeline(payload)
    evaluationResult.value = res
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
