<template>
  <div class="space-y-4 animate-fade-in">
    <!-- Collapsible Preset Drawer (Only shown when Sparkles icon is toggled) -->
    <div
      v-if="showPresetsPanel"
      class="p-4 rounded-2xl border space-y-3 animate-fade-in"
      style="background-color: var(--bg-surface-elevated); border-color: var(--border-color);"
    >
      <div class="flex items-center justify-between">
        <div
          class="flex items-center gap-2 text-xs font-semibold text-white"
          :title="t('tax.presetsTip')"
        >
          <Sparkles class="w-3.5 h-3.5 text-purple-400" />
          <span>{{ t('tax.presetsTitle') }}</span>
        </div>
        <button
          @click="showPresetsPanel = false"
          class="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          :title="t('tax.closePresetsTip')"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
        <div
          v-for="p in presetsList"
          :key="p.id"
          :title="tData(p.description)"
          class="p-3 rounded-xl border flex flex-col justify-between gap-2.5 transition-all hover:border-purple-500/40"
          style="background-color: var(--bg-surface); border-color: var(--border-color);"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="font-semibold text-xs text-white truncate">{{ tData(p.name) }}</span>
            <button
              @click="handleApplyPreset(p.id)"
              :disabled="applyingPreset === p.id"
              class="w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer disabled:opacity-50 shrink-0"
              :class="isPresetApplied(p)
                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25'
                : 'bg-white/5 hover:bg-purple-600 text-gray-300 hover:text-white border border-white/10 hover:border-purple-500'"
              :title="isPresetApplied(p) ? t('tax.presetAppliedTip') : t('tax.applyPresetTip')"
            >
              <RefreshCw v-if="applyingPreset === p.id" class="w-3.5 h-3.5 animate-spin" />
              <Check v-else-if="isPresetApplied(p)" class="w-3.5 h-3.5" />
              <Plus v-else class="w-3.5 h-3.5" />
            </button>
          </div>

          <div class="flex flex-wrap gap-1">
            <span
              v-for="c in p.classes"
              :key="c.code"
              class="px-1.5 py-0.5 rounded text-[10px] font-medium border"
              :style="{
                backgroundColor: `${c.color}15`,
                borderColor: `${c.color}35`,
                color: c.color
              }"
              :title="`${tFacet(c.code, c.display_name)} (${c.code})`"
            >
              {{ tFacet(c.code, c.display_name) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Main 3-Column Linear-Grade Minimalist Workspace -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-[720px]">
      <!-- Column 1 (3 cols): Orthogonal Dimensions -->
      <aside
        class="lg:col-span-3 border rounded-2xl p-3.5 flex flex-col gap-2.5"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Minimal Sidebar Header -->
        <div class="flex items-center justify-between px-1 pb-2 border-b border-white/5">
          <div class="flex items-center gap-1.5">
            <button
              @click="$emit('back-to-assets')"
              class="p-1.5 -ml-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              :title="t('tax.backToAssetsTip')"
            >
              <ArrowLeft class="w-3.5 h-3.5" />
            </button>
            <span
              class="text-xs font-semibold text-gray-300"
              :title="t('tax.dimensionsHeaderTip', { classes: tagClasses.length, tags: totalTagsCount })"
            >
              {{ t('tax.dimensionsHeader') }}
            </span>
          </div>

          <div class="flex items-center gap-1">
            <button
              @click="togglePresetsPanel"
              :class="[
                'w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer',
                showPresetsPanel
                  ? 'bg-purple-600 text-white'
                  : 'text-gray-400 hover:text-purple-300 hover:bg-white/5'
              ]"
              :title="t('tax.presetsBtnTip')"
            >
              <Sparkles class="w-3.5 h-3.5" />
            </button>

            <button
              @click="handleReorganizeAll"
              :disabled="reorganizing"
              class="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/5 transition-all cursor-pointer disabled:opacity-40"
              :title="t('tax.reorganizeBtnTip')"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin text-purple-400': reorganizing }" />
            </button>

            <button
              @click="showCreateClassCard = !showCreateClassCard"
              :class="[
                'w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer',
                showCreateClassCard
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              ]"
              :title="t('tax.createClassBtnTip')"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Compact Inline Create Dimension Popover -->
        <div
          v-if="showCreateClassCard"
          class="p-2.5 rounded-xl border border-white/10 bg-black/25 space-y-2 text-xs animate-fade-in"
        >
          <div class="grid grid-cols-2 gap-1.5">
            <input
              v-model="newClassForm.display_name"
              type="text"
              :placeholder="t('tax.newClassNamePlaceholder')"
              class="w-full bg-black/30 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-400"
              @keyup.enter="handleCreateClass"
            />
            <input
              v-model="newClassForm.code"
              type="text"
              :placeholder="t('tax.newClassCodePlaceholder')"
              class="w-full bg-black/30 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white font-mono placeholder-gray-500 focus:outline-none focus:border-blue-400"
              @keyup.enter="handleCreateClass"
            />
          </div>

          <div class="flex items-center justify-between pt-0.5">
            <div class="flex items-center gap-1">
              <button
                v-for="c in presetColors"
                :key="c"
                type="button"
                @click="newClassForm.color = c"
                class="w-3.5 h-3.5 rounded-full border transition-all cursor-pointer"
                :style="{ backgroundColor: c, borderColor: newClassForm.color === c ? '#fff' : 'transparent' }"
              />
            </div>

            <div class="flex items-center gap-1">
              <button
                type="button"
                @click="newClassForm.is_projectable = !newClassForm.is_projectable"
                class="w-6 h-6 rounded flex items-center justify-center transition-colors cursor-pointer"
                :class="newClassForm.is_projectable ? 'bg-blue-500/20 text-blue-300' : 'text-gray-500 hover:text-gray-300'"
                :title="t('tax.allowProjectableTip')"
              >
                <Folder class="w-3 h-3" />
              </button>
              <button
                type="button"
                @click="newClassForm.is_required = !newClassForm.is_required"
                class="w-6 h-6 rounded flex items-center justify-center transition-colors cursor-pointer"
                :class="newClassForm.is_required ? 'bg-amber-500/20 text-amber-300' : 'text-gray-500 hover:text-gray-300'"
                :title="t('tax.setRequiredTip')"
              >
                <Star class="w-3 h-3" />
              </button>
              <button
                type="button"
                @click="handleCreateClass"
                :disabled="!newClassForm.display_name.trim() || !newClassForm.code.trim()"
                class="w-6 h-6 rounded bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center disabled:opacity-30 cursor-pointer"
                :title="t('tax.confirmCreateClassTip')"
              >
                <Check class="w-3 h-3" />
              </button>
              <button
                type="button"
                @click="showCreateClassCard = false"
                class="w-6 h-6 rounded text-gray-400 hover:text-white hover:bg-white/10 flex items-center justify-center cursor-pointer"
                :title="t('common.cancel')"
              >
                <X class="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        <!-- Single-Line Dimension List -->
        <div class="flex-1 space-y-1 overflow-y-auto pr-0.5">
          <button
            v-for="tc in tagClasses"
            :key="tc.id"
            @click="selectClass(tc.id)"
            :title="formatDimensionTooltip(tc)"
            class="w-full px-3 py-2 rounded-xl text-left transition-all border flex items-center justify-between gap-2 cursor-pointer group"
            :class="selectedClassId === tc.id
              ? 'bg-purple-600/20 border-purple-500/40 text-white'
              : 'bg-transparent hover:bg-white/[0.04] border-transparent text-gray-300'"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: tc.color || '#a855f7' }" />
              <span class="text-xs font-medium truncate">{{ tFacet(tc.code, tc.display_name) }}</span>
              <Star
                v-if="tc.is_required && tc.code !== 'media_kind'"
                class="w-3 h-3 text-amber-400/80 shrink-0"
              />
            </div>
            <span class="text-[11px] font-mono text-gray-500 group-hover:text-gray-300 shrink-0">
              {{ getClassTagCount(tc.id) }}
            </span>
          </button>
        </div>
      </aside>

      <!-- Column 2 (5 cols): Active Dimension Tag Tree -->
      <section
        class="lg:col-span-5 border rounded-2xl p-3.5 flex flex-col gap-3"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <!-- Single-Line Dimension Header & Icon Controls -->
        <div
          v-if="currentClass"
          class="flex items-center justify-between gap-2 pb-2.5 border-b border-white/5 px-1"
        >
          <div
            class="flex items-center gap-2 min-w-0"
            :title="t('tax.currentClassHeaderTip', { name: tFacet(currentClass.code, currentClass.display_name), code: currentClass.code, count: currentClassTags.length })"
          >
            <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: currentClass.color || '#a855f7' }" />
            <h3 class="text-sm font-semibold text-white truncate">{{ tFacet(currentClass.code, currentClass.display_name) }}</h3>
            <span class="text-xs font-mono text-gray-500">{{ currentClassTags.length }}</span>
          </div>

          <div class="flex items-center gap-1 shrink-0">
            <button
              @click="handleCopyMCPColumnPrompt(currentClass)"
              class="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-purple-300 hover:bg-purple-500/15 transition-all cursor-pointer"
              :title="t('tax.copyMcpPromptTip', { name: tFacet(currentClass.code, currentClass.display_name) })"
            >
              <Bot class="w-3.5 h-3.5" />
            </button>

            <button
              v-if="currentClass.code !== 'media_kind'"
              @click="handleToggleRequired(currentClass)"
              class="w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer"
              :class="currentClass.is_required
                ? 'bg-amber-500/15 text-amber-300'
                : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'"
              :title="currentClass.is_required ? t('tax.requiredToggleOnTip') : t('tax.requiredToggleOffTip')"
            >
              <Star class="w-3.5 h-3.5" :class="{ 'fill-amber-400/30': currentClass.is_required }" />
            </button>

            <button
              @click="handleToggleProjectable(currentClass)"
              class="w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer"
              :class="currentClass.is_projectable
                ? 'bg-blue-500/15 text-blue-300'
                : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'"
              :title="currentClass.is_projectable ? t('tax.projectableToggleOnTip') : t('tax.projectableToggleOffTip')"
            >
              <Folder class="w-3.5 h-3.5" />
            </button>

            <button
              v-if="currentClass.code !== 'media_kind' && currentClass.code !== 'workflow'"
              @click="handleDeleteClass(currentClass)"
              class="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
              :title="t('tax.deleteClassTip')"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Unified Single-Row Search & Quick-Create Bar -->
        <div class="flex items-center gap-2">
          <!-- Filter Input -->
          <div class="relative w-36 sm:w-44 shrink-0">
            <Search class="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              v-model="treeSearchQuery"
              type="text"
              :placeholder="t('tax.searchPlaceholder')"
              class="w-full bg-black/20 border border-white/10 rounded-xl pl-8 pr-6 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
            />
            <button
              v-if="treeSearchQuery"
              @click="treeSearchQuery = ''"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white cursor-pointer"
              :title="t('tax.clearSearchTip')"
            >
              <X class="w-3 h-3" />
            </button>
          </div>

          <!-- Quick Create Tag Input -->
          <div
            class="flex-1 flex items-center gap-1.5 bg-black/20 border border-white/10 rounded-xl px-2.5 py-1 focus-within:border-purple-500/60 min-w-0"
          >
            <span
              v-if="newTagParentNode"
              class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] flex items-center gap-1 shrink-0 max-w-[100px]"
              :title="t('tax.parentTagChipTip', { name: tData(newTagParentNode.name) })"
            >
              <span class="truncate">{{ tData(newTagParentNode.name) }}</span>
              <X class="w-2.5 h-2.5 cursor-pointer shrink-0 hover:text-white" @click="newTagParentId = null" />
            </span>

            <input
              ref="newTagInputRef"
              v-model="newTagName"
              type="text"
              :placeholder="newTagParentNode ? t('tax.newChildTagPlaceholder') : t('tax.newTagPlaceholder')"
              class="flex-1 bg-transparent text-xs text-white placeholder-gray-500 focus:outline-none min-w-0 py-0.5"
              @keyup.enter="handleCreateTag"
            />

            <button
              @click="handleCreateTag"
              :disabled="!newTagName.trim()"
              class="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 disabled:opacity-30 transition-colors cursor-pointer shrink-0"
              :title="t('tax.createTagEnterTip')"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Tag Tree List -->
        <div class="flex-1 overflow-y-auto space-y-0.5 pr-1 max-h-[600px]">
          <div v-if="loading" class="py-16 text-center text-xs text-gray-500">
            {{ t('tax.loading') }}
          </div>

          <div v-else-if="filteredFlatTags !== null">
            <div v-if="filteredFlatTags.length === 0" class="py-12 text-center text-xs text-gray-500">
              {{ t('tax.noMatchingTags') }}
            </div>
            <div v-else class="space-y-0.5">
              <div
                v-for="item in filteredFlatTags"
                :key="item.id"
                @click="selectTagNode(item)"
                class="flex items-center justify-between px-3 py-1.5 rounded-xl border transition-all cursor-pointer group"
                :class="selectedTagId === item.id
                  ? 'bg-purple-600/20 border-purple-500/40 text-white'
                  : 'bg-transparent hover:bg-white/[0.04] border-transparent text-gray-200'"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <TagIcon class="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  <span class="text-xs truncate">{{ tData(item.display_path || item.name) }}</span>
                </div>
                <span class="text-[11px] font-mono text-gray-500 shrink-0" :title="t('tax.linkedUnitsCountTip')">
                  {{ item.unit_count || 0 }}
                </span>
              </div>
            </div>
          </div>

          <div v-else-if="currentClassTree.length === 0" class="py-16 text-center text-xs text-gray-500">
            {{ t('tax.noTagsYet') }}
          </div>

          <div v-else class="space-y-0.5">
            <template v-for="row in flattenedTreeRows" :key="row.node.id">
              <div
                @click="selectTagNode(row.node)"
                class="flex items-center justify-between py-1.5 px-2.5 rounded-xl border transition-all cursor-pointer group"
                :class="selectedTagId === row.node.id
                  ? 'bg-purple-600/20 border-purple-500/40 text-white'
                  : 'bg-transparent hover:bg-white/[0.04] border-transparent text-gray-200'"
                :style="{ marginLeft: `${row.depth * 16}px` }"
              >
                <div class="flex items-center gap-1.5 min-w-0">
                  <button
                    v-if="row.node.children && row.node.children.length > 0"
                    @click.stop="toggleExpandTag(row.node.id)"
                    class="w-4 h-4 rounded flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer shrink-0"
                  >
                    <ChevronDown v-if="isTagExpanded(row.node.id, row.depth)" class="w-3.5 h-3.5" />
                    <ChevronRight v-else class="w-3.5 h-3.5" />
                  </button>
                  <span v-else class="w-4 text-center text-gray-600 text-[10px] shrink-0">
                    {{ row.depth > 0 ? '└' : '·' }}
                  </span>

                  <span class="text-xs font-medium truncate">{{ tData(row.node.name) }}</span>
                </div>

                <div class="flex items-center gap-1 shrink-0">
                  <button
                    @click.stop="prepareChildTag(row.node)"
                    class="opacity-0 group-hover:opacity-100 p-1 rounded-lg text-gray-400 hover:text-purple-300 hover:bg-purple-500/15 transition-all cursor-pointer"
                    :title="t('tax.addChildUnderTip', { name: tData(row.node.name) })"
                  >
                    <Plus class="w-3.5 h-3.5" />
                  </button>
                  <button
                    @click.stop="handleDeleteTag(row.node)"
                    class="opacity-0 group-hover:opacity-100 p-1 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
                    :title="t('tax.deleteTagTip')"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                  <span
                    class="text-[11px] font-mono text-gray-500 group-hover:text-gray-300 min-w-[18px] text-right"
                    :title="t('tax.linkedUnitsCountTip')"
                  >
                    {{ row.node.unit_count || 0 }}
                  </span>
                </div>
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- Column 3 (4 cols): Minimalist Tag Inspector -->
      <aside
        class="lg:col-span-4 border rounded-2xl p-3.5 flex flex-col gap-3.5"
        style="background-color: var(--bg-surface); border-color: var(--border-color);"
      >
        <template v-if="selectedTag">
          <!-- Top Bar: Inline Editable Name + Icon Actions -->
          <div class="flex items-center justify-between gap-2 pb-2.5 border-b border-white/5">
            <div class="flex items-center gap-2 flex-1 min-w-0">
              <span
                class="w-2.5 h-2.5 rounded-full shrink-0"
                :style="{ backgroundColor: currentClass?.color || '#a855f7' }"
              />
              <input
                v-model="editTagName"
                type="text"
                :title="t('tax.editTagNameTip', { id: selectedTag.id, path: tData(selectedTag.full_path || selectedTag.name) })"
                class="flex-1 bg-transparent hover:bg-white/[0.04] focus:bg-black/25 border border-transparent focus:border-purple-500/50 rounded-lg px-2 py-1 text-sm font-semibold text-white focus:outline-none transition-colors min-w-0"
                @keyup.enter="handleSaveTagUpdate"
              />
              <button
                v-if="editTagName.trim() && editTagName.trim() !== selectedTag.name"
                @click="handleSaveTagUpdate"
                class="w-7 h-7 rounded-lg bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center transition-colors cursor-pointer shrink-0"
                :title="t('tax.saveTagNameTip')"
              >
                <Check class="w-3.5 h-3.5" />
              </button>
            </div>

            <div class="flex items-center gap-1 shrink-0">
              <button
                @click="handleJumpToAssetsWithTag(selectedTag)"
                class="w-7 h-7 rounded-lg text-gray-400 hover:text-purple-300 hover:bg-purple-500/15 flex items-center justify-center transition-colors cursor-pointer"
                :title="t('tax.filterInAssetsTip')"
              >
                <ArrowUpRight class="w-4 h-4" />
              </button>
              <button
                @click="handleDeleteTag(selectedTag)"
                class="w-7 h-7 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 flex items-center justify-center transition-colors cursor-pointer"
                :title="t('tax.deleteTagTip')"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Hierarchy & Dimension Selectors (2 clean columns with icons) -->
          <div class="grid grid-cols-2 gap-2 pb-3 border-b border-white/5">
            <div
              class="flex items-center gap-1.5 bg-black/20 border border-white/10 rounded-xl px-2.5 py-1.5"
              :title="t('tax.parentSelectorTip')"
            >
              <GitBranch class="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <select
                :value="selectedTag.parent_id || ''"
                @change="(e) => handleReparent(selectedTag.id, e.target.value ? Number(e.target.value) : null)"
                class="w-full bg-transparent text-xs text-gray-200 outline-none truncate cursor-pointer"
              >
                <option value="" class="bg-neutral-900">{{ t('tax.rootTagOption') }}</option>
                <option
                  v-for="tItem in availableParentCandidates"
                  :key="tItem.id"
                  :value="tItem.id"
                  class="bg-neutral-900"
                >
                  {{ tData(tItem.display_path || tItem.name) }}
                </option>
              </select>
            </div>

            <div
              class="flex items-center gap-1.5 bg-black/20 border border-white/10 rounded-xl px-2.5 py-1.5"
              :title="t('tax.classSelectorTip')"
            >
              <Layers class="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <select
                :value="selectedClassId"
                @change="(e) => handleMoveTagClass(selectedTag.id, Number(e.target.value))"
                class="w-full bg-transparent text-xs text-gray-200 outline-none truncate cursor-pointer"
              >
                <option v-for="tc in tagClasses" :key="tc.id" :value="tc.id" class="bg-neutral-900">
                  {{ tFacet(tc.code, tc.display_name) }}
                </option>
              </select>
            </div>
          </div>

          <!-- Synonyms / Aliases (Inline Flow) -->
          <div class="space-y-2 pb-3 border-b border-white/5">
            <div class="flex items-center justify-between">
              <span
                class="text-[11px] font-medium text-gray-400"
                :title="t('tax.aliasesTip')"
              >
                {{ t('tax.aliasesTitle') }}
              </span>
              <span v-if="tagAliases.length > 0" class="text-[11px] font-mono text-gray-500">
                {{ tagAliases.length }}
              </span>
            </div>

            <div class="flex flex-wrap items-center gap-1.5">
              <span
                v-for="al in tagAliases"
                :key="al.id"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] bg-white/5 border border-white/10 text-gray-200 group"
              >
                <span>{{ al.alias_name }}</span>
                <button
                  @click="handleRemoveAlias(al.id)"
                  class="text-gray-500 hover:text-red-400 cursor-pointer"
                  :title="t('tax.removeAliasTip')"
                >
                  <X class="w-3 h-3" />
                </button>
              </span>

              <div class="inline-flex items-center gap-1 bg-black/20 border border-white/10 rounded-lg px-2 py-0.5 focus-within:border-purple-500/50">
                <input
                  v-model="newAliasName"
                  type="text"
                  :placeholder="t('tax.addAliasPlaceholder')"
                  class="w-24 bg-transparent text-[11px] text-white placeholder-gray-500 focus:outline-none"
                  @keyup.enter="handleAddAlias"
                />
                <button
                  v-if="newAliasName.trim()"
                  @click="handleAddAlias"
                  class="text-purple-400 hover:text-purple-300 cursor-pointer"
                  :title="t('tax.addAliasTip')"
                >
                  <Plus class="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>

          <!-- Linked Works List -->
          <div class="flex-1 flex flex-col min-h-0 space-y-2">
            <div class="flex items-center justify-between">
              <span
                class="text-[11px] font-medium text-gray-400"
                :title="t('tax.linkedUnitsDescTip')"
              >
                {{ t('tax.linkedUnitsTitle') }}
              </span>
              <span class="text-[11px] font-mono text-gray-500">{{ tagUnits.length }}</span>
            </div>

            <div v-if="loadingUnits" class="py-8 text-center text-xs text-gray-500">
              {{ t('tax.loading') }}
            </div>
            <div v-else-if="tagUnits.length === 0" class="py-8 text-center text-xs text-gray-500">
              {{ t('tax.noLinkedUnits') }}
            </div>
            <div v-else class="flex-1 overflow-y-auto space-y-1 pr-0.5 max-h-[360px]">
              <div
                v-for="u in tagUnits"
                :key="u.id"
                class="flex items-center justify-between gap-2 px-2 py-1.5 rounded-xl hover:bg-white/[0.04] transition-colors group"
              >
                <div class="flex items-center gap-2.5 min-w-0">
                  <img
                    :src="`/api/stream/thumbnail/${u.id}`"
                    class="w-7 h-7 rounded-lg object-cover bg-black/40 shrink-0"
                    @error="(e) => e.target.style.display = 'none'"
                  />
                  <span class="text-xs text-gray-200 truncate" :title="tData(u.title)">{{ tData(u.title) }}</span>
                </div>
                <button
                  @click="handleUnlinkUnitTag(u.id, selectedTag.id)"
                  class="opacity-0 group-hover:opacity-100 p-1 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer shrink-0"
                  :title="t('tax.unlinkTagTip')"
                >
                  <X class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </template>

        <!-- Minimalist Empty Inspector -->
        <template v-else>
          <div class="flex-1 flex flex-col items-center justify-center text-center p-6 gap-2">
            <TagIcon class="w-5 h-5 text-gray-600" />
            <span class="text-xs text-gray-500">{{ t('tax.emptyInspectorHint') }}</span>

            <button
              v-if="currentClass && getFacetStat(currentClass.code)?.missing_units > 0"
              @click="handleJumpToMissingFacet(currentClass.code)"
              class="mt-4 px-3 py-1.5 rounded-xl border border-amber-500/25 bg-amber-500/10 hover:bg-amber-500/20 text-amber-200 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
              :title="t('tax.filterMissingFacetTip', { name: tFacet(currentClass.code, currentClass.display_name) })"
            >
              <span>{{ t('tax.missingFacetCountBtn', { count: getFacetStat(currentClass.code).missing_units }) }}</span>
              <ArrowUpRight class="w-3.5 h-3.5" />
            </button>
          </div>
        </template>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import {
  ArrowLeft,
  ArrowUpRight,
  Bot,
  Tag as TagIcon,
  Sparkles,
  Plus,
  RefreshCw,
  Search,
  X,
  Check,
  Star,
  Folder,
  GitBranch,
  Layers,
  ChevronDown,
  ChevronRight,
  Trash2,
} from 'lucide-vue-next'
import {
  fetchTagTree,
  fetchTaxonomyPresets,
  applyTaxonomyPreset,
  createTagClass,
  updateTagClass,
  deleteTagClass,
  createTag,
  updateTag,
  updateTagParent,
  deleteTagApi,
  fetchTagAliases,
  addTagAlias,
  removeTagAlias,
  fetchTagUnits,
  removeTag,
  reorganizeTags,
} from '../api'
import { useMediaStore } from '../stores/mediaStore'
import { usePlayerStore } from '../stores/playerStore'
import { t, tData, tFacet } from '../i18n'

const props = defineProps({
  initialClassCode: { type: String, default: null },
  initialTagId: { type: Number, default: null },
})

const emit = defineEmits(['back-to-assets', 'jump-to-tag', 'jump-to-missing'])

const mediaStore = useMediaStore()
const playerStore = usePlayerStore()

const loading = ref(false)
const reorganizing = ref(false)
const tagTreeData = ref([])
const selectedClassId = ref(null)
const selectedTagId = ref(null)
const treeSearchQuery = ref('')
const newTagInputRef = ref(null)

// Expand/collapse state for tag tree
const expandedTagIds = ref(new Set())
const collapsedRootIds = ref(new Set())

// Create Tag form
const newTagName = ref('')
const newTagParentId = ref(null)

// Create Class inline card
const showCreateClassCard = ref(false)
const presetColors = ['#8b5cf6', '#ec4899', '#f43f5e', '#f59e0b', '#10b981', '#06b6d4', '#3b82f6', '#6366f1']
const newClassForm = ref({
  display_name: '',
  code: '',
  color: '#8b5cf6',
  is_projectable: true,
  is_required: false,
})

// Presets panel
const showPresetsPanel = ref(false)
const presetsList = ref([])
const applyingPreset = ref(null)

// Right column inspector state
const editTagName = ref('')
const tagAliases = ref([])
const newAliasName = ref('')
const tagUnits = ref([])
const loadingUnits = ref(false)

const tagClasses = computed(() => {
  return tagTreeData.value.map(d => ({
    id: d.class_id,
    code: d.code,
    display_name: d.display_name,
    icon: d.icon,
    color: d.color,
    total_tags: d.total_tags,
    is_required: mediaStore.facetSummary?.find(f => f.code === d.code)?.is_required ?? false,
    is_projectable: mediaStore.facetSummary?.find(f => f.code === d.code)?.is_projectable ?? true,
  }))
})

const totalTagsCount = computed(() => {
  return tagTreeData.value.reduce((acc, c) => acc + (c.total_tags || 0), 0)
})

const currentClass = computed(() => {
  return tagClasses.value.find(c => c.id === selectedClassId.value) || null
})

const currentClassTree = computed(() => {
  const found = tagTreeData.value.find(d => d.class_id === selectedClassId.value)
  return found ? found.tree : []
})

const flattenTree = (nodes, list = []) => {
  for (const n of nodes) {
    list.push(n)
    if (n.children && n.children.length > 0) {
      flattenTree(n.children, list)
    }
  }
  return list
}

const currentClassTags = computed(() => {
  return flattenTree(currentClassTree.value)
})

const newTagParentNode = computed(() => {
  if (!newTagParentId.value) return null
  return currentClassTags.value.find(t => t.id === newTagParentId.value) || null
})

const selectedTag = computed(() => {
  if (!selectedTagId.value) return null
  return currentClassTags.value.find(t => t.id === selectedTagId.value) || null
})

const availableParentCandidates = computed(() => {
  if (!selectedTag.value) return []
  return currentClassTags.value.filter(t => t.id !== selectedTag.value.id)
})

const filteredFlatTags = computed(() => {
  const q = treeSearchQuery.value.trim().toLowerCase()
  if (!q) return null
  return currentClassTags.value.filter(
    t => t.name.toLowerCase().includes(q) || (t.display_path && t.display_path.toLowerCase().includes(q))
  )
})

const isTagExpanded = (tagId, depth) => {
  if (depth === 0) {
    return !collapsedRootIds.value.has(tagId)
  }
  return expandedTagIds.value.has(tagId)
}

const toggleExpandTag = (tagId) => {
  const rootIds = new Set(currentClassTree.value.map(n => n.id))
  if (rootIds.has(tagId)) {
    const next = new Set(collapsedRootIds.value)
    if (next.has(tagId)) next.delete(tagId)
    else next.add(tagId)
    collapsedRootIds.value = next
  } else {
    const next = new Set(expandedTagIds.value)
    if (next.has(tagId)) next.delete(tagId)
    else next.add(tagId)
    expandedTagIds.value = next
  }
}

const flattenedTreeRows = computed(() => {
  const rows = []
  const walk = (nodes, depth = 0) => {
    for (const n of nodes) {
      rows.push({ node: n, depth })
      if (n.children && n.children.length > 0 && isTagExpanded(n.id, depth)) {
        walk(n.children, depth + 1)
      }
    }
  }
  walk(currentClassTree.value, 0)
  return rows
})

const getClassTagCount = (classId) => {
  const found = tagTreeData.value.find(d => d.class_id === classId)
  return found ? found.total_tags : 0
}

const getFacetStat = (code) => {
  return mediaStore.facetSummary?.find(f => f.code === code) || null
}

const formatDimensionTooltip = (tc) => {
  const stat = getFacetStat(tc.code)
  const parts = [`${tFacet(tc.code, tc.display_name)} (${tc.code})`, `${getClassTagCount(tc.id)} ${t('tax.tagsSuffix')}`]
  if (stat) {
    parts.push(`${t('tax.coveragePrefix')} ${stat.coverage_percent}% (${stat.tagged_units}/${stat.total_units})`)
  }
  if (tc.is_required) parts.push(t('tax.requiredFacet'))
  return parts.join(' · ')
}

const prepareChildTag = (parentNode) => {
  newTagParentId.value = parentNode.id
  nextTick(() => {
    newTagInputRef.value?.focus()
  })
}

const loadData = async () => {
  loading.value = true
  try {
    const [data] = await Promise.all([
      fetchTagTree(),
      mediaStore.loadFacetSummary(),
    ])
    tagTreeData.value = data
    if (props.initialClassCode) {
      const target = data.find(d => d.code === props.initialClassCode)
      if (target) selectedClassId.value = target.class_id
    }
    if (!selectedClassId.value && data.length > 0) {
      const domainClass = data.find(d => d.code === 'domain')
      selectedClassId.value = domainClass ? domainClass.class_id : data[0].class_id
    }
    if (props.initialTagId) {
      selectedTagId.value = props.initialTagId
    }
  } catch (e) {
    console.error('Failed to load tag tree:', e)
  } finally {
    loading.value = false
  }
}

const selectClass = (classId) => {
  selectedClassId.value = classId
  selectedTagId.value = null
  newTagParentId.value = null
}

const selectTagNode = async (node) => {
  selectedTagId.value = node.id
  editTagName.value = node.name
  newAliasName.value = ''
  loadingUnits.value = true
  try {
    const [aliases, units] = await Promise.all([
      fetchTagAliases(node.id),
      fetchTagUnits(node.id, { include_descendants: true, limit: 50 }),
    ])
    tagAliases.value = aliases || []
    tagUnits.value = units || []
  } catch (e) {
    console.error('Failed to load tag inspector data:', e)
  } finally {
    loadingUnits.value = false
  }
}

watch(selectedTag, (newTag) => {
  if (newTag) {
    editTagName.value = newTag.name
  }
})

const togglePresetsPanel = async () => {
  showPresetsPanel.value = !showPresetsPanel.value
  if (showPresetsPanel.value && presetsList.value.length === 0) {
    try {
      presetsList.value = await fetchTaxonomyPresets()
    } catch (e) {
      console.error('Failed to load presets:', e)
    }
  }
}

const isPresetApplied = (preset) => {
  const existingCodes = new Set(tagClasses.value.map(c => c.code))
  return preset.classes.every(c => existingCodes.has(c.code))
}

const handleApplyPreset = async (presetId) => {
  applyingPreset.value = presetId
  try {
    await applyTaxonomyPreset(presetId)
    await loadData()
    await mediaStore.loadLensTree(mediaStore.activeLens)
    playerStore.showToast(t('tax.toastPresetApplied'))
  } catch (e) {
    playerStore.showToast(t('tax.toastPresetFailed') + (e.response?.data?.detail || e.message))
  } finally {
    applyingPreset.value = null
  }
}

const handleCreateClass = async () => {
  if (!newClassForm.value.display_name.trim() || !newClassForm.value.code.trim()) return
  try {
    const created = await createTagClass({
      display_name: newClassForm.value.display_name.trim(),
      code: newClassForm.value.code.trim().toLowerCase(),
      color: newClassForm.value.color,
      is_projectable: newClassForm.value.is_projectable,
      is_required: newClassForm.value.is_required,
    })
    showCreateClassCard.value = false
    newClassForm.value = {
      display_name: '',
      code: '',
      color: '#8b5cf6',
      is_projectable: true,
      is_required: false,
    }
    await loadData()
    selectedClassId.value = created.id
    playerStore.showToast(t('tax.toastClassCreated', { name: tFacet(created.code, created.display_name) }))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastClassCreateFailed'))
  }
}

const handleDeleteClass = async (tc) => {
  const count = getClassTagCount(tc.id)
  const name = tFacet(tc.code, tc.display_name)
  const msg = count > 0
    ? t('tax.confirmDeleteClassWithTags', { name, count })
    : t('tax.confirmDeleteClassEmpty', { name })
  if (!confirm(msg)) return
  try {
    await deleteTagClass(tc.id, count > 0)
    selectedClassId.value = null
    selectedTagId.value = null
    await loadData()
    playerStore.showToast(t('tax.toastClassDeleted', { name }))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastClassDeleteFailed'))
  }
}

const handleToggleRequired = async (tc) => {
  try {
    await updateTagClass(tc.id, { is_required: !tc.is_required })
    await loadData()
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastUpdateFailed'))
  }
}

const handleToggleProjectable = async (tc) => {
  try {
    await updateTagClass(tc.id, { is_projectable: !tc.is_projectable })
    await loadData()
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastUpdateFailed'))
  }
}

const handleCreateTag = async () => {
  if (!newTagName.value.trim() || !selectedClassId.value) return
  try {
    const parentId = newTagParentId.value
    const created = await createTag({
      name: newTagName.value.trim(),
      tag_class_id: selectedClassId.value,
      parent_id: parentId,
    })
    newTagName.value = ''
    if (parentId) {
      expandedTagIds.value.add(parentId)
      collapsedRootIds.value.delete(parentId)
    }
    await loadData()
    if (created && created.id) {
      selectTagNode(created)
    }
    playerStore.showToast(t('tax.toastTagCreated', { name: tData(created.name) }))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastTagCreateFailed'))
  }
}

const handleSaveTagUpdate = async () => {
  if (!selectedTag.value || !editTagName.value.trim() || editTagName.value.trim() === selectedTag.value.name) return
  try {
    const updated = await updateTag(selectedTag.value.id, {
      name: editTagName.value.trim(),
    })
    await loadData()
    if (updated && updated.id) {
      const node = currentClassTags.value.find(t => t.id === updated.id)
      if (node) await selectTagNode(node)
    }
    playerStore.showToast(t('tax.toastTagSaved', { name: tData(updated.name) }))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastSaveFailed'))
  }
}

const handleReparent = async (tagId, newParentId) => {
  try {
    await updateTagParent(tagId, newParentId)
    await loadData()
    playerStore.showToast(t('tax.toastParentUpdated'))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastParentFailed'))
  }
}

const handleMoveTagClass = async (tagId, targetClassId) => {
  if (!targetClassId || targetClassId === selectedClassId.value) return
  try {
    const updated = await updateTag(tagId, { tag_class_id: targetClassId })
    selectedClassId.value = targetClassId
    await loadData()
    if (updated && updated.id) {
      const node = currentClassTags.value.find(t => t.id === updated.id)
      if (node) await selectTagNode(node)
    }
    playerStore.showToast(t('tax.toastClassMoved'))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastClassMoveFailed'))
  }
}

const handleDeleteTag = async (node) => {
  if (!confirm(t('tax.confirmDeleteTag', { name: tData(node.name) }))) return
  try {
    await deleteTagApi(node.id)
    if (selectedTagId.value === node.id) {
      selectedTagId.value = null
    }
    await loadData()
    playerStore.showToast(t('tax.toastTagDeleted', { name: tData(node.name) }))
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastDeleteFailed'))
  }
}

const handleAddAlias = async () => {
  if (!selectedTag.value || !newAliasName.value.trim()) return
  try {
    await addTagAlias(selectedTag.value.id, {
      alias_name: newAliasName.value.trim(),
      language: 'zh',
    })
    newAliasName.value = ''
    tagAliases.value = await fetchTagAliases(selectedTag.value.id)
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastAliasAddFailed'))
  }
}

const handleRemoveAlias = async (aliasId) => {
  if (!selectedTag.value) return
  try {
    await removeTagAlias(aliasId)
    tagAliases.value = await fetchTagAliases(selectedTag.value.id)
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastAliasRemoveFailed'))
  }
}

const handleUnlinkUnitTag = async (unitId, tagId) => {
  try {
    await removeTag(unitId, tagId)
    tagUnits.value = tagUnits.value.filter(u => u.id !== unitId)
    await loadData()
  } catch (e) {
    playerStore.showToast(e.response?.data?.detail || t('tax.toastUnlinkFailed'))
  }
}

const handleReorganizeAll = async () => {
  reorganizing.value = true
  try {
    await reorganizeTags()
    await loadData()
    playerStore.showToast(t('tax.toastReorganized'))
  } catch (e) {
    playerStore.showToast(t('tax.toastReorganizeFailed') + (e.response?.data?.detail || e.message))
  } finally {
    reorganizing.value = false
  }
}

const handleCopyMCPColumnPrompt = async (tc) => {
  if (!tc) return
  const name = tFacet(tc.code, tc.display_name)
  const prompt = t('tax.mcpColumnPrompt', { code: tc.code, name })
  try {
    await navigator.clipboard.writeText(prompt)
    playerStore.showToast(t('tax.toastMcpPromptCopied', { name }))
  } catch (e) {
    mediaStore.openAgentMCP()
  }
}

const handleJumpToAssetsWithTag = (tagNode) => {
  emit('jump-to-tag', {
    classCode: currentClass.value?.code || 'domain',
    tagNode,
  })
}

const handleJumpToMissingFacet = (facetCode) => {
  emit('jump-to-missing', facetCode)
}

onMounted(() => {
  loadData()
})
</script>
