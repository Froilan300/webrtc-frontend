/**
 * CameraView — vídeo en vivo de la cámara del robot.
 * Muestra el stream MJPEG (`/video`), botones circulares de foto y vídeo (que
 * descargan el archivo automáticamente) y pantalla completa SOLO de la cámara
 * (expansión CSS + API nativa del navegador).
 */
import { useEffect, useRef, useState } from 'react'
import { useRobotStore } from '../stores/useRobotStore'

// Muestra un icono de /public; si la imagen no carga, cae a un emoji de reserva
function Icon({ src, fallback }) {
  const [err, setErr] = useState(false)
  if (err) return <span className="text-base leading-none">{fallback}</span>
  return <img src={src} alt="" className="h-5 w-5 object-contain" onError={() => setErr(true)} />
}

export function CameraView() {
  const isConnected = useRobotStore(s => s.isConnected)
  const [recording, setRecording] = useState(false)
  const [busy, setBusy] = useState(false)
  const [fsErr, setFsErr] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const camRef = useRef(null)

  const download = async (filename) => {
    if (!filename) return
    // Descargamos el archivo como blob y forzamos la descarga automática a "Descargas"
    try {
      const res  = await fetch(`/api/media/${filename}`)
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Descarga:', e)
    }
  }

  // Hace una foto en el backend y la descarga automáticamente
  const takePhoto = async () => {
    setBusy(true)
    try {
      const res = await fetch('/api/photo', { method: 'POST' })
      const { filename } = await res.json()
      download(filename)
    } catch (e) {
      console.error('Foto:', e)
    } finally {
      setBusy(false)
    }
  }

  // Empieza a grabar o para y descarga el vídeo resultante
  const toggleRecording = async () => {
    setBusy(true)
    try {
      if (!recording) {
        await fetch('/api/video/start', { method: 'POST' })
        setRecording(true)
      } else {
        const res = await fetch('/api/video/stop', { method: 'POST' })
        const { filename } = await res.json()
        setRecording(false)
        download(filename)
      }
    } catch (e) {
      console.error('Vídeo:', e)
    } finally {
      setBusy(false)
    }
  }

  // Pantalla completa SOLO de la cámara. Expandimos con CSS (funciona siempre) y
  // ADEMÁS intentamos la pantalla completa real del navegador (si está permitida).
  const toggleFullscreen = () => {
    const willExpand = !expanded
    setExpanded(willExpand)
    try {
      if (willExpand) {
        camRef.current?.requestFullscreen?.().catch(() => {})
      } else if (document.fullscreenElement) {
        document.exitFullscreen?.().catch(() => {})
      }
    } catch { /* ignorar */ }
  }

  // Si el usuario sale de la pantalla completa real (Esc), sincroniza el estado
  useEffect(() => {
    const onFs = () => { if (!document.fullscreenElement) setExpanded(false) }
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  // Salir del modo expandido con Esc (cuando no hay pantalla completa nativa)
  useEffect(() => {
    if (!expanded) return
    const onKey = (e) => { if (e.key === 'Escape') setExpanded(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  return (
    <div
      ref={camRef}
      className={
        expanded
          ? 'fixed inset-0 z-[60] bg-black'
          : 'relative bg-black rounded-lg overflow-hidden'
      }
      style={expanded ? undefined : { aspectRatio: '16/9' }}
    >
      {isConnected ? (
        <img
          src="/video"
          alt="Cámara robot"
          className="w-full h-full object-contain"
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm font-mono">
          Sin señal — robot desconectado
        </div>
      )}

      <div className={`absolute top-2 left-2 text-xs font-bold px-2 py-0.5 rounded
        ${isConnected ? 'bg-red-500 text-white' : 'bg-gray-700 text-gray-400'}`}>
        {isConnected ? '● LIVE' : '○ OFF'}
      </div>

      {recording && (
        <div className="absolute top-2 right-2 text-xs font-bold px-2 py-0.5 rounded bg-red-600 text-white animate-pulse">
          ● REC
        </div>
      )}

      {isConnected && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex flex-col gap-3">
          {/* Foto (arriba) */}
          <button
            onClick={takePhoto}
            disabled={busy}
            className="w-12 h-12 rounded-full flex items-center justify-center bg-black/90 text-gray-900 shadow-lg disabled:opacity-50 transition-transform hover:scale-110"
            title="Hacer foto y descargar"
          >
            <Icon src="/icono-foto.png" fallback="📷" />
          </button>
          {/* Vídeo (debajo) */}
          <button
            onClick={toggleRecording}
            disabled={busy}
            className={`w-12 h-12 rounded-full flex items-center justify-center shadow-lg disabled:opacity-50 transition-transform hover:scale-110 ${
              recording
                ? 'bg-red-600 text-white animate-pulse'
                : 'bg-black/90 text-gray-900'
            }`}
            title={recording ? 'Parar y descargar vídeo' : 'Empezar a grabar'}
          >
            <Icon src="/icono-video.png" fallback={recording ? '⏹' : '⏺'} />
          </button>
        </div>
      )}

      {/* Pantalla completa — abajo a la derecha de la cámara */}
      {isConnected && (
        <button
          onClick={toggleFullscreen}
          className="absolute bottom-3 right-3 w-11 h-11 rounded-full flex items-center justify-center bg-black/90 text-gray-900 shadow-lg transition-transform hover:scale-110"
          title={expanded ? 'Salir de pantalla completa' : 'Pantalla completa de la cámara'}
        >
          {fsErr
            ? <span className="text-lg leading-none">{expanded ? '✕' : '⛶'}</span>
            : <img
                src="/pantalla-completa.png"
                alt=""
                className="h-5 w-5 object-contain"
                onError={() => setFsErr(true)}
              />}
        </button>
      )}
    </div>
  )
}
