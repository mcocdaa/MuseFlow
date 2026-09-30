import { defineStore } from 'pinia'
import {
  fetchFeed,
  fetchAlgorithms,
  fetchAssets,
  fetchCollections,
  fetchSupersets,
  rateAsset,
  logTelemetry,
  triggerScan
} from '../api'

export const useMediaStore = defineStore('media', {
  state: () => ({
    currentMode: 'stream', // 'stream' | 'workplace'
    activeCategory: 'all', // 'all' | 'image' | 'video' | 'audio'
    selectedAlgorithm: 'discover',
    algorithms: [],
    feedItems: [],
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
  }),

  actions: {
    async init() {
      try {
        const algos = await fetchAlgorithms()
        this.algorithms = algos
      } catch (e) {
        console.error('Failed to fetch algorithms', e)
      }
      await Promise.all([
        this.loadFeed(),
        this.loadCollections(),
        this.loadSupersets()
      ])
    },

    async loadFeed() {
      this.loading = true
      try {
        const params = {
          algorithm: this.selectedAlgorithm,
          limit: 36,
        }
        if (this.activeCategory !== 'all') {
          params.unit_type = this.activeCategory
        }
        if (this.selectedCollectionId) {
          params.collection_id = this.selectedCollectionId
        }
        this.feedItems = await fetchFeed(params)
      } catch (e) {
        console.error('Failed to load feed', e)
      } finally {
        this.loading = false
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
