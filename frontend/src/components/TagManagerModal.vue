<template>
  <div v-if="isOpen" @click.self="close" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
    <div 
      class="w-full max-w-4xl max-h-[88vh] flex flex-col rounded-2xl shadow-2xl border overflow-hidden relative"
      style="background: var(--bg-surface-elevated); border-color: var(--border-color);"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b shrink-0" style="border-color: var(--border-color);">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-xl text-white shadow-md" style="background: linear-gradient(135deg, #a855f7, #6366f1);">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
          </div>
          <div>
            <h3 class="text-base font-bold" style="color: var(--text-main);">{{ t('tagMgr.title') }}</h3>
            <p class="text-xs" style="color: var(--text-muted);">
              {{ t('tagMgr.subtitle') }}
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

      <!-- Main Split: Class Sidebar & Tag Hierarchy Tree -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Left: Tag Classes Sidebar -->
        <div class="w-60 border-r p-4 shrink-0 flex flex-col gap-2 overflow-y-auto" style="border-color: var(--border-color); background: var(--bg-surface);">
          <div class="flex items-center justify-between mb-1 gap-2">
            <div class="text-[11px] font-semibold uppercase tracking-wider whitespace-nowrap" style="color: var(--text-muted);">
              {{ t('workplace.dimensions', { count: tagClasses.length }) }}
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button 
                @click="openPresetsModal"
                class="px-2 py-0.5 rounded-lg text-[10px] font-semibold text-purple-400 hover:text-white bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 transition-all flex items-center gap-0.5 cursor-pointer whitespace-nowrap"
                :title="t('tagMgr.presetsTip')"
              >
                <span>{{ t('tagMgr.presets') }}</span>
              </button>
              <button 
                @click="showCreateClassModal = true"
                class="px-2 py-0.5 rounded-lg text-[10px] font-semibold text-blue-400 hover:text-white bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 transition-all flex items-center gap-0.5 cursor-pointer whitespace-nowrap"
                :title="t('tagMgr.newFacetTip')"
              >
                <span>{{ t('tagMgr.newFacet') }}</span>
              </button>
            </div>
          </div>

          <button
            v-for="tc in tagClasses"
            :key="tc.id"
            @click="selectedClassId = tc.id"
            class="flex items-center justify-between p-2.5 rounded-xl text-xs font-medium transition-all text-left border cursor-pointer"
            :style="selectedClassId === tc.id
              ? 'background: rgba(168, 85, 247, 0.15); color: #fff; border-color: rgba(168, 85, 247, 0.4);'
              : 'background: transparent; color: var(--text-muted); border-color: transparent;'"
          >
            <div class="flex items-center gap-2 truncate">
              <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: tc.color || '#a855f7' }"></span>
              <span class="truncate">{{ tFacet(tc.code, tc.display_name) }}</span>
              <span v-if="tc.code === 'media_kind'" class="text-[9px] text-blue-400 font-mono px-1 py-0.2 bg-blue-500/10 rounded" :title="t('tagMgr.physicalTip')">{{ t('tagMgr.physicalBadge') }}</span>
              <span v-else-if="tc.is_required" class="text-[9px] text-amber-400 font-bold" :title="t('tagMgr.requiredTip')">⭐</span>
            </div>
            <span class="text-[10px] font-mono opacity-60 bg-white/5 px-1.5 py-0.2 rounded-full">
              {{ getClassTagCount(tc.id) }}
            </span>
          </button>
        </div>

        <!-- Right: Tag Hierarchy Tree & Create/Edit Area -->
        <div class="flex-1 flex flex-col p-5 overflow-y-auto space-y-4">
          <!-- Active Class Header & Add Tag Input Bar -->
          <div class="flex flex-col gap-3 p-3.5 rounded-xl border" style="background: var(--bg-surface); border-color: var(--border-color);">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex flex-wrap items-center gap-2">
                <span class="w-3 h-3 rounded-full shrink-0" :style="{ backgroundColor: currentClass?.color || '#a855f7' }"></span>
                <span class="text-sm font-bold text-white">{{ currentClass ? tFacet(currentClass.code, currentClass.display_name) : '' }}</span>
                <span class="text-xs font-mono text-gray-400">({{ currentClass?.code }})</span>

                <!-- Toggle Required Facet -->
                <button
                  v-if="currentClass && currentClass.code !== 'media_kind'"
                  @click="handleToggleRequired(currentClass)"
                  class="flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold transition-all border select-none cursor-pointer"
                  :class="currentClass.is_required 
                    ? 'bg-amber-500/25 border-amber-500/50 text-amber-200' 
                    : 'bg-white/5 border-white/10 text-gray-400 hover:text-gray-200 hover:bg-white/10'"
                  :title="t('tagMgr.toggleRequiredTip')"
                >
                  <span>{{ currentClass.is_required ? t('tagMgr.requiredFacet') : t('tagMgr.optionalFacet') }}</span>
                </button>

                <!-- Toggle Projectable -->
                <button
                  v-if="currentClass"
                  @click="handleToggleProjectable(currentClass)"
                  class="flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold transition-all border select-none cursor-pointer"
                  :class="currentClass.is_projectable 
                    ? 'bg-blue-500/20 border-blue-500/40 text-blue-200' 
                    : 'bg-white/5 border-white/10 text-gray-500 hover:text-gray-300'"
                  :title="t('tagMgr.toggleProjectableTip')"
                >
                  <span>{{ currentClass.is_projectable ? t('tagMgr.projectable') : t('tagMgr.virtualOnly') }}</span>
                </button>
              </div>

              <!-- Delete Class Button (Protected for system core) -->
              <button
                v-if="currentClass && currentClass.code !== 'media_kind' && currentClass.code !== 'workflow'"
                @click="handleDeleteClass(currentClass)"
                class="flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold transition-all border select-none cursor-pointer bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20 hover:text-red-300"
                :title="t('tagMgr.deleteFacetTip')"
              >
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                <span>{{ t('tagMgr.deleteFacet') }}</span>
              </button>
            </div>

            <!-- Quick Add Tag Row -->
            <div class="flex items-center gap-2 pt-1 border-t border-white/5">
              <input
                v-model="newTagName"
                type="text"
                :placeholder="t('tagMgr.newTagPlaceholder', { name: currentClass ? tFacet(currentClass.code, currentClass.display_name) : '' })"
                class="bg-white/5 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 flex-1 max-w-xs"
                @keyup.enter="handleCreateTag"
              />

              <select
                v-model="newTagParentId"
                class="bg-white/5 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-gray-300 outline-none max-w-[150px]"
                :title="t('tagMgr.selectParentTip')"
              >
                <option :value="null">{{ t('tagMgr.asRootTag') }}</option>
                <option v-for="tNode in currentClassTags" :key="tNode.id" :value="tNode.id">
                  {{ t('tagMgr.inheritPrefix') }} {{ tData(tNode.name) }}
                </option>
              </select>

              <button
                @click="handleCreateTag"
                :disabled="!newTagName.trim()"
                class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white disabled:opacity-40 transition-colors cursor-pointer shrink-0"
              >
                {{ t('tagMgr.createTagBtn') }}
              </button>
            </div>
          </div>

          <!-- Tree View Area -->
          <div class="flex-1 rounded-xl border p-4 overflow-y-auto" style="background: var(--bg-surface); border-color: var(--border-color);">
            <div v-if="loading" class="text-center py-12 text-xs" style="color: var(--text-muted);">
              {{ t('tagMgr.loadingTree') }}
            </div>

            <div v-else-if="currentClassTree.length === 0" class="text-center py-12 text-xs" style="color: var(--text-muted);">
              {{ t('tagMgr.emptyTree') }}
            </div>

            <!-- Recursive Tree List -->
            <div v-else class="space-y-1.5">
              <TagTreeNode
                v-for="node in currentClassTree"
                :key="node.id"
                :node="node"
                :level="0"
                :allClassTags="currentClassTags"
                @reparent="handleReparent"
                @delete="handleDelete"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Help Note -->
      <div class="px-6 py-3 border-t shrink-0 flex items-center justify-between text-xs" style="border-color: var(--border-color); color: var(--text-muted);">
        <div class="flex items-center gap-1.5">
          <span class="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
          <span>{{ t('tagMgr.footerNote') }}</span>
        </div>
        <button
          @click="close"
          class="px-4 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-white transition-colors cursor-pointer"
        >
          {{ t('tagMgr.doneAndClose') }}
        </button>
      </div>

      <!-- Sub-Modal 1: Create Custom TagClass -->
      <div 
        v-if="showCreateClassModal"
        class="absolute inset-0 z-20 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-fade-in"
      >
        <div 
          class="w-full max-w-md p-6 rounded-2xl border shadow-2xl space-y-4"
          style="background: var(--bg-surface-elevated); border-color: var(--border-color);"
        >
          <div class="flex items-center justify-between border-b pb-3" style="border-color: var(--border-color);">
            <div class="flex items-center gap-2">
              <span class="text-base font-bold text-white">{{ t('tagMgr.createFacetTitle') }}</span>
            </div>
            <button @click="showCreateClassModal = false" class="text-gray-400 hover:text-white">
              ✕
            </button>
          </div>

          <div class="space-y-3 text-xs">
            <div>
              <label class="block font-medium text-gray-300 mb-1">{{ t('tagMgr.displayNameLabel') }}</label>
              <input 
                v-model="newClassForm.display_name" 
                type="text" 
                :placeholder="t('tagMgr.displayNamePlaceholder')"
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label class="block font-medium text-gray-300 mb-1">{{ t('tagMgr.codeLabel') }}</label>
              <input 
                v-model="newClassForm.code" 
                type="text" 
                :placeholder="t('tagMgr.codePlaceholder')"
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white font-mono placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
              <span class="text-[10px] text-gray-500">{{ t('tagMgr.codeHint') }}</span>
            </div>

            <div>
              <label class="block font-medium text-gray-300 mb-1">{{ t('tagMgr.colorLabel') }}</label>
              <div class="flex items-center gap-2">
                <button
                  v-for="c in presetColors"
                  :key="c"
                  type="button"
                  @click="newClassForm.color = c"
                  class="w-6 h-6 rounded-full border-2 transition-all cursor-pointer"
                  :style="{ backgroundColor: c, borderColor: newClassForm.color === c ? '#fff' : 'transparent' }"
                ></button>
              </div>
            </div>

            <div class="space-y-2 pt-2 border-t border-white/5">
              <label class="flex items-center gap-2 text-gray-300 cursor-pointer">
                <input type="checkbox" v-model="newClassForm.is_projectable" class="rounded text-purple-600" />
                <span>{{ t('tagMgr.projectableCheckbox') }}</span>
              </label>

              <label class="flex items-center gap-2 text-gray-300 cursor-pointer">
                <input type="checkbox" v-model="newClassForm.is_required" class="rounded text-purple-600" />
                <span>{{ t('tagMgr.requiredCheckbox') }}</span>
              </label>
            </div>

            <div>
              <label class="block font-medium text-gray-300 mb-1">{{ t('tagMgr.descLabel') }}</label>
              <input 
                v-model="newClassForm.description" 
                type="text" 
                :placeholder="t('tagMgr.descPlaceholder')"
                class="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          <div class="flex items-center justify-end gap-2 pt-3 border-t" style="border-color: var(--border-color);">
            <button 
              @click="showCreateClassModal = false"
              class="px-4 py-2 rounded-xl text-xs text-gray-400 hover:text-white bg-white/5 transition-colors cursor-pointer"
            >
              {{ t('common.cancel') }}
            </button>
            <button 
              @click="handleCreateClass"
              :disabled="!newClassForm.display_name.trim() || !newClassForm.code.trim()"
              class="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-40 transition-colors cursor-pointer shadow-lg"
            >
              {{ t('tagMgr.createAndApply') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Sub-Modal 2: Taxonomy Presets Library -->
      <div 
        v-if="showPresetsModal"
        class="absolute inset-0 z-20 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-fade-in"
      >
        <div 
          class="w-full max-w-2xl max-h-full flex flex-col p-6 rounded-2xl border shadow-2xl space-y-4 overflow-hidden"
          style="background: var(--bg-surface-elevated); border-color: var(--border-color);"
        >
          <div class="flex items-center justify-between border-b pb-3 shrink-0" style="border-color: var(--border-color);">
            <div>
              <h4 class="text-base font-bold text-white flex items-center gap-2">
                <span>{{ t('tagMgr.presetsModalTitle') }}</span>
              </h4>
              <p class="text-xs text-gray-400">
                {{ t('tagMgr.presetsModalDesc') }}
              </p>
            </div>
            <button @click="showPresetsModal = false" class="text-gray-400 hover:text-white">
              ✕
            </button>
          </div>

          <div class="flex-1 overflow-y-auto space-y-3 pr-1">
            <div 
              v-for="p in presetsList" 
              :key="p.id"
              class="p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 transition-all hover:border-purple-500/40"
              style="background: var(--bg-surface); border-color: var(--border-color);"
            >
              <div class="space-y-1.5 flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-sm text-white">{{ tData(p.name) }}</span>
                  <span class="font-mono text-[10px] text-gray-500">({{ p.id }})</span>
                </div>
                <p class="text-xs text-gray-400">{{ tData(p.description) }}</p>

                <!-- TagClass chips inside preset -->
                <div class="flex flex-wrap items-center gap-1.5 pt-1">
                  <span 
                    v-for="c in p.classes" 
                    :key="c.code"
                    class="px-2 py-0.5 rounded-md text-[10px] font-medium border flex items-center gap-1"
                    :style="{ backgroundColor: `${c.color}15`, borderColor: `${c.color}40`, color: c.color }"
                  >
                    <span>{{ tFacet(c.code, c.display_name) }}</span>
                    <span class="opacity-60 font-mono text-[9px]">({{ c.code }})</span>
                  </span>
                </div>
              </div>

              <button
                @click="handleApplyPreset(p.id)"
                :disabled="applyingPreset"
                class="px-3.5 py-1.5 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 disabled:opacity-50 transition-all shrink-0 cursor-pointer shadow-md"
              >
                {{ isPresetFullyLoaded(p) ? t('tagMgr.presetLoaded') : t('tagMgr.presetLoadBtn') }}
              </button>
            </div>
          </div>

          <div class="flex items-center justify-end pt-3 border-t shrink-0" style="border-color: var(--border-color);">
            <button 
              @click="showPresetsModal = false"
              class="px-4 py-1.5 rounded-xl text-xs text-white bg-white/10 hover:bg-white/15 transition-colors cursor-pointer"
            >
              {{ t('common.close') }}
            </button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, defineComponent, h } from 'vue'
import {
  fetchTagClasses,
  createTagClass,
  updateTagClass,
  deleteTagClass,
  fetchTaxonomyPresets,
  applyTaxonomyPreset,
  fetchTagTree,
  fetchAllTagsFlat,
  createTag,
  updateTagParent,
  deleteTagApi
} from '../api'
import { useMediaStore } from '../stores/mediaStore'
import { t, tData, tFacet } from '../i18n'

const mediaStore = useMediaStore()

const props = defineProps({
  isOpen: Boolean,
})

const emit = defineEmits(['close', 'changed'])

const loading = ref(false)
const tagClasses = ref([])
const tagTreeData = ref([])
const allFlatTags = ref([])
const selectedClassId = ref(null)

const newTagName = ref('')
const newTagParentId = ref(null)

// Custom Class Modal
const showCreateClassModal = ref(false)
const presetColors = ['#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b', '#06b6d4', '#64748b']
const newClassForm = ref({
  code: '',
  display_name: '',
  icon: 'tag',
  color: '#3b82f6',
  is_projectable: true,
  is_required: false,
  description: '',
})

// Presets Modal
const showPresetsModal = ref(false)
const presetsList = ref([])
const applyingPreset = ref(false)

const loadData = async () => {
  loading.value = true
  try {
    const [classes, tree, flat] = await Promise.all([
      fetchTagClasses(),
      fetchTagTree(),
      fetchAllTagsFlat()
    ])
    tagClasses.value = classes || []
    tagTreeData.value = tree || []
    allFlatTags.value = flat || []
    if (!selectedClassId.value && classes.length > 0) {
      selectedClassId.value = classes[1]?.id || classes[0]?.id
    }
  } catch (err) {
    console.error('Failed to load tag taxonomy data:', err)
  } finally {
    loading.value = false
  }
}

watch(() => props.isOpen, (open) => {
  if (open) {
    loadData()
  }
})

const handleKeyDown = (e) => {
  if (e.key === 'Escape' && props.isOpen) {
    if (showCreateClassModal.value) {
      showCreateClassModal.value = false
    } else if (showPresetsModal.value) {
      showPresetsModal.value = false
    } else {
      close()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  if (props.isOpen) {
    loadData()
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

const close = () => {
  emit('close')
}

const currentClass = computed(() => {
  return tagClasses.value.find(c => c.id === selectedClassId.value)
})

const currentClassTags = computed(() => {
  return allFlatTags.value.filter(t => t.tag_class_id === selectedClassId.value)
})

const currentClassTree = computed(() => {
  const treeItem = tagTreeData.value.find(t => t.class_id === selectedClassId.value)
  return treeItem?.tree || []
})

const getClassTagCount = (classId) => {
  const item = tagTreeData.value.find(t => t.class_id === classId)
  return item?.total_tags || 0
}

const handleToggleRequired = async (tc) => {
  if (!tc) return
  const newVal = !tc.is_required
  try {
    const updated = await updateTagClass(tc.id, { is_required: newVal })
    tc.is_required = updated.is_required
    await mediaStore.loadFacetSummary()
    emit('changed')
  } catch (err) {
    console.error('Failed to toggle is_required:', err)
  }
}

const handleToggleProjectable = async (tc) => {
  if (!tc) return
  const newVal = !tc.is_projectable
  try {
    const updated = await updateTagClass(tc.id, { is_projectable: newVal })
    tc.is_projectable = updated.is_projectable
    await mediaStore.loadFacetSummary()
    emit('changed')
  } catch (err) {
    console.error('Failed to toggle is_projectable:', err)
  }
}

const handleCreateClass = async () => {
  const code = newClassForm.value.code.trim().toLowerCase()
  const name = newClassForm.value.display_name.trim()
  if (!code || !name) return

  try {
    const created = await createTagClass({
      code,
      display_name: name,
      icon: newClassForm.value.icon,
      color: newClassForm.value.color,
      is_projectable: newClassForm.value.is_projectable,
      is_required: newClassForm.value.is_required,
      description: newClassForm.value.description.trim() || undefined,
    })
    showCreateClassModal.value = false
    newClassForm.value = {
      code: '',
      display_name: '',
      icon: 'tag',
      color: '#3b82f6',
      is_projectable: true,
      is_required: false,
      description: '',
    }
    await loadData()
    selectedClassId.value = created.id
    await mediaStore.loadFacetSummary()
    emit('changed')
  } catch (err) {
    alert(t('tagMgr.createFacetFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleDeleteClass = async (tc) => {
  if (!tc) return
  const name = tFacet(tc.code, tc.display_name)
  if (tc.code === 'media_kind' || tc.code === 'workflow') {
    alert(`${name}: ${t('tagMgr.coreInvariantError')}`)
    return
  }

  if (!confirm(`${t('tagMgr.confirmDeleteFacet')} "${name}" (${tc.code})?`)) return

  try {
    await deleteTagClass(tc.id, false)
    await loadData()
    if (tagClasses.value.length > 0) {
      selectedClassId.value = tagClasses.value[0].id
    }
    await mediaStore.loadFacetSummary()
    emit('changed')
  } catch (err) {
    const detail = err.response?.data?.detail || err.message
    if (confirm(`${detail}\n\n${t('tagMgr.confirmForceDeleteFacet')}`)) {
      try {
        await deleteTagClass(tc.id, true)
        await loadData()
        if (tagClasses.value.length > 0) {
          selectedClassId.value = tagClasses.value[0].id
        }
        await mediaStore.loadFacetSummary()
        emit('changed')
      } catch (e2) {
        alert(t('tagMgr.forceDeleteFailed') + (e2.response?.data?.detail || e2.message))
      }
    }
  }
}

const openPresetsModal = async () => {
  try {
    presetsList.value = await fetchTaxonomyPresets()
    showPresetsModal.value = true
  } catch (err) {
    console.error('Failed to fetch presets:', err)
  }
}

const isPresetFullyLoaded = (preset) => {
  if (!preset || !preset.classes) return false
  const existingCodes = new Set(tagClasses.value.map(c => c.code))
  return preset.classes.every(c => existingCodes.has(c.code))
}

const handleApplyPreset = async (presetId) => {
  applyingPreset.value = true
  try {
    await applyTaxonomyPreset(presetId)
    await loadData()
    await mediaStore.loadFacetSummary()
    emit('changed')
  } catch (err) {
    alert(t('tagMgr.loadPresetFailed') + (err.response?.data?.detail || err.message))
  } finally {
    applyingPreset.value = false
  }
}

const handleCreateTag = async () => {
  if (!newTagName.value.trim() || !selectedClassId.value) return
  try {
    await createTag({
      name: newTagName.value.trim(),
      tag_class_id: selectedClassId.value,
      parent_id: newTagParentId.value,
    })
    newTagName.value = ''
    newTagParentId.value = null
    await loadData()
    emit('changed')
  } catch (err) {
    alert(t('tagMgr.createTagFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleReparent = async ({ tagId, newParentId }) => {
  try {
    await updateTagParent(tagId, newParentId)
    await loadData()
    emit('changed')
  } catch (err) {
    alert(t('tagMgr.reparentFailed') + (err.response?.data?.detail || err.message))
  }
}

const handleDelete = async (tagId) => {
  if (!confirm(t('tagMgr.confirmDeleteTag'))) return
  try {
    await deleteTagApi(tagId)
    await loadData()
    emit('changed')
  } catch (err) {
    alert(t('tagMgr.deleteTagFailed') + (err.response?.data?.detail || err.message))
  }
}

// Recursive Tag Tree Node Component
const TagTreeNode = defineComponent({
  name: 'TagTreeNode',
  props: {
    node: Object,
    level: Number,
    allClassTags: Array,
  },
  emits: ['reparent', 'delete'],
  setup(props, { emit }) {
    const isEditingParent = ref(false)
    const selectedParent = ref(props.node.parent_id)

    const applyParentChange = () => {
      emit('reparent', { tagId: props.node.id, newParentId: selectedParent.value })
      isEditingParent.value = false
    }

    const candidateParents = computed(() => {
      return props.allClassTags.filter(t => t.id !== props.node.id)
    })

    return () => {
      const n = props.node
      const lvl = props.level
      const indentPx = `${lvl * 24}px`

      return h('div', { class: 'group/node' }, [
        // Main Item Row
        h('div', {
          class: 'flex items-center justify-between p-2 rounded-xl transition-colors hover:bg-white/5 text-xs select-none',
          style: { paddingLeft: indentPx }
        }, [
          // Left: Icon + Tree branches indicator + Unit count
          h('div', { class: 'flex items-center gap-2 truncate flex-grow mr-2' }, [
            lvl > 0 ? h('span', { class: 'text-gray-600 font-mono select-none' }, '└── ') : null,
            h('span', { class: 'font-semibold text-white truncate' }, tData(n.name)),
            n.aliases && n.aliases.length > 0 ? h('span', {
              class: 'text-[10px] text-amber-300/80 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.2 rounded font-mono truncate max-w-[160px]',
              title: `${t('tagMgr.aliasTooltipPrefix')} ${n.aliases.join(', ')}`
            }, `≈ ${n.aliases.join(', ')}`) : null,
            h('span', { class: 'text-[10px] font-mono text-gray-500 bg-white/5 px-1.5 py-0.2 rounded-full shrink-0' }, `${n.unit_count || 0} ${t('tagMgr.assetsCountSuffix')}`)
          ]),

          // Right: Actions (Change Parent, Delete)
          h('div', { class: 'flex items-center gap-1.5 opacity-0 group-hover/node:opacity-100 transition-opacity shrink-0' }, [
            isEditingParent.value
              ? h('div', { class: 'flex items-center gap-1 bg-gray-900 border border-purple-500/40 rounded-lg p-1' }, [
                  h('select', {
                    value: selectedParent.value,
                    onChange: (e) => {
                      selectedParent.value = e.target.value === '' ? null : Number(e.target.value)
                    },
                    class: 'bg-transparent text-[11px] text-white outline-none max-w-[120px]'
                  }, [
                    h('option', { value: '' }, t('tagMgr.setRootOption')),
                    candidateParents.value.map(p => h('option', { value: p.id }, tData(p.name)))
                  ]),
                  h('button', {
                    onClick: applyParentChange,
                    class: 'text-[10px] bg-purple-600 text-white px-1.5 py-0.5 rounded cursor-pointer'
                  }, t('common.confirm')),
                  h('button', {
                    onClick: () => { isEditingParent.value = false },
                    class: 'text-[10px] text-gray-400 hover:text-white px-1 cursor-pointer'
                  }, t('common.cancel'))
                ])
              : h('button', {
                  onClick: () => { isEditingParent.value = true; selectedParent.value = n.parent_id },
                  class: 'text-[11px] text-purple-300 hover:text-white px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors cursor-pointer',
                  title: t('tagMgr.changeParentTip')
                }, t('tagMgr.changeParentBtn')),

            h('button', {
              onClick: () => emit('delete', n.id),
              class: 'text-gray-500 hover:text-red-400 p-1 rounded hover:bg-red-500/10 transition-colors cursor-pointer',
              title: t('tagMgr.deleteTagTip')
            }, [
              h('svg', { class: 'w-3.5 h-3.5', fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
                h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16' })
              ])
            ])
          ])
        ]),

        // Children Subtree
        n.children && n.children.length > 0
          ? h('div', { class: 'space-y-1' }, n.children.map(child =>
              h(TagTreeNode, {
                key: child.id,
                node: child,
                level: lvl + 1,
                allClassTags: props.allClassTags,
                onReparent: (args) => emit('reparent', args),
                onDelete: (id) => emit('delete', id)
              })
            ))
          : null
      ])
    }
  }
})
</script>
