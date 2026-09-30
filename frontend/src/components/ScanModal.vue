<script setup>
import { ref } from 'vue'
import { useMediaStore } from '../stores/mediaStore'
import { X, FolderSearch, CheckCircle2, AlertCircle, Sparkles } from 'lucide-vue-next'

const mediaStore = useMediaStore()
const scanPath = ref('')
const scanning = ref(false)
const scanResult = ref(null)
const errorMsg = ref('')

const handleStartScan = async (pathToScan = null) => {
  const target = pathToScan || scanPath.value.trim()
  if (!target) return
  scanning.value = true
  errorMsg.value = ''
  scanResult.value = null
  try {
    const res = await mediaStore.scanFolder(target)
    scanResult.value = res
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || err.message
  } finally {
    scanning.value = false
  }
}

const handleClose = () => {
  mediaStore.scanModalOpen = false
  scanResult.value = null
  errorMsg.value = ''
}
</script>

<template>
  <div
    v-if="mediaStore.scanModalOpen"
    class="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-md animate-fade-in"
  >
    <div class="bg-[#171923] border border-white/10 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
      <button
        @click="handleClose"
        class="absolute top-4 right-4 text-gray-400 hover:text-white p-1 rounded-lg"
      >
        <X class="w-5 h-5" />
      </button>

      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center">
          <FolderSearch class="w-5 h-5" />
        </div>
        <div>
          <h3 class="text-base font-semibold text-white">纳管物理媒体目录</h3>
          <p class="text-xs text-gray-400">非破坏性递归索引，不会移动或更改你的物理文件</p>
        </div>
      </div>

      <!-- Path Input Form -->
      <div class="space-y-4">
        <div>
          <label class="block text-xs font-medium text-gray-300 mb-1.5">
            输入本地绝对路径 (Windows 路径如 D:\Photos 或 Linux 路径)
          </label>
          <div class="flex items-center gap-2">
            <input
              v-model="scanPath"
              type="text"
              placeholder="/home/mcocdaa/AI_CODE 或 D:\Media"
              class="flex-grow bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
              @keyup.enter="() => handleStartScan()"
            />
            <button
              @click="() => handleStartScan()"
              :disabled="scanning || !scanPath.trim()"
              class="bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-xs font-medium px-4 py-2 rounded-xl transition-all shadow-md shrink-0"
            >
              <span v-if="scanning">扫描中...</span>
              <span v-else>开始纳管</span>
            </button>
          </div>
        </div>

        <!-- Quick Demo Presets -->
        <div class="bg-white/5 rounded-xl p-3 border border-white/5">
          <div class="text-[11px] font-medium text-gray-400 mb-2 flex items-center gap-1.5">
            <Sparkles class="w-3.5 h-3.5 text-purple-400" />
            <span>快速纳管测试库 (Sample Library)</span>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              @click="handleStartScan('/home/mcocdaa/AI_CODE/MuseFlow/sample_media')"
              class="text-xs bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-200 px-3 py-1.5 rounded-lg transition-colors"
            >
              📁 MuseFlow 内置测试样本集
            </button>
          </div>
        </div>

        <!-- Success Result -->
        <div
          v-if="scanResult"
          class="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3 flex items-start gap-2.5 text-emerald-300 text-xs"
        >
          <CheckCircle2 class="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
          <div>
            <div class="font-semibold">纳管成功！</div>
            <div class="text-[11px] text-emerald-200/80 mt-0.5">
              已扫描物理文件 {{ scanResult.total_files }} 个，智能构建原子消费单元 {{ scanResult.total_units }} 个。
            </div>
          </div>
        </div>

        <!-- Error Msg -->
        <div
          v-if="errorMsg"
          class="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 flex items-start gap-2.5 text-rose-300 text-xs"
        >
          <AlertCircle class="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
          <div>{{ errorMsg }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
