import React, { useState, useEffect } from 'react'
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition'
import 'regenerator-runtime/runtime'

const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export default function InterviewComponent() {
  const [sessionId, setSessionId] = useState(null)
  const [currentQuestion, setCurrentQuestion] = useState(
    "Hi — I'm Synthia, your interviewer. Tell me a bit about yourself to get started."
  )
  const [lastQuestion, setLastQuestion] = useState(null)
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)

  const { transcript, resetTranscript, browserSupportsSpeechRecognition } = useSpeechRecognition()

  useEffect(() => {
    async function startSession() {
      try {
        const res = await fetch(`${API_URL}/api/start`)
        const data = await res.json()
        setSessionId(data.session_id)
      } catch (err) {
        console.error('Failed to start session', err)
      }
    }

    startSession()
  }, [])

  async function sendTextToAgent(message) {
    if (!sessionId) return
    setIsProcessing(true)
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message }),
      })

      const data = await res.json()
      if (data.question) {
        setLastQuestion(data.question)
        setCurrentQuestion(data.question)
      } else {
        console.warn('Unexpected response from API', data)
      }
    } catch (err) {
      console.error('Error sending text to agent', err)
    } finally {
      setIsProcessing(false)
    }
  }

  function handleRecordClick() {
    if (isRecording) {
      SpeechRecognition.stopListening()
      setIsRecording(false)

      // Send the final transcript to the backend
      if (transcript && transcript.trim().length > 0) {
        // First, try to persist the Q&A pair so we have a log even if the agent tool
        // also runs server-side. This helps keep the frontend in control of saving.
        const qaPayload = {
          question: currentQuestion || lastQuestion || 'user_response',
          answer: transcript.trim(),
          session_id: sessionId,
        }

        ;(async () => {
          try {
            await fetch(`${API_URL}/api/save`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(qaPayload),
            })
          } catch (err) {
            console.warn('Failed to save Q&A to server', err)
          }
        })()

        sendTextToAgent(transcript.trim())
      }
    } else {
      resetTranscript()
      SpeechRecognition.startListening({ continuous: true })
      setIsRecording(true)
    }
  }

  if (!browserSupportsSpeechRecognition) {
    return <div>Your browser does not support Speech Recognition.</div>
  }

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 16 }}>
      <h2>Synthia — AI Interviewer</h2>

      <div style={{ marginBottom: 12, padding: 12, border: '1px solid #ddd', borderRadius: 8 }}>
        <strong>Question:</strong>
        <p>{currentQuestion}</p>
      </div>

      <div style={{ marginBottom: 12 }}>
        <strong>Your answer (live transcript):</strong>
        <p style={{ minHeight: 48, background: '#fafafa', padding: 8, borderRadius: 6 }}>{transcript}</p>
      </div>

      <button onClick={handleRecordClick} disabled={isProcessing || !sessionId} style={{ padding: '8px 16px' }}>
        {isRecording ? 'Stop Recording' : 'Start Recording'}
      </button>

      {isProcessing && <p>Synthia is thinking...</p>}
    </div>
  )
}
