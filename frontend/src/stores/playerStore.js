import { watch } from 'vue'
import { defineStore } from 'pinia'
import { logTelemetry, createSupersetFromQueue, fetchAssets } from '../api'
import { useI18nStore } from './i18nStore'

const t = (key, params) => useI18nStore().t(key, params)
const tData = (str) => useI18nStore().tData(str)

function expandCompositeUnit(unit) {
  if (!unit) return { tracks: [], gallery: [] }
  const attrs = unit.dynamic_attributes || {}
  const rawTracks = Array.isArray(attrs.tracks) ? attrs.tracks : []
  const rawGallery = Array.isArray(attrs.gallery) ? attrs.gallery : []
  const fileMap = new Map()
  if (Array.isArray(unit.files)) {
    for (const f of unit.files) {
      if (f && f.id) fileMap.set(f.id, f)
    }
  }

  let tracks = []
  if (rawTracks.length > 0) {
    rawTracks.forEach((t, idx) => {
      if (!t.audio_file_id) return
      const audioFile = fileMap.get(t.audio_file_id) || {
        id: t.audio_file_id,
        file_name: t.title || unit.title,
        role: 'primary',
      }
      const subId = t.subtitle_file_id || t.lyrics_file_id
      const isLyrics = Boolean(!t.subtitle_file_id && t.lyrics_file_id)
      const subFile = subId
        ? fileMap.get(subId) || {
            id: subId,
            file_name: t.title || unit.title,
            role: isLyrics ? 'lyrics' : 'subtitle',
          }
        : null
      const trackFiles = [{ ...audioFile, role: 'primary' }]
      if (subFile) {
        trackFiles.push({ ...subFile, role: subFile.role === 'lyrics' ? 'lyrics' : 'subtitle' })
      }
      tracks.push({
        ...unit,
        track_key: `${unit.id}_track_${idx}_${t.audio_file_id}`,
        title: t.title || audioFile.file_name || unit.title,
        collection_name: unit.title,
        unit_type: t.unit_type || unit.unit_type,
        duration_seconds: t.duration_seconds ?? unit.duration_seconds,
        files: trackFiles,
      })
    })
  }
  if (tracks.length === 0) {
    tracks = [unit]
  }

  const gallery = []
  if (rawGallery.length > 0) {
    rawGallery.forEach((g, idx) => {
      if (!g.file_id) return
      const imgFile = fileMap.get(g.file_id) || {
        id: g.file_id,
        file_name: g.file_name || g.title || unit.title,
        role: 'primary',
      }
      gallery.push({
        id: unit.id,
        file_id: g.file_id,
        track_key: `${unit.id}_img_${idx}_${g.file_id}`,
        title: g.title || imgFile.file_name || unit.title,
        collection_name: unit.title,
        unit_type: 'image',
        files: [{ ...imgFile, role: 'primary' }],
      })
    })
  } else if (Array.isArray(unit.files)) {
    unit.files
      .filter((f) => f.role === 'image' || f.role === 'cover')
      .forEach((imgFile, idx) => {
        gallery.push({
          id: unit.id,
          file_id: imgFile.id,
          track_key: `${unit.id}_img_${idx}_${imgFile.id}`,
          title: imgFile.file_name?.replace(/\.[^.]+$/, '') || unit.title,
          collection_name: unit.title,
          unit_type: 'image',
          files: [{ ...imgFile, role: 'primary' }],
        })
      })
  }

  return { tracks, gallery }
}

export const usePlayerStore = defineStore('player', {
  state: () => ({
    // -------------------------------------------------------------
    // Toast Notification System
    // -------------------------------------------------------------
    toast: {
      message: '',
      key: '',
      params: null,
      visible: false,
      timerId: null,
    },

    // -------------------------------------------------------------
    // 1. Background Track (Audio / Ambient Video Mini PiP / Disc)
    // -------------------------------------------------------------
    activeBgUnit: null,
    bgQueue: [],
    bgQueueIndex: 0,
    isBgPlaying: false,
    bgVolume: 0.8,
    bgPrevVolume: 0.8,
    bgPlayMode: 'order', // 'order' | 'repeat' | 'shuffle'
    bgViewMode: 'hidden', // 'hidden' | 'disc' | 'mini' | 'full'
    miniPos: { x: null, y: null }, // Initialized on mount to bottom-right
    miniSize: { width: 340, height: 210 },
    bgSleepTimerMinutes: 0,
    bgSleepTimeoutId: null,
    queueDrawerOpen: false,

    // -------------------------------------------------------------
    // 2. Foreground Track (Slideshow / Image & Continuous Viewer)
    // -------------------------------------------------------------
    activeFgUnit: null,
    fgQueue: [],
    fgQueueIndex: 0,
    fgViewerOpen: false,
    fgAutoPlay: false,
    fgIntervalSeconds: 15,
    fgTimeRemaining: 15,
    fgPlayMode: 'order', // 'order' | 'repeat' | 'shuffle'
    fgTimerId: null,

    // -------------------------------------------------------------
    // 3. Foreground Audio Modal (Inspection / Series / Album Player)
    // -------------------------------------------------------------
    fgAudioModalOpen: false,
    activeFgAudioUnit: null,
    fgAudioPlaylist: [],
    fgAudioPlaylistIndex: 0,
    isFgAudioPlaying: false,
    fgAudioVolume: 0.85,
    fgAudioPrevVolume: 0.85,
    fgAudioDrawerOpen: false,
    companionGallery: [],
    galleryDrawerOpen: false,

    // -------------------------------------------------------------
    // 4. Subtitle Interactive Configuration (Draggable + Styling)
    // -------------------------------------------------------------
    subtitleConfig: {
      verticalPercent: 18, // 18% from bottom, draggable between 5% and 80%
      fontSize: 'md', // 'sm' (14px), 'md' (18px), 'lg' (24px), 'xl' (32px)
      style: 'glass', // 'shadow' | 'glass'
    },

    // -------------------------------------------------------------
    // 5. Standalone Video Modal (with Series Episode Drawer)
    // -------------------------------------------------------------
    videoModalOpen: false,
    activeVideoUnit: null,
    videoQueue: [],
    videoQueueIndex: 0,
    videoDrawerOpen: false,
    videoVolume: 0.85,
    videoPrevVolume: 0.85,

    // -------------------------------------------------------------
    // 6. Telemetry & Dwell Tracking
    // -------------------------------------------------------------
    activeDwellUnitId: null,
    dwellStartTime: null,
  }),

  getters: {
    // Aliases for audio compatibility
    activeAudioUnit: (state) => state.activeBgUnit,
    isPlayingAudio: (state) => state.isBgPlaying,
    audioVolume: (state) => state.bgVolume,
    audioPlayMode: (state) => state.bgPlayMode,
    audioQueue: (state) => state.bgQueue,
    audioQueueIndex: (state) => state.bgQueueIndex,

    // Aliases for image viewer
    imageModalOpen: (state) => state.fgViewerOpen,
    activeImageUnit: (state) => state.activeFgUnit,
    imageQueue: (state) => state.fgQueue,
    imageQueueIndex: (state) => state.fgQueueIndex,

    currentBgFile: (state) => {
      if (!state.activeBgUnit?.files?.length) return null
      return (
        state.activeBgUnit.files.find((f) => f.role === 'primary' || f.role === 'audio' || f.role === 'video') ||
        state.activeBgUnit.files[0]
      )
    },

    currentFgFile: (state) => {
      if (!state.activeFgUnit?.files?.length) return null
      return (
        state.activeFgUnit.files.find((f) => f.role === 'primary' || f.role === 'video' || f.role === 'image') ||
        state.activeFgUnit.files[0]
      )
    },
  },

  actions: {
    // -------------------------------------------------------------
    // Telemetry
    // -------------------------------------------------------------
    startDwell(unitId) {
      if (!unitId) return
      this.endDwell()
      this.activeDwellUnitId = unitId
      this.dwellStartTime = Date.now()
      logTelemetry(unitId, 'click', 0)
    },

    endDwell() {
      if (this.activeDwellUnitId && this.dwellStartTime) {
        const elapsedSeconds = Math.min((Date.now() - this.dwellStartTime) / 1000, 180.0)
        if (elapsedSeconds > 1) {
          logTelemetry(this.activeDwellUnitId, 'dwell', elapsedSeconds)
        }
      }
      this.activeDwellUnitId = null
      this.dwellStartTime = null
    },

    // -------------------------------------------------------------
    // Background Player Control (Audio / Mini-Video PiP / Vinyl Disc)
    // -------------------------------------------------------------
    playAudio(unit, queue = [], viewMode = 'disc') {
      this.startDwell(unit.id)
      this.activeBgUnit = unit

      if (queue.length > 0) {
        this.bgQueue = queue
        const idx = this.bgQueue.findIndex((u) => u.id === unit.id)
        this.bgQueueIndex = idx !== -1 ? idx : 0
      } else {
        if (!this.bgQueue.some((u) => u.id === unit.id)) {
          this.bgQueue.push(unit)
        }
        this.bgQueueIndex = this.bgQueue.findIndex((u) => u.id === unit.id)
      }

      this.isBgPlaying = true
      // Default to mini floating player or disc widget
      if (this.bgViewMode === 'hidden') {
        this.bgViewMode = viewMode
      }
    },

    togglePlayAudio() {
      this.isBgPlaying = !this.isBgPlaying
    },

    setBgVolume(vol) {
      this.bgVolume = Math.max(0, Math.min(1, parseFloat(vol)))
    },

    toggleBgMute() {
      if (this.bgVolume > 0) {
        this.bgPrevVolume = this.bgVolume
        this.bgVolume = 0
      } else {
        this.bgVolume = this.bgPrevVolume || 0.8
      }
    },

    nextAudio() {
      if (!this.bgQueue.length) return
      if (this.bgPlayMode === 'repeat' && this.activeBgUnit) {
        this.startDwell(this.activeBgUnit.id)
        this.isBgPlaying = true
        return
      }
      if (this.bgPlayMode === 'shuffle' && this.bgQueue.length > 1) {
        let randIdx = Math.floor(Math.random() * this.bgQueue.length)
        if (randIdx === this.bgQueueIndex) {
          randIdx = (randIdx + 1) % this.bgQueue.length
        }
        this.bgQueueIndex = randIdx
      } else {
        this.bgQueueIndex = (this.bgQueueIndex + 1) % this.bgQueue.length
      }
      const nextUnit = this.bgQueue[this.bgQueueIndex]
      this.activeBgUnit = nextUnit
      this.startDwell(nextUnit.id)
      this.isBgPlaying = true
    },

    prevAudio() {
      if (!this.bgQueue.length) return
      this.bgQueueIndex = (this.bgQueueIndex - 1 + this.bgQueue.length) % this.bgQueue.length
      const prevUnit = this.bgQueue[this.bgQueueIndex]
      this.activeBgUnit = prevUnit
      this.startDwell(prevUnit.id)
      this.isBgPlaying = true
    },

    toggleAudioPlayMode() {
      const modes = ['order', 'repeat', 'shuffle']
      const currentIdx = modes.indexOf(this.bgPlayMode)
      this.bgPlayMode = modes[(currentIdx + 1) % modes.length]
    },

    setBgViewMode(mode) {
      this.bgViewMode = mode
    },

    closeBgPlayer() {
      this.endDwell()
      this.isBgPlaying = false
      this.bgViewMode = 'hidden'
      this.activeBgUnit = null
    },

    setSleepTimer(minutes) {
      if (this.bgSleepTimeoutId) {
        clearTimeout(this.bgSleepTimeoutId)
        this.bgSleepTimeoutId = null
      }
      this.bgSleepTimerMinutes = minutes
      if (minutes > 0) {
        this.bgSleepTimeoutId = setTimeout(() => {
          this.isBgPlaying = false
          this.bgSleepTimerMinutes = 0
          this.bgSleepTimeoutId = null
        }, minutes * 60 * 1000)
      }
    },

    // -------------------------------------------------------------
    // Foreground Continuous Viewer / Slideshow (Images & Videos)
    // -------------------------------------------------------------
    openImage(unit, queue = [], autoPlay = false) {
      if (!unit) return
      this.startDwell(unit.id)

      // 1. If unit is already an expanded single gallery page (has file_id), use the provided queue directly
      if (unit.file_id) {
        this.fgQueue = queue.length > 0 ? queue : [unit]
        const idx = this.fgQueue.findIndex((u) => u.file_id === unit.file_id)
        this.fgQueueIndex = idx !== -1 ? idx : 0
        this.activeFgUnit = this.fgQueue[this.fgQueueIndex] || unit
      } else if (unit.dynamic_attributes?.gallery?.length > 1 && queue.length <= 1) {
        // 2. Opening a single multi-page comic / photo album card: expand its pages + any companion video clips
        const { tracks, gallery } = expandCompositeUnit(unit)
        const bonusVideos = Array.isArray(unit.dynamic_attributes?.tracks) && unit.dynamic_attributes.tracks.length > 0
          ? tracks.filter((t) => t.unit_type === 'video' || t.unit_type === 'bundle')
          : []
        const combined = [...gallery, ...bonusVideos]
        this.fgQueue = combined.length > 0 ? combined : [unit]
        this.fgQueueIndex = 0
        this.activeFgUnit = this.fgQueue[0]
      } else {
        // 3. Opening a standalone loose image or a multi-unit series queue
        const sourceList = queue.length > 0 ? queue : [unit]
        const expanded = []
        let targetIdx = 0
        for (const item of sourceList) {
          if (item.id === unit.id && expanded.length > 0 && targetIdx === 0) {
            targetIdx = expanded.length
          }
          if (item.dynamic_attributes?.gallery?.length > 1) {
            const { tracks, gallery } = expandCompositeUnit(item)
            const bonusVideos = Array.isArray(item.dynamic_attributes?.tracks) && item.dynamic_attributes.tracks.length > 0
              ? tracks.filter((t) => t.unit_type === 'video' || t.unit_type === 'bundle')
              : []
            expanded.push(...gallery, ...bonusVideos)
          } else {
            expanded.push(item)
          }
        }
        this.fgQueue = expanded.length > 0 ? expanded : [unit]
        if (targetIdx === 0 && unit.id) {
          const foundIdx = this.fgQueue.findIndex((u) => u.id === unit.id)
          if (foundIdx !== -1) targetIdx = foundIdx
        }
        this.fgQueueIndex = targetIdx
        this.activeFgUnit = this.fgQueue[this.fgQueueIndex] || unit
      }

      this.fgViewerOpen = true
      this.fgAutoPlay = autoPlay

      // Legacy image lightbox fields sync
      this.activeImageUnit = this.activeFgUnit
      this.imageQueue = this.fgQueue
      this.imageQueueIndex = this.fgQueueIndex

      this.resetFgTimer()
    },

    closeImage() {
      this.stopFgTimer()
      this.endDwell()
      this.fgViewerOpen = false
      this.activeFgUnit = null
      this.activeImageUnit = null
    },

    nextImage() {
      this.nextFg()
    },

    prevImage() {
      this.prevFg()
    },

    nextFg() {
      if (!this.fgQueue.length) return
      if (this.fgPlayMode === 'shuffle' && this.fgQueue.length > 1) {
        let randIdx = Math.floor(Math.random() * this.fgQueue.length)
        if (randIdx === this.fgQueueIndex) randIdx = (randIdx + 1) % this.fgQueue.length
        this.fgQueueIndex = randIdx
      } else {
        this.fgQueueIndex = (this.fgQueueIndex + 1) % this.fgQueue.length
      }

      const nextUnit = this.fgQueue[this.fgQueueIndex]
      this.activeFgUnit = nextUnit
      this.activeImageUnit = nextUnit
      this.startDwell(nextUnit.id)
      this.resetFgTimer()
    },

    prevFg() {
      if (!this.fgQueue.length) return
      this.fgQueueIndex = (this.fgQueueIndex - 1 + this.fgQueue.length) % this.fgQueue.length
      const prevUnit = this.fgQueue[this.fgQueueIndex]
      this.activeFgUnit = prevUnit
      this.activeImageUnit = prevUnit
      this.startDwell(prevUnit.id)
      this.resetFgTimer()
    },

    toggleFgAutoPlay() {
      this.fgAutoPlay = !this.fgAutoPlay
      if (this.fgAutoPlay) {
        this.resetFgTimer()
      } else {
        this.stopFgTimer()
      }
    },

    setFgInterval(seconds) {
      this.fgIntervalSeconds = seconds
      if (this.fgAutoPlay) {
        this.resetFgTimer()
      }
    },

    toggleFgPlayMode() {
      const modes = ['order', 'shuffle', 'repeat']
      const idx = modes.indexOf(this.fgPlayMode)
      this.fgPlayMode = modes[(idx + 1) % modes.length]
    },

    resetFgTimer() {
      this.stopFgTimer()
      if (!this.fgAutoPlay || !this.fgViewerOpen) return

      // If current unit is video, let the video's @ended event trigger nextFg() instead
      if (this.activeFgUnit?.unit_type === 'video' || this.activeFgUnit?.unit_type === 'bundle') {
        this.fgTimeRemaining = 0
        return
      }

      this.fgTimeRemaining = this.fgIntervalSeconds
      this.fgTimerId = setInterval(() => {
        if (this.fgTimeRemaining > 1) {
          this.fgTimeRemaining--
        } else {
          this.nextFg()
        }
      }, 1000)
    },

    stopFgTimer() {
      if (this.fgTimerId) {
        clearInterval(this.fgTimerId)
        this.fgTimerId = null
      }
    },

    // -------------------------------------------------------------
    // Foreground Audio Modal (Inspection / Series / Album Player)
    // -------------------------------------------------------------
    openAudioModal(unit, playlist = [], autoPlay = false, companionGallery = []) {
      this.startDwell(unit.id)
      const sourceList = playlist.length > 0 ? playlist : [unit]
      const expandedTracks = []
      const expandedGallery = [...(companionGallery || [])]
      for (const item of sourceList) {
        const { tracks, gallery } = expandCompositeUnit(item)
        expandedTracks.push(...tracks)
        if (item.id === unit.id && (!companionGallery || companionGallery.length === 0)) {
          expandedGallery.push(...gallery)
        }
      }
      this.fgAudioPlaylist = expandedTracks.length > 0 ? expandedTracks : [unit]
      const idx = this.fgAudioPlaylist.findIndex((u) =>
        unit.track_key && u.track_key ? u.track_key === unit.track_key : u.id === unit.id
      )
      this.fgAudioPlaylistIndex = idx !== -1 ? idx : 0
      this.activeFgAudioUnit = this.fgAudioPlaylist[this.fgAudioPlaylistIndex] || unit
      this.isFgAudioPlaying = autoPlay
      this.companionGallery = expandedGallery
      this.galleryDrawerOpen = false
      this.fgAudioModalOpen = true
      this.fgAudioDrawerOpen = false
    },

    closeAudioModal() {
      this.endDwell()
      this.fgAudioModalOpen = false
      this.isFgAudioPlaying = false
      this.activeFgAudioUnit = null
    },

    togglePlayFgAudio() {
      this.isFgAudioPlaying = !this.isFgAudioPlaying
    },

    setFgAudioVolume(vol) {
      this.fgAudioVolume = Math.max(0, Math.min(1, parseFloat(vol)))
    },

    toggleFgAudioMute() {
      if (this.fgAudioVolume > 0) {
        this.fgAudioPrevVolume = this.fgAudioVolume
        this.fgAudioVolume = 0
      } else {
        this.fgAudioVolume = this.fgAudioPrevVolume || 0.85
      }
    },

    nextFgAudio() {
      if (!this.fgAudioPlaylist.length) return
      this.fgAudioPlaylistIndex = (this.fgAudioPlaylistIndex + 1) % this.fgAudioPlaylist.length
      const nextUnit = this.fgAudioPlaylist[this.fgAudioPlaylistIndex]
      this.activeFgAudioUnit = nextUnit
      this.startDwell(nextUnit.id)
      this.isFgAudioPlaying = true
    },

    prevFgAudio() {
      if (!this.fgAudioPlaylist.length) return
      this.fgAudioPlaylistIndex = (this.fgAudioPlaylistIndex - 1 + this.fgAudioPlaylist.length) % this.fgAudioPlaylist.length
      const prevUnit = this.fgAudioPlaylist[this.fgAudioPlaylistIndex]
      this.activeFgAudioUnit = prevUnit
      this.startDwell(prevUnit.id)
      this.isFgAudioPlaying = true
    },

    selectFgAudioIndex(idx, autoPlay = true) {
      if (idx < 0 || idx >= this.fgAudioPlaylist.length) return
      this.fgAudioPlaylistIndex = idx
      this.activeFgAudioUnit = this.fgAudioPlaylist[idx]
      this.startDwell(this.activeFgAudioUnit.id)
      this.isFgAudioPlaying = autoPlay
    },

    transferFgAudioToBg() {
      if (!this.activeFgAudioUnit) return
      this.addMultipleToBgQueue(this.fgAudioPlaylist)
      this.activeBgUnit = this.activeFgAudioUnit
      this.bgQueueIndex = this.bgQueue.findIndex(u =>
        this.activeFgAudioUnit.track_key && u.track_key
          ? u.track_key === this.activeFgAudioUnit.track_key
          : u.id === this.activeFgAudioUnit.id
      )
      if (this.bgQueueIndex === -1) this.bgQueueIndex = 0
      this.isBgPlaying = this.isFgAudioPlaying
      this.bgViewMode = 'disc'
      this.closeAudioModal()
      this.showI18nToast('playerStore.toastMovedToBg', { title: tData(this.activeBgUnit.title) })
    },

    toggleFgAudioDrawer() {
      this.fgAudioDrawerOpen = !this.fgAudioDrawerOpen
    },

    // -------------------------------------------------------------
    // Full-screen Video Player & Picture-in-Picture Handoff
    // -------------------------------------------------------------
    openVideo(unit, queue = [], autoPlay = false) {
      this.startDwell(unit.id)
      const sourceList = queue.length > 0 ? queue : [unit]
      const expandedTracks = []
      for (const item of sourceList) {
        const { tracks } = expandCompositeUnit(item)
        expandedTracks.push(...tracks)
      }
      this.videoQueue = expandedTracks.length > 0 ? expandedTracks : [unit]
      const idx = this.videoQueue.findIndex((u) =>
        unit.track_key && u.track_key ? u.track_key === unit.track_key : u.id === unit.id
      )
      this.videoQueueIndex = idx !== -1 ? idx : 0
      this.activeVideoUnit = this.videoQueue[this.videoQueueIndex] || unit
      this.videoModalOpen = true
      this.videoDrawerOpen = false
    },

    closeVideo() {
      this.endDwell()
      this.videoModalOpen = false
      this.activeVideoUnit = null
    },

    selectVideoIndex(idx) {
      if (idx < 0 || idx >= this.videoQueue.length) return
      this.videoQueueIndex = idx
      this.activeVideoUnit = this.videoQueue[idx]
      this.startDwell(this.activeVideoUnit.id)
    },

    toggleVideoDrawer() {
      this.videoDrawerOpen = !this.videoDrawerOpen
    },

    minimizeVideoToPiP() {
      if (!this.activeVideoUnit) return
      // Transfer active video into background PiP player
      this.activeBgUnit = this.activeVideoUnit
      this.bgQueue = this.videoQueue.length > 0 ? this.videoQueue : [this.activeVideoUnit]
      this.bgQueueIndex = this.videoQueueIndex
      this.isBgPlaying = true
      this.bgViewMode = 'mini' // Floating window
      this.videoModalOpen = false
      this.activeVideoUnit = null
    },

    nextVideo() {
      if (this.videoQueueIndex < this.videoQueue.length - 1) {
        this.videoQueueIndex++
        const nextUnit = this.videoQueue[this.videoQueueIndex]
        this.startDwell(nextUnit.id)
        this.activeVideoUnit = nextUnit
      }
    },

    prevVideo() {
      if (this.videoQueueIndex > 0) {
        this.videoQueueIndex--
        const prevUnit = this.videoQueue[this.videoQueueIndex]
        this.startDwell(prevUnit.id)
        this.activeVideoUnit = prevUnit
      }
    },

    setVideoVolume(vol) {
      this.videoVolume = Math.max(0, Math.min(1, parseFloat(vol)))
    },

    toggleVideoMute() {
      if (this.videoVolume > 0) {
        this.videoPrevVolume = this.videoVolume
        this.videoVolume = 0
      } else {
        this.videoVolume = this.videoPrevVolume || 0.85
      }
    },

    // -------------------------------------------------------------
    // Subtitle Customization
    // -------------------------------------------------------------
    setSubtitleVerticalPercent(pct) {
      this.subtitleConfig.verticalPercent = Math.max(5, Math.min(85, pct))
    },

    setSubtitleFontSize(size) {
      this.subtitleConfig.fontSize = size
    },

    setSubtitleStyle(style) {
      this.subtitleConfig.style = style
    },

    // -------------------------------------------------------------
    // Toast Notification Feedback
    // -------------------------------------------------------------
    showToast(message, durationMs = 2500, i18nKey = '', i18nParams = null) {
      if (this.toast.timerId) {
        clearTimeout(this.toast.timerId)
      }
      this.toast.key = i18nKey
      this.toast.params = i18nParams
      this.toast.message = message
      this.toast.visible = true
      if (!this._toastLocaleWatcherBound) {
        this._toastLocaleWatcherBound = true
        const i18nStore = useI18nStore()
        watch(i18nStore.locale, () => {
          if (this.toast.visible && this.toast.key) {
            const resolvedParams = {}
            if (this.toast.params) {
              for (const [k, v] of Object.entries(this.toast.params)) {
                resolvedParams[k] = k === 'title' ? tData(v) : v
              }
            }
            this.toast.message = t(this.toast.key, resolvedParams)
          }
        })
      }
      this.toast.timerId = setTimeout(() => {
        this.toast.visible = false
        this.toast.timerId = null
      }, durationMs)
    },

    showI18nToast(key, params = {}, durationMs = 2500) {
      const resolvedParams = {}
      for (const [k, v] of Object.entries(params)) {
        resolvedParams[k] = k === 'title' ? tData(v) : v
      }
      this.showToast(t(key, resolvedParams), durationMs, key, params)
    },

    // -------------------------------------------------------------
    // Queue Editing & Superset Unification Actions
    // -------------------------------------------------------------
    addToBgQueue(unit) {
      if (!unit) return
      const { tracks } = expandCompositeUnit(unit)
      let addedCount = 0
      for (const tItem of tracks) {
        const key = tItem.track_key || tItem.id
        const exists = this.bgQueue.some((u) => (u.track_key || u.id) === key)
        if (!exists) {
          this.bgQueue.push(tItem)
          addedCount++
        }
      }
      if (addedCount > 0) {
        if (tracks.length > 1) {
          this.showI18nToast('playerStore.toastAddedTracksToQueue', { title: unit.title, count: addedCount })
        } else {
          this.showI18nToast('playerStore.toastAddedUnitToQueue', { title: unit.title })
        }
      } else {
        this.showI18nToast('playerStore.toastAlreadyInQueue', { title: unit.title })
      }
      // If nothing was in background, set activeBgUnit peacefully paused
      if (!this.activeBgUnit && this.bgQueue.length > 0) {
        this.activeBgUnit = this.bgQueue[0]
        this.bgQueueIndex = 0
        this.isBgPlaying = false
        this.bgViewMode = 'disc'
      }
    },

    addMultipleToBgQueue(units) {
      if (!units || !units.length) return
      let addedCount = 0
      units.forEach((u) => {
        const { tracks } = expandCompositeUnit(u)
        tracks.forEach((tItem) => {
          const key = tItem.track_key || tItem.id
          if (!this.bgQueue.some((item) => (item.track_key || item.id) === key)) {
            this.bgQueue.push(tItem)
            addedCount++
          }
        })
      })
      if (!this.activeBgUnit && this.bgQueue.length > 0) {
        this.playAudio(this.bgQueue[0], this.bgQueue, 'disc')
      }
      this.showI18nToast('playerStore.toastBatchAddedToQueue', { count: addedCount })
    },

    removeFromBgQueue(index) {
      if (index < 0 || index >= this.bgQueue.length) return
      const isCurrent = index === this.bgQueueIndex
      const removedTitle = this.bgQueue[index]?.title || t('playerStore.defaultItemTitle')
      this.bgQueue.splice(index, 1)

      if (this.bgQueue.length === 0) {
        this.activeBgUnit = null
        this.isBgPlaying = false
        this.bgQueueIndex = 0
        this.showI18nToast('playerStore.toastRemovedAndCleared', { title: removedTitle })
      } else if (isCurrent) {
        const nextIdx = Math.min(index, this.bgQueue.length - 1)
        this.bgQueueIndex = nextIdx
        this.activeBgUnit = this.bgQueue[nextIdx]
        this.startDwell(this.activeBgUnit.id)
        this.showI18nToast('playerStore.toastSwitchedNext', { title: this.activeBgUnit.title })
      } else if (index < this.bgQueueIndex) {
        this.bgQueueIndex--
        this.showI18nToast('playerStore.toastRemovedFromQueue', { title: removedTitle })
      } else {
        this.showI18nToast('playerStore.toastRemovedFromQueue', { title: removedTitle })
      }
    },

    moveBgQueueItem(fromIndex, toIndex) {
      if (
        fromIndex < 0 ||
        fromIndex >= this.bgQueue.length ||
        toIndex < 0 ||
        toIndex >= this.bgQueue.length ||
        fromIndex === toIndex
      ) {
        return
      }
      const currentActiveId = this.activeBgUnit?.id
      const [moved] = this.bgQueue.splice(fromIndex, 1)
      this.bgQueue.splice(toIndex, 0, moved)

      if (currentActiveId) {
        const newIdx = this.bgQueue.findIndex((u) => u.id === currentActiveId)
        if (newIdx !== -1) {
          this.bgQueueIndex = newIdx
        }
      }
    },

    clearBgQueue() {
      this.endDwell()
      this.bgQueue = []
      this.bgQueueIndex = 0
      this.activeBgUnit = null
      this.isBgPlaying = false
      this.bgViewMode = 'hidden'
      this.showI18nToast('playerStore.toastQueueClearedExit')
    },

    stopAndExitBgPlayback() {
      this.endDwell()
      this.isBgPlaying = false
      this.activeBgUnit = null
      this.bgViewMode = 'hidden'
      this.showI18nToast('playerStore.toastStoppedBg')
    },

    toggleQueueDrawer() {
      this.queueDrawerOpen = !this.queueDrawerOpen
    },

    openQueueDrawer() {
      this.queueDrawerOpen = true
    },

    closeQueueDrawer() {
      this.queueDrawerOpen = false
    },

    async saveBgQueueAsSuperset(name) {
      if (!name || !name.trim()) {
        this.showI18nToast('playerStore.errEmptySupersetName')
        throw new Error(t('playerStore.errEmptySupersetName'))
      }
      if (!this.bgQueue.length) {
        this.showI18nToast('playerStore.errEmptyQueueSave')
        throw new Error(t('playerStore.errQueueEmpty'))
      }

      const res = await createSupersetFromQueue({
        name: name.trim(),
        description: t('playerStore.bgQueueSupersetDesc'),
        icon: 'list-music',
        unit_ids: this.bgQueue.map((u) => u.id)
      })
      this.showI18nToast('playerStore.toastSavedBgSuperset', { name: name.trim(), count: res.unit_count })
      return res
    },

    async loadSuperset(supersetId, target = 'bg', autoPlay = true) {
      try {
        const units = await fetchAssets({ superset_id: supersetId, limit: 200 })
        if (!units || units.length === 0) {
          this.showI18nToast('playerStore.toastSupersetEmpty')
          return
        }

        if (target === 'bg') {
          this.bgQueue = [...units]
          const firstPlayable =
            units.find((u) => u.unit_type === 'audio' || u.unit_type === 'video' || u.unit_type === 'bundle') ||
            units[0]
          this.playAudio(firstPlayable, this.bgQueue, 'mini')
          this.showI18nToast('playerStore.toastLoadedSupersetBg', { count: units.length })
        } else {
          // Foreground continuous viewer / slideshow
          this.openImage(units[0], units, autoPlay)
          this.showI18nToast('playerStore.toastLoadedSupersetFg', { count: units.length })
        }
      } catch (err) {
        console.error('Failed to load superset into queue', err)
        this.showI18nToast('playerStore.toastLoadSupersetFailed', {
          msg: err.message || t('playerStore.errNetwork')
        })
      }
    },

    addToFgQueue(unit) {
      if (!unit) return
      if (!this.fgQueue.some((u) => u.id === unit.id)) {
        this.fgQueue.push(unit)
        this.showI18nToast('playerStore.toastAddedToFgQueue', { title: unit.title })
      } else {
        this.showI18nToast('playerStore.toastAlreadyInFgQueue', { title: unit.title })
      }
    },

    removeFromFgQueue(index) {
      if (index < 0 || index >= this.fgQueue.length) return
      const isCurrent = index === this.fgQueueIndex
      this.fgQueue.splice(index, 1)

      if (this.fgQueue.length === 0) {
        this.closeImage()
      } else if (isCurrent) {
        const nextIdx = Math.min(index, this.fgQueue.length - 1)
        this.fgQueueIndex = nextIdx
        this.activeFgUnit = this.fgQueue[nextIdx]
        this.activeImageUnit = this.activeFgUnit
      } else if (index < this.fgQueueIndex) {
        this.fgQueueIndex--
      }
    },

    async saveFgQueueAsSuperset(name) {
      if (!name || !name.trim()) throw new Error(t('playerStore.errEmptySupersetName'))
      if (!this.fgQueue.length) throw new Error(t('playerStore.errFgQueueEmpty'))

      const res = await createSupersetFromQueue({
        name: name.trim(),
        description: t('playerStore.fgQueueSupersetDesc'),
        icon: 'sparkles',
        unit_ids: this.fgQueue.map((u) => u.id)
      })
      this.showI18nToast('playerStore.toastSavedFgSuperset', { name: name.trim(), count: res.unit_count })
      return res
    }
  },
})
