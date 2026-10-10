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
  fetchMaintenanceStatus
} from '../api'

export const useMediaStore = defineStore('media', {
  state: () => ({
    currentMode: 'stream', // 'stream' | 'workplace'
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
    searchQuery: '',
    loading: false,
    scanModalOpen: false,
    recapModalOpen: false,
    recapData: null,
    aiOrganizerModalOpen: false,
    aiOrganizerTargetFolder: '',
    physicalOrganizerModalOpen: false,
    physicalOrganizerTargetFolder: '',
    maintenanceLocks: [],
    activeFacetFilters: {
      workflow: [],
      domain: [],
      creator: [],
    },
    facetTrayOpen: true,
  }),

  actions: {
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
      this.activeFacetFilters = {
        workflow: [],
        domain: [],
        creator: [],
      }
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
        this.loadSupersets()
      ])
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

    async updateRating(unitId, rating) {
      try {
        const updated = await rateAsset(unitId, rating, null)
        this.patchLocalUnit(unitId, updated)
        logTelemetry(unitId, 'rate', 0)
      } catch (e) {
        console.error('Failed to update rating', e)
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
