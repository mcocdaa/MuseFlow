<script setup>
import { ref, onMounted } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { X, BrainCircuit, Sparkles, RefreshCw, Layers, ArrowRight } from 'lucide-vue-next'
import { fetchMemoryRecapContext } from '../api'

const mediaStore = useMediaStore()
const loading = ref(false)
const contextData = ref(null)

const loadContext = async () => {
  loading.value = true
  try {
    contextData.value = await fetchMemoryRecapContext()
  } catch (err) {
    console.error('Failed to load AI context', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadContext()
})
</script>

<template>
  <div
    v-if="mediaStore.recapModalOpen"
    class="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-md animate-fade-in"
  >
    <div class="bg-[#171923] border border-white/10 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative">
      <button
        @click="mediaStore.recapModalOpen = false"
        class="absolute top-4 right-4 text-gray-400 hover:text-white p-1 rounded-lg"
      >
        <X class="w-5 h-5" />
      </button>

      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-pink-500/20 to-purple-500/20 text-pink-400 flex items-center justify-center border border-pink-500/30">
          <BrainCircuit class="w-5 h-5" />
        </div>
        <div>
          <h3 class="text-base font-semibold text-white">AI 记忆唤醒与待整理中枢</h3>
          <p class="text-xs text-gray-400">开放 API 供外部大模型与智能 Agent 自主感知并优化媒体库</p>
        </div>
      </div>

      <div v-if="loading" class="py-12 flex justify-center text-purple-400">
        <RefreshCw class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="contextData" class="space-y-4 text-xs">
        <!-- Summary Box -->
        <div class="bg-purple-900/20 border border-purple-500/30 rounded-xl p-3.5">
          <div class="flex items-center justify-between mb-1.5 font-medium text-purple-300">
            <span class="flex items-center gap-1.5">
              <Sparkles class="w-4 h-4 text-pink-400" />
              <span>智能记忆雷达</span>
            </span>
            <span class="bg-purple-500/30 px-2 py-0.5 rounded-full font-mono text-[11px]">
              {{ contextData.stale_memory_count }} 份尘封记忆待回顾
            </span>
          </div>
          <p class="text-gray-300 leading-relaxed text-[11px]">
            检测到库内部分从未被浏览、评分的内容。推荐算法插件可以通过接口自动将这些内容安排进“时光倒流”流中。
          </p>
        </div>

        <!-- Sample Stale Memories List -->
        <div>
          <div class="text-gray-400 font-semibold mb-2">待重温/待归类采样：</div>
          <div class="space-y-1.5 max-h-40 overflow-y-auto">
            <div
              v-for="unit in contextData.sample_stale_units"
              :key="unit.id"
              class="flex items-center justify-between bg-white/5 border border-white/5 rounded-lg px-3 py-2 text-gray-200"
            >
              <span class="truncate font-medium">{{ unit.title }}</span>
              <span class="text-[10px] text-gray-500 uppercase px-1.5 py-0.5 rounded bg-white/5">
                {{ unit.type }}
              </span>
            </div>
          </div>
        </div>

        <!-- External Agent Hook Prompt -->
        <div class="bg-black/40 border border-white/5 rounded-xl p-3">
          <div class="text-[11px] font-semibold text-gray-300 mb-1">面向开发与 AI Agent 的开放接口：</div>
          <code class="text-[10px] text-purple-300 block font-mono bg-white/5 p-2 rounded">
            GET /api/ai/memory_recap_context<br/>
            GET /api/ai/unorganized<br/>
            POST /api/supersets/{id}/items
          </code>
        </div>
      </div>
    </div>
  </div>
</template>
