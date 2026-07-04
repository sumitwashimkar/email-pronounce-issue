import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'

const WS_URL = 'ws://localhost:8000/ws'

function WaveformIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <rect x="2" y="9" width="3" height="6" rx="1.5" />
      <rect x="8" y="5" width="3" height="14" rx="1.5" />
      <rect x="14" y="2" width="3" height="20" rx="1.5" />
      <rect x="20" y="7" width="3" height="10" rx="1.5" />
    </svg>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  )
}

function DocumentIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="16" y2="17" />
    </svg>
  )
}

function InfoIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}

function App() {
  const [listening, setListening] = useState(false)
  const [interimText, setInterimText] = useState('')
  const [finalChunks, setFinalChunks] = useState([])
  const [error, setError] = useState('')

  const wsRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const streamRef = useRef(null)
  const mountedRef = useRef(true)
  const reconnectAttemptsRef = useRef(0)

  const openWarmConnection = useCallback(() => {
    const ws = new WebSocket(WS_URL)
    ws.intentionalClose = false
    wsRef.current = ws

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'interim') {
        setInterimText(data.transcript)
      } else if (data.type === 'final') {
        setFinalChunks((prev) => [...prev, data.transcript])
        setInterimText('')
      } else if (data.type === 'error') {
        setError(data.message)
      }
    }

    ws.onerror = () => {
      if (mountedRef.current) setError('Connection to backend failed. Is it running?')
    }

    ws.onclose = () => {
      if (ws.intentionalClose || !mountedRef.current) return
      setListening(false)
      const attempt = reconnectAttemptsRef.current++
      const delay = Math.min(1000 * 2 ** attempt, 15000)
      setTimeout(() => {
        if (mountedRef.current) openWarmConnection()
      }, delay)
    }

    return ws
  }, [])

  useEffect(() => {
    mountedRef.current = true
    const ws = openWarmConnection()
    return () => {
      mountedRef.current = false
      ws.intentionalClose = true
      ws.close()
    }
  }, [openWarmConnection])

  const startListening = async () => {
    setError('')
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      mediaRecorderRef.current = mediaRecorder

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(event.data)
        }
      }

      mediaRecorder.start(250) // send audio chunks every 250ms
      setListening(true)
    } catch (err) {
      setError(`Microphone access failed: ${err.message}`)
    }
  }

  const stopListening = () => {
    mediaRecorderRef.current?.stop()
    streamRef.current?.getTracks().forEach((track) => track.stop())
    if (wsRef.current) {
      wsRef.current.intentionalClose = true
      wsRef.current.close()
    }
    openWarmConnection()

    setListening(false)
    setInterimText('')
  }

  const clearTranscript = () => {
    setFinalChunks([])
    setInterimText('')
  }

  const hasTranscript = finalChunks.length > 0 || !!interimText
  const statusLabel = error ? 'Something went wrong' : listening ? 'Listening...' : 'Ready to listen'

  return (
    <div className="page">
      <div className="bg-glow" />

      <div className="app">
        <span className="badge">
          <WaveformIcon />
          Voice to Text
        </span>

        <h1>
          Voice <span className="gradient-text">Transcript</span> Demo
        </h1>
        <p className="subtitle">Click the mic, talk, and see your clean transcript in real-time.</p>

        <div className="mic-wrap">
          <div className="mic-halo" />
          <button
            type="button"
            className={`mic-button ${listening ? 'listening' : ''}`}
            onClick={listening ? stopListening : startListening}
            aria-label={listening ? 'Stop listening' : 'Start listening'}
          >
            <MicIcon />
          </button>
        </div>

        <div className="status">
          <span className={`status-dot ${listening ? 'listening' : ''} ${error ? 'error' : ''}`} />
          {statusLabel}
        </div>

        {error && <p className="error-text">{error}</p>}

        <div className="transcript-card">
          <div className="transcript-header">
            <DocumentIcon />
            Transcript
          </div>
          <div className="transcript-body">
            {!hasTranscript && (
              <span className="placeholder">Transcript will appear here...</span>
            )}
            {finalChunks.map((chunk, i) => (
              <span key={i} className="final-chunk">{chunk} </span>
            ))}
            {interimText && (
              <span className="interim-chunk">
                {interimText}
                <span className="cursor" />
              </span>
            )}
          </div>
        </div>

        {finalChunks.length > 0 && (
          <button type="button" className="clear-button" onClick={clearTranscript}>
            Clear
          </button>
        )}
      </div>
    </div>
  )
}

export default App
