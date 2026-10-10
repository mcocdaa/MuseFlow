<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
    <div 
      class="w-full max-w-4xl max-h-[85vh] flex flex-col rounded-2xl shadow-2xl border overflow-hidden"
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
            <h3 class="text-base font-bold" style="color: var(--text-main);">面向对象标签知识库 (Tag Taxonomy Manager)</h3>
            <p class="text-xs" style="color: var(--text-muted);">
              类继承树形拓扑 · 级联穿透筛选 · 物理落点锚定 · 零环路拓扑防卫
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
        <div class="w-56 border-r p-4 shrink-0 flex flex-col gap-2 overflow-y-auto" style="border-color: var(--border-color); background: var(--bg-surface);">
          <div class="text-[11px] font-semibold uppercase tracking-wider mb-1" style="color: var(--text-muted);">
            标签元类 (Tag Classes)
          </div>

          <button
            v-for="tc in tagClasses"
            :key="tc.id"
            @click="selectedClassId = tc.id"
            class="flex items-center justify-between p-2.5 rounded-xl text-xs font-medium transition-all text-left border"
            :style="selectedClassId === tc.id
              ? 'background: rgba(168, 85, 247, 0.15); color: #fff; border-color: rgba(168, 85, 247, 0.4);'
              : 'background: transparent; color: var(--text-muted); border-color: transparent;'"
          >
            <div class="flex items-center gap-2 truncate">
              <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: tc.color || '#a855f7' }"></span>
              <span class="truncate">{{ tc.display_name }}</span>
            </div>
            <span class="text-[10px] font-mono opacity-60 bg-white/5 px-1.5 py-0.2 rounded-full">
              {{ getClassTagCount(tc.id) }}
            </span>
          </button>
        </div>

        <!-- Right: Tag Hierarchy Tree & Create/Edit Area -->
        <div class="flex-1 flex flex-col p-5 overflow-y-auto space-y-4">
          <!-- Active Class Header & Add Tag Input Bar -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl border" style="background: var(--bg-surface); border-color: var(--border-color);">
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: currentClass?.color || '#a855f7' }"></span>
              <span class="text-sm font-bold text-white">{{ currentClass?.display_name }}</span>
              <span class="text-xs" style="color: var(--text-muted);">({{ currentClass?.description || '层级分类' }})</span>
            </div>

            <!-- Quick Add Tag Row -->
            <div class="flex items-center gap-2">
              <input
                v-model="newTagName"
                type="text"
                placeholder="新建标签名称..."
                class="bg-white/5 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 w-36 sm:w-44"
                @keyup.enter="handleCreateTag"
              />

              <select
                v-model="newTagParentId"
                class="bg-white/5 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-gray-300 outline-none max-w-[130px]"
                title="选择继承父标签 (可选)"
              >
                <option :value="null">-- 作为基类 (Root) --</option>
                <option v-for="t in currentClassTags" :key="t.id" :value="t.id">
                  继承: {{ t.name }}
                </option>
              </select>

              <button
                @click="handleCreateTag"
                class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-medium transition-all shrink-0 active:scale-95 shadow-sm"
              >
                + 添加
              </button>
            </div>
          </div>

          <!-- Tags Tree Representation -->
          <div class="border rounded-xl p-4 flex-1 overflow-y-auto" style="background: var(--bg-surface); border-color: var(--border-color);">
            <div v-if="loading" class="text-center py-12 text-xs" style="color: var(--text-muted);">
              加载标签拓扑中...
            </div>

            <div v-else-if="currentClassTree.length === 0" class="text-center py-12 text-xs" style="color: var(--text-muted);">
              当前元类下暂无标签，请在上方输入框新建
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
          <span>路径显示规则：仅1层显示名称；2层显示「父/子」；3层以上自动紧凑折叠为「... / 父类 / 当前类」。</span>
        </div>
        <button
          @click="close"
          class="px-4 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-white transition-colors"
        >
          完成并关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, defineComponent, h } from 'vue'
import {
  fetchTagClasses,
  fetchTagTree,
  fetchAllTagsFlat,
  createTag,
  updateTagParent,
  deleteTagApi
} from '../api'

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
      selectedClassId.value = classes[1]?.id || classes[0]?.id // default to domain or first
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

onMounted(() => {
  if (props.isOpen) {
    loadData()
  }
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
    alert('创建标签失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleReparent = async ({ tagId, newParentId }) => {
  try {
    await updateTagParent(tagId, newParentId)
    await loadData()
    emit('changed')
  } catch (err) {
    alert('调整继承关系失败：' + (err.response?.data?.detail || err.message))
  }
}

const handleDelete = async (tagId) => {
  if (!confirm('确定删除此标签吗？\n（已挂载该标签的资产会自动解绑，其子标签会自动挂载到上一级）')) return
  try {
    await deleteTagApi(tagId)
    await loadData()
    emit('changed')
  } catch (err) {
    alert('删除标签失败：' + (err.response?.data?.detail || err.message))
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

    // Filter available parents to exclude self
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
          // Left: Icon + Tree branches indicator + Display Path + Unit count
          h('div', { class: 'flex items-center gap-2 truncate flex-grow mr-2' }, [
            lvl > 0 ? h('span', { class: 'text-gray-600 font-mono select-none' }, '└── ') : null,
            h('span', { class: 'font-semibold text-white truncate' }, n.name),
            n.parent_name ? h('span', {
              class: 'text-[10px] text-purple-400/80 bg-purple-500/10 border border-purple-500/20 px-1.5 py-0.2 rounded font-mono truncate max-w-[200px]',
              title: n.full_path
            }, n.display_path) : null,
            n.aliases && n.aliases.length > 0 ? h('span', {
              class: 'text-[10px] text-amber-300/80 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.2 rounded font-mono truncate max-w-[160px]',
              title: `同义词/别名: ${n.aliases.join(', ')}`
            }, `≈ ${n.aliases.join(', ')}`) : null,
            h('span', { class: 'text-[10px] font-mono text-gray-500 bg-white/5 px-1.5 py-0.2 rounded-full shrink-0' }, `${n.unit_count || 0} 部资产`)
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
                    h('option', { value: '' }, '-- 设为根类 --'),
                    candidateParents.value.map(p => h('option', { value: p.id }, p.name))
                  ]),
                  h('button', {
                    onClick: applyParentChange,
                    class: 'text-[10px] bg-purple-600 text-white px-1.5 py-0.5 rounded'
                  }, '确定'),
                  h('button', {
                    onClick: () => { isEditingParent.value = false },
                    class: 'text-[10px] text-gray-400 hover:text-white px-1'
                  }, '取消')
                ])
              : h('button', {
                  onClick: () => { isEditingParent.value = true; selectedParent.value = n.parent_id },
                  class: 'text-[11px] text-purple-300 hover:text-white px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors',
                  title: '更改此标签的父级继承关系'
                }, '调整父级'),

            h('button', {
              onClick: () => emit('delete', n.id),
              class: 'text-gray-500 hover:text-red-400 p-1 rounded hover:bg-red-500/10 transition-colors',
              title: '删除此标签'
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
