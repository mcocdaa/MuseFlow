import { defineStore } from 'pinia'
import { logTelemetry } from '../api'

export const usePlayerStore = defineStore('player', {
  state: () => ({
    // Video reel / player
    videoModalOpen: false,
    activeVideoUnit: null,
    videoQueue: [],
    videoQueueIndex: 0,

    // Image lightbox
    imageModalOpen: false,
    activeImageUnit: null,

    // Audio player bar
    activeAudioUnit: null,
    isPlayingAudio: false,
    audioVolume: 0.8,
    audioLoop: false,
    audioSleepTimerMinutes: 0,
    audioSleepTimeoutId: null,

    // Dwell telemetry tracking
    activeDwellUnitId: null,
    dwellStartTime: null,
  }),

  actions: {
    startDwell(unitId) {
      this.endDwell() // Close previous dwell if any
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

    // Video Reel control
    openVideo(unit, queue = []) {
      this.startDwell(unit.id)
      this.activeVideoUnit = unit
      this.videoQueue = queue.length > 0 ? queue : [unit]
      const idx = this.videoQueue.findIndex(u => u.id === unit.id)
      this.videoQueueIndex = idx !== -1 ? idx : 0
      this.videoModalOpen = true
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

    closeVideo() {
      this.endDwell()
      this.videoModalOpen = false
      this.activeVideoUnit = null
    },

    // Image Lightbox control
    openImage(unit) {
      this.startDwell(unit.id)
      this.activeImageUnit = unit
      this.imageModalOpen = true
    },

    closeImage() {
      this.endDwell()
      this.imageModalOpen = false
      this.activeImageUnit = null
    },

    // Audio Player control
    playAudio(unit) {
      this.startDwell(unit.id)
      this.activeAudioUnit = unit
      this.isPlayingAudio = true
    },

    togglePlayAudio() {
      this.isPlayingAudio = !this.isPlayingAudio
    },

    setSleepTimer(minutes) {
      if (this.audioSleepTimeoutId) {
        clearTimeout(this.audioSleepTimeoutId)
        this.audioSleepTimeoutId = null
      }
      this.audioSleepTimerMinutes = minutes
      if (minutes > 0) {
        this.audioSleepTimeoutId = setTimeout(() => {
          this.isPlayingAudio = false
          this.audioSleepTimerMinutes = 0
          this.audioSleepTimeoutId = null
        }, minutes * 60 * 1000)
      }
    }
  }
})
