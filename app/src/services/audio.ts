/**
 * JARVIS Core — Audio / Speech Recognition Service
 * 
 * Wraps the Web Speech API for live speech-to-text.
 * Abstracted so faster-whisper or other STT can replace it later.
 */

export type TranscriptionCallback = (text: string, isFinal: boolean) => void
export type StatusCallback = (status: 'listening' | 'stopped' | 'error', error?: string) => void

class AudioService {
  private recognition: any = null
  private _isListening = false
  private onTranscription: TranscriptionCallback | null = null
  private onStatus: StatusCallback | null = null

  get isListening(): boolean {
    return this._isListening
  }

  get isSupported(): boolean {
    return !!(
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition
    )
  }

  /** Initialize speech recognition */
  init(onTranscription: TranscriptionCallback, onStatus: StatusCallback): void {
    this.onTranscription = onTranscription
    this.onStatus = onStatus

    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition

    if (!SpeechRecognition) {
      console.error('[Audio] Speech recognition not supported')
      onStatus('error', 'Speech recognition not supported in this browser')
      return
    }

    this.recognition = new SpeechRecognition()
    this.recognition.continuous = true
    this.recognition.interimResults = true
    this.recognition.lang = 'en-US'
    this.recognition.maxAlternatives = 1

    this.recognition.onresult = (event: any) => {
      let interimTranscript = ''
      let finalTranscript = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalTranscript += transcript
        } else {
          interimTranscript += transcript
        }
      }

      if (finalTranscript) {
        this.onTranscription?.(finalTranscript, true)
      } else if (interimTranscript) {
        this.onTranscription?.(interimTranscript, false)
      }
    }

    this.recognition.onerror = (event: any) => {
      console.error('[Audio] Recognition error:', event.error)
      if (event.error === 'not-allowed') {
        this.onStatus?.('error', 'Microphone blocked. Enable microphone permission.')
      } else if (event.error === 'no-speech') {
        // Don't treat no-speech as a fatal error, just keep listening
      } else {
        this.onStatus?.('error', `Speech recognition error: ${event.error}`)
      }
    }

    this.recognition.onend = () => {
      // Auto-restart if we're supposed to be listening
      if (this._isListening) {
        try {
          this.recognition.start()
        } catch (e) {
          this._isListening = false
          this.onStatus?.('stopped')
        }
      } else {
        this.onStatus?.('stopped')
      }
    }
  }

  /** Start listening */
  start(): void {
    if (!this.recognition) {
      this.onStatus?.('error', 'Speech recognition not initialized')
      return
    }

    try {
      this._isListening = true
      this.recognition.start()
      this.onStatus?.('listening')
    } catch (e) {
      // May already be started
      console.warn('[Audio] Start error:', e)
    }
  }

  /** Stop listening */
  stop(): void {
    this._isListening = false
    try {
      this.recognition?.stop()
    } catch (e) {
      // Ignore
    }
    this.onStatus?.('stopped')
  }

  /** Toggle listening */
  toggle(): void {
    if (this._isListening) {
      this.stop()
    } else {
      this.start()
    }
  }
}

// Singleton
export const audioService = new AudioService()
