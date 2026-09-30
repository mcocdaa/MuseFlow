<script setup>
import { ref, watch, onMounted } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import {
  X,
  Bot,
  Sparkles,
  Layers,
  FolderTree,
  FolderOpen,
  CheckCircle2,
  AlertCircle,
  FileVideo,
  FileText,
  FileAudio,
  ArrowRight,
  RefreshCw,
  Cpu
} from 'lucide-vue-next'
import { analyzeFolderWithAI, applyAITriagePlan, fetchAISettings } from '../api'

const mediaStore = useMediaStore()

const folderPath = ref('')
const customInstruction = ref('')
const analyzing = ref(false)
const applying = ref(false)
const plan = ref(null)
const errorMsg = ref('')
const successMsg = ref('')
const aiSettings = ref(null)

onMounted(async () => {
  try {
    aiSettings.value = await fetchAISettings()
  } catch (e) {
    console.error('Failed to load AI settings', e)
  }
})

watch(() => mediaStore.aiOrganizerModalOpen, (isOpen) => {
  if (isOpen) {
    folderPath.value = mediaStore.aiOrganizerTargetFolder || ''
    plan.value = null
    errorMsg.value = ''
    successMsg.value = ''
  }
})

const handleStartAnalysis = async () => {
  if (!folderPath.value.trim()) return
  analyzing.value = true
  errorMsg.value = ''
  successMsg.value = ''
  plan.value = null

  try {
    const res = await analyzeFolderWithAI(folderPath.value.trim(), customInstruction.value.trim())
    plan.value = res
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message
  } finally {
    analyzing.value = false
  }
}

const handleApplyPlan = async () => {
  if (!plan.value) return
  applying.value = true
  errorMsg.value = ''
  try {
    const res = await applyAITriagePlan(folderPath.value.trim(), plan.value)
    successMsg.value = `应用成功！已更新 ${res.collections_created} 个系列，${res.units_created} 个原子消费单元。`
    await Promise.all([
      mediaStore.loadCollections(),
      mediaStore.loadFeed(),
      mediaStore.loadWorkplaceItems(),
    ])
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message
  } finally {
    applying.value = false
  }
}

const handleClose = () => {
  mediaStore.aiOrganizerModalOpen = false
  plan.value = null
  errorMsg.value = ''
  successMsg.value = ''
}
</script>

<template>
  <div
    v-if="mediaStore.aiOrganizerModalOpen"
    class="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4 backdrop-blur-md animate-fade-in"
  >
    <div class="bg-[#171923] border border-purple-500/30 rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl relative overflow-hidden">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-pink-600 to-indigo-600 text-white flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Bot class="w-5 h-5" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-white">AI 智能目录拓扑重组中枢</h3>
              <span class="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full flex items-center gap-1 font-mono">
                <Cpu class="w-3 h-3 text-purple-400" />
                <span>{{ aiSettings?.model || 'grok-4.7' }}</span>
              </span>
            </div>
            <p class="text-xs text-gray-400 mt-0.5">
              识别跨层级嵌套子系列、智能解决散落音画字幕/伴侣文件配对，生成零破坏重组方案
            </p>
          </div>
        </div>

        <button
          @click="handleClose"
          class="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Modal Body (Scrollable) -->
      <div class="flex-grow overflow-y-auto p-6 space-y-5">
        <!-- Configuration / Input Section -->
        <div class="bg-white/5 border border-white/5 rounded-2xl p-4 space-y-3">
          <div>
            <label class="block text-xs font-semibold text-gray-300 mb-1.5 flex items-center justify-between">
              <span>待深度分析的文件夹绝对路径：</span>
              <button
                @click="folderPath = '/home/mcocdaa/AI_CODE/MuseFlow/backend/sample_media/Project_Complex_A'"
                class="text-[11px] text-purple-400 hover:underline"
              >
                载入测试用复杂嵌套文件夹 (A/B & 跨层级Vlog)
              </button>
            </label>
            <input
              v-model="folderPath"
              type="text"
              placeholder="例如: /home/mcocdaa/AI_CODE/MuseFlow/backend/sample_media/Project_Complex_A"
              class="w-full bg-black/40 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 font-mono"
            />
          </div>

          <div>
            <label class="block text-xs font-semibold text-gray-300 mb-1.5">
              补充指令 (可选，例如：“把嵌套的子工程 B 单独提取为独立系列”):
            </label>
            <input
              v-model="customInstruction"
              type="text"
              placeholder="给大模型的个性化指导（可留空，AI 会自动按最佳模式拆解）"
              class="w-full bg-black/40 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
            />
          </div>

          <div class="flex items-center justify-between pt-1">
            <div class="text-[11px] text-gray-400 flex items-center gap-1.5">
              <Sparkles class="w-3.5 h-3.5 text-pink-400" />
              <span>由 grok-4.7 深度推理目录拓扑与语义关系</span>
            </div>

            <button
              @click="handleStartAnalysis"
              :disabled="analyzing || !folderPath.trim()"
              class="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-40 text-white text-xs font-semibold px-5 py-2 rounded-xl transition-all shadow-lg shadow-purple-600/30 flex items-center gap-2 shrink-0"
            >
              <RefreshCw v-if="analyzing" class="w-4 h-4 animate-spin" />
              <Bot v-else class="w-4 h-4" />
              <span>{{ analyzing ? 'AI 正在深度思考目录树拓扑...' : '召唤 AI 分析拓扑' }}</span>
            </button>
          </div>
        </div>

        <!-- Error Alert -->
        <div
          v-if="errorMsg"
          class="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 flex items-start gap-2.5 text-rose-300 text-xs"
        >
          <AlertCircle class="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
          <div class="break-words">{{ errorMsg }}</div>
        </div>

        <!-- Success Alert -->
        <div
          v-if="successMsg"
          class="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3 flex items-start gap-2.5 text-emerald-300 text-xs"
        >
          <CheckCircle2 class="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
          <div class="font-semibold">{{ successMsg }}</div>
        </div>

        <!-- AI Plan Result View -->
        <div v-if="plan" class="space-y-4 animate-fade-in">
          <!-- Summary Rationale Card -->
          <div class="bg-purple-950/30 border border-purple-500/40 rounded-2xl p-4 space-y-1.5">
            <div class="flex items-center gap-2 text-xs font-bold text-purple-300 uppercase tracking-wider">
              <Sparkles class="w-4 h-4 text-pink-400" />
              <span>AI 拓扑分析洞察与重组理由</span>
            </div>
            <p class="text-xs text-gray-200 leading-relaxed">
              {{ plan.summary }}
            </p>
          </div>

          <!-- Suggested Collections & Bundles -->
          <div class="space-y-3">
            <div class="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center justify-between">
              <span>规划系列与复合消费包 (共 {{ plan.collections?.length || 0 }} 个系列)：</span>
              <span class="text-[11px] text-gray-500 font-normal">物理文件位置保持原位</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                v-for="(col, cIdx) in plan.collections"
                :key="cIdx"
                class="bg-white/5 border border-white/10 rounded-2xl p-4 flex flex-col justify-between gap-3 hover:border-purple-500/30 transition-colors"
              >
                <div>
                  <!-- Collection Name & Path -->
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-bold text-white flex items-center gap-1.5">
                      <FolderOpen class="w-4 h-4 text-blue-400" />
                      <span>{{ col.name }}</span>
                    </span>
                    <span
                      v-if="col.folder_rel_path !== '.'"
                      class="text-[10px] bg-pink-500/20 text-pink-300 border border-pink-500/30 px-2 py-0.5 rounded-full font-medium"
                    >
                      独立剥离子系列
                    </span>
                  </div>
                  <div class="text-[11px] text-gray-400 mb-2 font-mono truncate">
                    路径：{{ col.folder_rel_path }}
                  </div>
                  <p v-if="col.description" class="text-xs text-gray-300 mb-3 bg-black/20 p-2 rounded-lg">
                    {{ col.description }}
                  </p>

                  <!-- Units inside this collection -->
                  <div class="space-y-2">
                    <div
                      v-for="(u, uIdx) in col.units"
                      :key="uIdx"
                      class="bg-white/5 border border-white/5 rounded-xl p-2.5 text-xs flex flex-col gap-1.5"
                    >
                      <div class="flex items-center justify-between font-semibold text-gray-200">
                        <span class="truncate flex items-center gap-1.5">
                          <Layers v-if="u.unit_type === 'bundle'" class="w-3.5 h-3.5 text-purple-400 shrink-0" />
                          <FileVideo v-else-if="u.unit_type === 'video'" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
                          <span class="truncate">{{ u.title }}</span>
                        </span>
                        <span
                          :class="[
                            'text-[10px] px-1.5 py-0.2 rounded uppercase font-semibold shrink-0',
                            u.unit_type === 'bundle'
                              ? 'bg-purple-500/30 text-purple-300 border border-purple-500/30'
                              : 'bg-white/10 text-gray-400'
                          ]"
                        >
                          {{ u.unit_type }}
                        </span>
                      </div>

                      <!-- Primary File -->
                      <div class="text-[11px] text-gray-400 font-mono truncate">
                        主文件: {{ u.primary_file }}
                      </div>

                      <!-- Auxiliary files if bundle -->
                      <div v-if="u.auxiliary_files?.length > 0" class="pl-2 border-l border-purple-500/30 space-y-1 my-0.5">
                        <div
                          v-for="(aux, aIdx) in u.auxiliary_files"
                          :key="aIdx"
                          class="text-[10px] text-purple-300 flex items-center gap-1 font-mono truncate"
                        >
                          <span class="bg-purple-500/20 px-1 rounded text-[9px] uppercase font-sans">
                            {{ aux.role }}
                          </span>
                          <span class="truncate">{{ aux.path }}</span>
                        </div>
                      </div>

                      <!-- Reason -->
                      <div v-if="u.reason" class="text-[10px] text-gray-500 italic mt-0.5">
                        {{ u.reason }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Recommended Supersets -->
          <div v-if="plan.recommended_supersets?.length > 0" class="bg-white/5 border border-white/5 rounded-2xl p-4">
            <div class="text-xs font-bold text-pink-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Sparkles class="w-3.5 h-3.5 text-pink-400" />
              <span>推荐构建的虚拟超集 (Supersets)：</span>
            </div>
            <div class="flex flex-wrap gap-2">
              <div
                v-for="(sup, sIdx) in plan.recommended_supersets"
                :key="sIdx"
                class="bg-pink-500/10 border border-pink-500/30 rounded-xl p-2 text-xs flex flex-col gap-0.5 max-w-sm"
              >
                <div class="font-bold text-pink-200">{{ sup.name }}</div>
                <div class="text-[10px] text-gray-400">{{ sup.reason }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div v-if="plan" class="px-6 py-4 border-t border-white/10 flex items-center justify-between bg-white/[0.02]">
        <div class="text-xs text-gray-400">
          已规划 {{ plan.collections?.length || 0 }} 个系列，共归整 {{ plan.total_scanned_files }} 个物理文件
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="handleClose"
            class="px-4 py-2 rounded-xl text-xs text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            取消
          </button>
          <button
            @click="handleApplyPlan"
            :disabled="applying"
            class="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-5 py-2 rounded-xl transition-all shadow-lg shadow-purple-600/30 flex items-center gap-1.5"
          >
            <CheckCircle2 v-if="!applying" class="w-4 h-4" />
            <RefreshCw v-else class="w-4 h-4 animate-spin" />
            <span>{{ applying ? '正在写入数据库...' : '✨ 一键确认应用此方案' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
