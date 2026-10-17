<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  Terminal,
  Copy,
  Check,
  X,
  Bot,
} from 'lucide-vue-next'
import { fetchMCPConfig } from '../api'
import { usePlayerStore } from '../stores/playerStore'
import { t, tData } from '../i18n'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

const playerStore = usePlayerStore()

const mcpData = ref(null)
const loading = ref(false)
const copiedKey = ref('')

const agentPlaybooks = computed(() => [
  {
    id: 'taxonomy',
    label: t('mcp.pbTaxonomyLabel'),
    prompt: t('mcp.pbTaxonomyPrompt'),
  },
  {
    id: 'series',
    label: t('mcp.pbSeriesLabel'),
    prompt: t('mcp.pbSeriesPrompt'),
  },
  {
    id: 'untagged',
    label: t('mcp.pbUntaggedLabel'),
    prompt: t('mcp.pbUntaggedPrompt'),
  },
])

const handleKeyDown = (e) => {
  if (e.key === 'Escape' && props.isOpen) {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  loadConfig()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

const loadConfig = async () => {
  loading.value = true
  try {
    mcpData.value = await fetchMCPConfig()
  } catch (err) {
    console.error('Failed to load MCP config:', err)
  } finally {
    loading.value = false
  }
}

const configSnippet = computed(() => {
  if (!mcpData.value?.config_json) return ''
  return JSON.stringify(mcpData.value.config_json, null, 2)
})

const copyText = async (text, key, toastMsg) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedKey.value = key
    playerStore.showToast(toastMsg)
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1800)
  } catch (e) {
    playerStore.showToast(t('mcp.toastCopyFailed'))
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md select-none"
      @click.self="emit('close')"
    >
      <div
        class="relative w-full max-w-2xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
        style="background-color: var(--bg-surface-elevated);"
      >
        <!-- Minimalist Single-Line Header -->
        <div class="px-5 py-3.5 border-b border-white/5 flex items-center justify-between shrink-0">
          <div
            class="flex items-center gap-2.5"
            :title="t('mcp.headerTip')"
          >
            <div
              class="w-7 h-7 rounded-lg flex items-center justify-center text-white shrink-0"
              style="background-color: var(--accent-color);"
            >
              <Bot class="w-4 h-4 text-white" />
            </div>
            <span class="text-sm font-semibold text-white">{{ t('mcp.title') }}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
              stdio
            </span>
          </div>

          <button
            @click="emit('close')"
            class="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
            :title="t('mcp.closeTip')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-5 overflow-y-auto space-y-5 text-xs text-gray-300">
          <!-- 1. MCP Server JSON Config -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span
                class="text-[11px] font-medium text-gray-400"
                :title="t('mcp.configTip')"
              >
                {{ t('mcp.configLabel') }}
              </span>
              <button
                @click="copyText(configSnippet, 'config', t('mcp.toastCopiedConfig'))"
                class="w-7 h-7 rounded-lg flex items-center justify-center bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white border border-white/10 transition-colors cursor-pointer"
                :title="t('mcp.copyConfigTip')"
              >
                <Check v-if="copiedKey === 'config'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>
            </div>

            <pre
              class="p-3.5 rounded-xl bg-black/50 border border-white/10 font-mono text-[11px] text-emerald-300 overflow-x-auto select-all leading-relaxed"
            >{{ configSnippet || t('common.loading') }}</pre>
          </div>

          <!-- 2. Ready-to-Use External Agent Prompts -->
          <div class="space-y-2">
            <span
              class="text-[11px] font-medium text-gray-400 block"
              :title="t('mcp.playbooksTip')"
            >
              {{ t('mcp.playbooksLabel') }}
            </span>

            <div class="space-y-1.5">
              <div
                v-for="item in agentPlaybooks"
                :key="item.id"
                :title="item.prompt"
                class="flex items-center justify-between gap-3 px-3 py-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] border border-white/5 transition-colors"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <Terminal class="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  <span class="text-xs text-gray-200 truncate">{{ item.label }}</span>
                </div>
                <button
                  @click="copyText(item.prompt, item.id, t('mcp.toastCopiedPlaybook'))"
                  class="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer shrink-0"
                  :title="t('mcp.copyPlaybookTip')"
                >
                  <Check v-if="copiedKey === item.id" class="w-3.5 h-3.5 text-emerald-400" />
                  <Copy v-else class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          <!-- 3. Exposed MCP Tools (Hover for descriptions) -->
          <div v-if="mcpData?.tools" class="space-y-2">
            <div class="flex items-center justify-between">
              <span
                class="text-[11px] font-medium text-gray-400"
                :title="t('mcp.toolsTip')"
              >
                {{ t('mcp.toolsLabel') }}
              </span>
              <span class="text-[11px] font-mono text-gray-500">{{ mcpData.tools.length }}</span>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              <div
                v-for="toolItem in mcpData.tools"
                :key="toolItem.name"
                :title="tData(toolItem.desc)"
                class="px-2.5 py-1.5 rounded-lg bg-white/[0.02] hover:bg-white/[0.06] border border-white/5 font-mono text-[11px] text-purple-300 truncate cursor-default transition-colors"
              >
                {{ toolItem.name }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
