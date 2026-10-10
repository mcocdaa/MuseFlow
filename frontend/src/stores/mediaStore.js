import { defineStore } from 'pinia'
import {
  fetchFeed,
  fetchAlgorithms,
  fetchAssets,
  fetchCollections,
  fetchSupersets,
  rateAsset,
  logTelemetry,
  triggerScan,
  fetchAllTagsFlat,
  cooldownAsset,
  fetchLensTree,
  fetchFacetSummary
} from '../api'

export const useMediaStore = defineStore('media', {
  state: () => ({
    currentMode: 'stream', // 'stream' | 'workplace'
    workplaceView: 'assets', // 'assets' (资产列表) | 'taxonomy' (分类与标签中心专页)
    taxonomyInitialClassCode: null,
    taxonomyInitialTagId: null,
    activeCategory: 'all', // 'all' | 'image' | 'video' | 'audio'
    feedDisplayMode: 'series', // 'series' (系列聚合) | 'flat' (单集平铺)
    selectedAlgorithm: 'discover',
    algorithms: [],
    feedItems: [],
    feedOffset: 0,
    hasMoreFeed: true,
    loadingMore: false,
    workplaceItems: [],
    collections: [],
    supersets: [],
    selectedCollectionId: null,
    selectedSupersetId: null,
    activeLens: 'physical', // 'physical' | 'domain' | 'creator' | 'workflow'
    selectedLensTagId: null,
    selectedMissingFacet: null,
    facetSummary: [],
    lensTreeData: null,
    lensTreeLoading: false,
    searchQuery: '',
    loading: false,
    scanModalOpen: false,
    recapModalOpen: false,
    recapData: null,
    aiOrganizerModalOpen: false,
    aiOrganizerTargetFolder: '',
    agentMCPModalOpen: false,
    physicalOrganizerModalOpen: false,
    physicalOrganizerTargetFolder: '',
    maintenanceLocks: [],
    activeFacetFilters: {},
    sidebarOpen: true,
    facetTrayOpen: true,
    allTags: [],
    tagsLoading: false,
  }),

  actions: {
    openTaxonomyWorkspace(classCode = null, tagId = null) {
      this.currentMode = 'workplace'
      this.workplaceView = 'taxonomy'
      this.taxonomyInitialClassCode = classCode
      this.taxonomyInitialTagId = tagId
    },

    toggleFacetFilter(category, val) {
      if (!this.activeFacetFilters[category]) {
        this.activeFacetFilters[category] = []
      }
      const idx = this.activeFacetFilters[category].indexOf(val)
      if (idx > -1) {
        this.activeFacetFilters[category].splice(idx, 1)
      } else {
        this.activeFacetFilters[category].push(val)
      }
    },

    clearFacetFilters() {
      this.activeFacetFilters = {}
    },

    isFacetActive(category, val) {
      return this.activeFacetFilters[category]?.includes(val) || false
    },

    hasAnyActiveFacet() {
      return Object.values(this.activeFacetFilters).some(arr => Array.isArray(arr) && arr.length > 0)
    },

    openAIOrganizer(folderPath = '') {
      this.aiOrganizerTargetFolder = folderPath
      this.aiOrganizerModalOpen = true
    },

    openAgentMCP() {
      this.agentMCPModalOpen = true
    },

    openPhysicalOrganizer(folderPath = '') {
      this.physicalOrganizerTargetFolder = folderPath
      this.physicalOrganizerModalOpen = true
    },

    setFeedDisplayMode(mode) {
      this.feedDisplayMode = mode
      return this.loadFeed()
    },

    async checkMaintenance() {
      try {
        const res = await fetchMaintenanceStatus()
        this.maintenanceLocks = res.active_locks || []
      } catch (e) {
        // ignore
      }
    },

    async init() {
      // 1. 率先快速加载结构化类继承标签树 (<50ms)，让顶层类体系瞬间就绪，无需等待体积庞大的媒体流
      await this.loadTags()

      try {
        const algos = await fetchAlgorithms()
        this.algorithms = algos
      } catch (e) {
        console.error('Failed to fetch algorithms', e)
      }
      this.checkMaintenance()
      setInterval(() => {
        this.checkMaintenance()
      }, 10000)
      await Promise.all([
        this.loadFeed(),
        this.loadCollections(),
        this.loadSupersets(),
        this.loadFacetSummary()
      ])
    },

    async loadTags() {
      this.tagsLoading = true
      try {
        const tags = await fetchAllTagsFlat()
        this.allTags = tags || []
      } catch (e) {
        console.error('Failed to load all tags flat', e)
      } finally {
        this.tagsLoading = false
      }
    },

    async loadFeed() {
      this.loading = true
      this.feedOffset = 0
      this.hasMoreFeed = true
      try {
        const params = {
          mode: this.feedDisplayMode === 'series' ? 'series' : 'unit',
          algorithm: this.selectedAlgorithm,
        }
        // 系列模式下不传 limit，服务端默认全量 100% 返回所有系列（零遗漏！）
        // 分集平铺模式下首屏流式载入 60 轨，支持触底自动加载更多
        if (this.feedDisplayMode === 'flat') {
          params.limit = 60
          params.offset = 0
        }
        if (this.activeCategory !== 'all') {
          params.unit_type = this.activeCategory
        }
        if (this.selectedCollectionId) {
          params.collection_id = this.selectedCollectionId
        }
        if (this.searchQuery && this.searchQuery.trim()) {
          params.search = this.searchQuery.trim()
        }
        this.feedItems = await fetchFeed(params)
        if (this.feedDisplayMode === 'flat' && this.feedItems.length < 60) {
          this.hasMoreFeed = false
        }
      } catch (e) {
        console.error('Failed to load feed', e)
      } finally {
        this.loading = false
      }
    },

    async loadMoreFeed() {
      if (this.loadingMore || !this.hasMoreFeed || this.feedDisplayMode === 'series') return
      this.loadingMore = true
      try {
        this.feedOffset += 60
        const params = {
          mode: 'unit',
          algorithm: this.selectedAlgorithm,
          limit: 60,
          offset: this.feedOffset,
        }
        if (this.activeCategory !== 'all') {
          params.unit_type = this.activeCategory
        }
        if (this.selectedCollectionId) {
          params.collection_id = this.selectedCollectionId
        }
        if (this.searchQuery && this.searchQuery.trim()) {
          params.search = this.searchQuery.trim()
        }
        const moreItems = await fetchFeed(params)
        if (moreItems && moreItems.length > 0) {
          this.feedItems.push(...moreItems)
          if (moreItems.length < 60) {
            this.hasMoreFeed = false
          }
        } else {
          this.hasMoreFeed = false
        }
      } catch (e) {
        console.error('Failed to load more feed items', e)
      } finally {
        this.loadingMore = false
      }
    },

    async loadWorkplaceItems() {
      this.loading = true
      try {
        const params = {
          limit: 100,
        }
        if (this.activeCategory !== 'all') {
          params.unit_type = this.activeCategory
        }
        if (this.selectedCollectionId) {
          params.collection_id = this.selectedCollectionId
        }
        if (this.selectedSupersetId) {
          params.superset_id = this.selectedSupersetId
        }
        if (this.selectedLensTagId) {
          params.tag_id = this.selectedLensTagId
        }
        if (this.selectedMissingFacet) {
          params.missing_facet = this.selectedMissingFacet
        }
        if (this.searchQuery) {
          params.search = this.searchQuery
        }
        this.workplaceItems = await fetchAssets(params)
      } catch (e) {
        console.error('Failed to load workplace items', e)
      } finally {
        this.loading = false
      }
    },

    async loadFacetSummary() {
      try {
        const data = await fetchFacetSummary()
        this.facetSummary = data || []
      } catch (e) {
        console.error('Failed to load facet summary', e)
      }
    },

    async loadLensTree(classCode) {
      this.lensTreeLoading = true
      try {
        const data = await fetchLensTree(classCode)
        this.lensTreeData = data
      } catch (e) {
        console.error('Failed to load lens tree', e)
      } finally {
        this.lensTreeLoading = false
      }
    },

    async switchLens(lensCode) {
      this.activeLens = lensCode
      this.selectedCollectionId = null
      this.selectedSupersetId = null
      this.selectedLensTagId = null
      this.selectedMissingFacet = null
      if (lensCode !== 'physical') {
        await this.loadLensTree(lensCode)
      }
      await this.loadWorkplaceItems()
    },

    async selectLensNode(node) {
      this.selectedCollectionId = null
      this.selectedSupersetId = null
      if (node.is_unassigned) {
        this.selectedLensTagId = null
        this.selectedMissingFacet = node.missing_facet
      } else {
        this.selectedLensTagId = node.id
        this.selectedMissingFacet = null
      }
      await this.loadWorkplaceItems()
    },

    async toggleMissingFacet(facetCode) {
      this.selectedCollectionId = null
      this.selectedSupersetId = null
      this.selectedLensTagId = null
      if (this.selectedMissingFacet === facetCode) {
        this.selectedMissingFacet = null
      } else {
        this.selectedMissingFacet = facetCode
      }
      await this.loadWorkplaceItems()
    },

    clearLensSelection() {
      this.selectedLensTagId = null
      this.selectedMissingFacet = null
      return this.loadWorkplaceItems()
    },

    async loadCollections() {
      try {
        this.collections = await fetchCollections()
      } catch (e) {
        console.error('Failed to load collections', e)
      }
    },

    async loadSupersets() {
      try {
        this.supersets = await fetchSupersets()
      } catch (e) {
        console.error('Failed to load supersets', e)
      }
    },

    async updateRating(unitId, rating, notes = null) {
      try {
        const updated = await rateAsset(unitId, rating, null, notes)
        this.patchLocalUnit(unitId, updated)
        return updated
      } catch (e) {
        console.error('Failed to update rating', e)
      }
    },

    async addToCooldown(unitId, days = 14, reason = '听腻了') {
      try {
        const updated = await cooldownAsset(unitId, days, reason)
        // 从当前流中即时移除或打上已冷却标记
        this.feedItems = this.feedItems.filter(item => {
          if (item.representative_unit_id === unitId || item.id === unitId) return false
          return true
        })
        this.patchLocalUnit(unitId, updated)
      } catch (e) {
        console.error('Failed to add to cooldown', e)
      }
    },

    async toggleFavorite(unitId) {
      const item = this.findLocalUnit(unitId)
      if (!item) return
      const newFav = !item.is_favorite
      try {
        const updated = await rateAsset(unitId, null, newFav)
        this.patchLocalUnit(unitId, updated)
        logTelemetry(unitId, 'favorite', 0)
      } catch (e) {
        console.error('Failed to toggle favorite', e)
      }
    },

    findLocalUnit(unitId) {
      return this.feedItems.find(u => u.id === unitId) || this.workplaceItems.find(u => u.id === unitId)
    },

    patchLocalUnit(unitId, updated) {
      const fIdx = this.feedItems.findIndex(u => u.id === unitId)
      if (fIdx !== -1) {
        this.feedItems[fIdx] = { ...this.feedItems[fIdx], ...updated }
      }
      const wIdx = this.workplaceItems.findIndex(u => u.id === unitId)
      if (wIdx !== -1) {
        this.workplaceItems[wIdx] = { ...this.workplaceItems[wIdx], ...updated }
      }
    },

    async scanFolder(path) {
      this.loading = true
      try {
        const res = await triggerScan(path)
        await Promise.all([this.loadCollections(), this.loadFeed(), this.loadWorkplaceItems()])
        return res
      } finally {
        this.loading = false
      }
    }
  }
})
