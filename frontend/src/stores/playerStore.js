import { defineStore } from 'pinia'
import { logTelemetry, createSupersetFromQueue, fetchAssets } from '../api'

export const usePlayerStore = defineStore('player', {
  state: () => ({
    // -------------------------------------------------------------
    // Toast Notification System
    // -------------------------------------------------------------
    toast: {
      message: '',
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

    // -------------------------------------------------------------
    // 4. Subtitle Interactive Configuration (Draggable + Styling)
    // -------------------------------------------------------------
    subtitleConfig: {
      verticalPercent: 12, // 12% from bottom, draggable between 5% and 80%
      fontSize: 'md', // 'sm' (14px), 'md' (18px), 'lg' (24px), 'xl' (32px)
      style: 'shadow', // 'shadow' | 'glass'
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
      this.startDwell(unit.id)
      this.activeFgUnit = unit
      this.fgQueue = queue.length > 0 ? queue : [unit]
      const idx = this.fgQueue.findIndex((u) => u.id === unit.id)
      this.fgQueueIndex = idx !== -1 ? idx : 0
      this.fgViewerOpen = true
      this.fgAutoPlay = autoPlay

      // Legacy image lightbox fields sync
      this.activeImageUnit = unit
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
    openAudioModal(unit, playlist = [], autoPlay = false) {
      this.startDwell(unit.id)
      this.activeFgAudioUnit = unit
      this.fgAudioPlaylist = playlist.length > 0 ? playlist : [unit]
      const idx = this.fgAudioPlaylist.findIndex((u) => u.id === unit.id)
      this.fgAudioPlaylistIndex = idx !== -1 ? idx : 0
      this.isFgAudioPlaying = autoPlay
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
      this.bgQueueIndex = this.bgQueue.findIndex(u => u.id === this.activeFgAudioUnit.id)
      this.isBgPlaying = this.isFgAudioPlaying
      this.bgViewMode = 'disc'
      this.closeAudioModal()
      this.showToast(`已将「${this.activeFgAudioUnit.title}」移入背景播放`)
    },

    toggleFgAudioDrawer() {
      this.fgAudioDrawerOpen = !this.fgAudioDrawerOpen
    },

    // -------------------------------------------------------------
    // Full-screen Video Player & Picture-in-Picture Handoff
    // -------------------------------------------------------------
    openVideo(unit, queue = [], autoPlay = false) {
      this.startDwell(unit.id)
      this.activeVideoUnit = unit
      this.videoQueue = queue.length > 0 ? queue : [unit]
      const idx = this.videoQueue.findIndex((u) => u.id === unit.id)
      this.videoQueueIndex = idx !== -1 ? idx : 0
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
    showToast(message, durationMs = 2500) {
      if (this.toast.timerId) {
        clearTimeout(this.toast.timerId)
      }
      this.toast.message = message
      this.toast.visible = true
      this.toast.timerId = setTimeout(() => {
        this.toast.visible = false
        this.toast.timerId = null
      }, durationMs)
    },

    // -------------------------------------------------------------
    // Queue Editing & Superset Unification Actions
    // -------------------------------------------------------------
    addToBgQueue(unit) {
      if (!unit) return
      const exists = this.bgQueue.some((u) => u.id === unit.id)
      if (!exists) {
        this.bgQueue.push(unit)
        this.showToast(`已加入播放队列: 「${unit.title}」`)
      } else {
        this.showToast(`「${unit.title}」已在播放队列中`)
      }
      // If nothing was in background, set activeBgUnit peacefully paused
      if (!this.activeBgUnit && this.bgQueue.length > 0) {
        this.activeBgUnit = unit
        this.bgQueueIndex = 0
        this.isBgPlaying = false
        this.bgViewMode = 'disc'
      }
    },

    addMultipleToBgQueue(units) {
      if (!units || !units.length) return
      let addedCount = 0
      units.forEach((u) => {
        if (!this.bgQueue.some((item) => item.id === u.id)) {
          this.bgQueue.push(u)
          addedCount++
        }
      })
      if (!this.activeBgUnit && this.bgQueue.length > 0) {
        this.playAudio(this.bgQueue[0], this.bgQueue, 'disc')
      }
      this.showToast(`已批量添加 ${addedCount} 项至背景播放队列`)
    },

    removeFromBgQueue(index) {
      if (index < 0 || index >= this.bgQueue.length) return
      const isCurrent = index === this.bgQueueIndex
      const removedTitle = this.bgQueue[index]?.title || '项目'
      this.bgQueue.splice(index, 1)

      if (this.bgQueue.length === 0) {
        this.activeBgUnit = null
        this.isBgPlaying = false
        this.bgQueueIndex = 0
        this.showToast(`已从队列移除「${removedTitle}」，队列已清空`)
      } else if (isCurrent) {
        const nextIdx = Math.min(index, this.bgQueue.length - 1)
        this.bgQueueIndex = nextIdx
        this.activeBgUnit = this.bgQueue[nextIdx]
        this.startDwell(this.activeBgUnit.id)
        this.showToast(`已切换至下一首: 「${this.activeBgUnit.title}」`)
      } else if (index < this.bgQueueIndex) {
        this.bgQueueIndex--
        this.showToast(`已从队列移除「${removedTitle}」`)
      } else {
        this.showToast(`已从队列移除「${removedTitle}」`)
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
      this.showToast('背景播放队列已清空，退出播放')
    },

    stopAndExitBgPlayback() {
      this.endDwell()
      this.isBgPlaying = false
      this.activeBgUnit = null
      this.bgViewMode = 'hidden'
      this.showToast('已停止并退出背景播放')
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
        this.showToast('超集名称不能为空')
        throw new Error('超集名称不能为空')
      }
      if (!this.bgQueue.length) {
        this.showToast('播放队列为空，无法另存为超集')
        throw new Error('播放队列为空')
      }

      const res = await createSupersetFromQueue({
        name: name.trim(),
        description: '由播放队列一键另存生成',
        icon: 'list-music',
        unit_ids: this.bgQueue.map((u) => u.id)
      })
      this.showToast(`已将当前队列另存为超集「${name.trim()}」(${res.unit_count}项)`)
      return res
    },

    async loadSuperset(supersetId, target = 'bg', autoPlay = true) {
      try {
        const units = await fetchAssets({ superset_id: supersetId, limit: 200 })
        if (!units || units.length === 0) {
          this.showToast('该超集暂无可播放的资产')
          return
        }

        if (target === 'bg') {
          this.bgQueue = [...units]
          const firstPlayable =
            units.find((u) => u.unit_type === 'audio' || u.unit_type === 'video' || u.unit_type === 'bundle') ||
            units[0]
          this.playAudio(firstPlayable, this.bgQueue, 'mini')
          this.showToast(`已载入超集 (${units.length} 项) 至背景队列`)
        } else {
          // Foreground continuous viewer / slideshow
          this.openImage(units[0], units, autoPlay)
          this.showToast(`已载入超集 (${units.length} 项) 开启全屏连播`)
        }
      } catch (err) {
        console.error('Failed to load superset into queue', err)
        this.showToast('载入超集失败：' + (err.message || '网络异常'))
      }
    },

    addToFgQueue(unit) {
      if (!unit) return
      if (!this.fgQueue.some((u) => u.id === unit.id)) {
        this.fgQueue.push(unit)
        this.showToast(`已加入连播清单: 「${unit.title}」`)
      } else {
        this.showToast(`「${unit.title}」已在连播清单中`)
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
      if (!name || !name.trim()) throw new Error('超集名称不能为空')
      if (!this.fgQueue.length) throw new Error('连播列表为空')

      const res = await createSupersetFromQueue({
        name: name.trim(),
        description: '由连播清单另存生成',
        icon: 'sparkles',
        unit_ids: this.fgQueue.map((u) => u.id)
      })
      this.showToast(`已将连播清单另存为超集「${name.trim()}」(${res.unit_count}项)`)
      return res
    }
  },
})
