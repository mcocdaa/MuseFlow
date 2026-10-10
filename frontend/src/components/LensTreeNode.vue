<script setup>
import { ref } from 'vue'
import { ChevronRight, ChevronDown, Tag, AlertCircle, Folder, Hash } from 'lucide-vue-next'

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  depth: {
    type: Number,
    default: 0
  },
  selectedTagId: {
    type: [Number, String, null],
    default: null
  },
  selectedMissingFacet: {
    type: [String, null],
    default: null
  },
  activeClassCode: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['select'])

// Default expand top 2 levels
const isExpanded = ref(props.depth < 2)

const hasChildren = props.node.children && props.node.children.length > 0

const toggleExpand = (e) => {
  e?.stopPropagation()
  isExpanded.value = !isExpanded.value
}

const isSelected = () => {
  if (props.node.is_unassigned) {
    return props.selectedMissingFacet === props.node.missing_facet
  }
  return props.selectedTagId === props.node.id
}

const handleNodeClick = () => {
  if (hasChildren && !isExpanded.value) {
    isExpanded.value = true
  }
  emit('select', props.node)
}
</script>

<template>
  <div class="lens-tree-node select-none">
    <div
      @click="handleNodeClick"
      class="group/node flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer transition-all text-xs font-medium"
      :class="[
        isSelected()
          ? node.is_unassigned
            ? 'bg-amber-500/25 text-amber-200 border border-amber-500/40 shadow-sm'
            : 'bg-purple-600/30 text-purple-200 border border-purple-500/40 shadow-sm'
          : node.is_unassigned
            ? 'text-amber-300/90 hover:bg-amber-500/10 hover:text-amber-200'
            : 'text-gray-300 hover:bg-white/5 hover:text-white'
      ]"
      :style="{ paddingLeft: `${8 + depth * 14}px` }"
      :title="node.display_path || node.name"
    >
      <div class="flex items-center gap-1.5 min-w-0 truncate">
        <!-- Expand / Collapse chevron if children exist -->
        <button
          v-if="hasChildren"
          @click="toggleExpand"
          class="p-0.5 -ml-1 text-gray-400 hover:text-white rounded hover:bg-white/10 transition-colors shrink-0"
        >
          <ChevronDown v-if="isExpanded" class="w-3.5 h-3.5" />
          <ChevronRight v-else class="w-3.5 h-3.5" />
        </button>
        <span v-else class="w-3 shrink-0"></span>

        <!-- Icon -->
        <AlertCircle
          v-if="node.is_unassigned"
          class="w-3.5 h-3.5 text-amber-400 shrink-0"
        />
        <Tag
          v-else-if="depth > 0"
          class="w-3.5 h-3.5 text-purple-400/80 shrink-0"
        />
        <Folder
          v-else
          class="w-3.5 h-3.5 text-indigo-400 shrink-0"
        />

        <!-- Title -->
        <span class="truncate" :class="{ 'font-semibold': depth === 0 || node.is_unassigned }">
          {{ node.name }}
        </span>
      </div>

      <!-- Count Badge -->
      <div class="flex items-center gap-1 shrink-0 ml-2">
        <span
          class="text-[10px] px-1.5 py-0.5 rounded-full font-mono transition-colors"
          :class="[
            node.is_unassigned
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : isSelected()
                ? 'bg-purple-500/30 text-purple-200'
                : 'bg-white/5 text-gray-400 group-hover/node:text-gray-300'
          ]"
          :title="hasChildren ? `包含子孙累计: ${node.unit_count} 项 (直属: ${node.direct_count || 0})` : `${node.unit_count} 项`"
        >
          {{ node.unit_count }}
        </span>
      </div>
    </div>

    <!-- Recursive children -->
    <div v-if="hasChildren && isExpanded" class="relative">
      <!-- Subtle tree line guide -->
      <div
        class="absolute left-0 top-0 bottom-0 border-l border-white/5"
        :style="{ left: `${14 + depth * 14}px` }"
      ></div>

      <LensTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :selectedTagId="selectedTagId"
        :selectedMissingFacet="selectedMissingFacet"
        :activeClassCode="activeClassCode"
        @select="(n) => emit('select', n)"
      />
    </div>
  </div>
</template>
