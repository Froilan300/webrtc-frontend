/**
 * Experiencia WebXR para Meta Quest 3 — PASO 3: ver la cámara + CONDUCIR.
 *
 * - Ver la CÁMARA del perro (stream MJPEG de /video) en un panel flotante.
 * - Conducir con el STICK DERECHO: arriba/abajo = adelante/atrás, izq/der = girar.
 * - Cualquier GATILLO = parada de emergencia.
 *
 * Se prueba en el PC con la extensión "WebXR API Emulator" (no necesita gafas ni
 * HTTPS sobre localhost). Necesita el Bridge corriendo para el vídeo y el control.
 */
import * as THREE from 'three'
import { VRButton } from 'three/examples/jsm/webxr/VRButton.js'
import { ws } from '../services/websocketService.js'

// ── Escena ────────────────────────────────────────────────────────────────────
const scene = new THREE.Scene()
scene.background = new THREE.Color(0x101014)

const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 100)
camera.position.set(0, 1.6, 0)   // altura de ojos ~1.6 m (fuera de VR)

const renderer = new THREE.WebGLRenderer({ antialias: true })
renderer.setPixelRatio(window.devicePixelRatio)
renderer.setSize(window.innerWidth, window.innerHeight)
renderer.xr.enabled = true       // ← habilita WebXR
document.body.appendChild(renderer.domElement)
document.body.appendChild(VRButton.createButton(renderer))   // botón "Enter VR"

// ── Luz + suelo de referencia ─────────────────────────────────────────────────
scene.add(new THREE.HemisphereLight(0xffffff, 0x303040, 1.0))
scene.add(new THREE.GridHelper(10, 10, 0x334, 0x223))

// ── Panel flotante = pantalla con la CÁMARA del robot ──────────────────────────
const PANEL_W = 1.6                                // ancho fijo (m); el alto se ajusta al vídeo
let   panelH  = 0.9                                // provisional hasta el primer frame
const PANEL_POS = new THREE.Vector3(0, 1.6, -2)   // 2 m al frente, a la altura de los ojos
const FRAME_MARGIN = 0.06

// Indicador de estado (visible en la página 2D del navegador, para depurar en el
// emulador del PC — en VR no se ve, pero el panel ya lo dirá).
const dbg = document.createElement('div')
dbg.style.cssText = 'position:fixed;top:8px;left:8px;z-index:10;font:14px monospace;color:#eab308;background:#000a;padding:6px 10px;border-radius:6px'
dbg.textContent = 'vídeo: cargando /video…'
document.body.appendChild(dbg)

// <img> que recibe el stream MJPEG de /video (MISMO origen: pasa por el proxy de
// Vite / servidor de empresa hasta el Bridge). El navegador lo repinta con cada
// frame; nosotros lo subimos a la GPU como textura. SIN crossOrigin (es del mismo
// origen; ponerlo fuerza CORS y puede romper la carga a través del proxy).
const videoImg = new Image()
videoImg.decoding = 'async'
videoImg.style.cssText = 'position:fixed;left:-9999px;top:0;width:2px;height:2px'  // fuera de pantalla, pero se decodifica
document.body.appendChild(videoImg)

const videoTex = new THREE.Texture(videoImg)
videoTex.colorSpace = THREE.SRGBColorSpace

// Marco azul detrás del panel
const frame = new THREE.Mesh(
  new THREE.PlaneGeometry(1, 1),
  new THREE.MeshBasicMaterial({ color: 0x3b82f6 })
)
frame.position.copy(PANEL_POS).setZ(PANEL_POS.z - 0.01)
frame.scale.set(PANEL_W + FRAME_MARGIN, panelH + FRAME_MARGIN, 1)
scene.add(frame)

// Panel: arranca con un placeholder y cambia al vídeo cuando llega el primer frame
const panelMat = new THREE.MeshBasicMaterial({ map: makePlaceholderTexture('ESPERANDO CAMARA...') })
const panel = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), panelMat)
panel.position.copy(PANEL_POS)
panel.scale.set(PANEL_W, panelH, 1)
scene.add(panel)

// Detección robusta de "vídeo listo": lo intentamos por el evento load, por la
// promesa decode() y también cada frame (naturalWidth). El primero que acierte gana.
let haveVideo = false
function markVideoReady() {
  if (haveVideo || !videoImg.naturalWidth) return
  panelH = PANEL_W * (videoImg.naturalHeight / videoImg.naturalWidth)  // aspecto real
  panel.scale.set(PANEL_W, panelH, 1)
  frame.scale.set(PANEL_W + FRAME_MARGIN, panelH + FRAME_MARGIN, 1)
  panelMat.map = videoTex
  panelMat.needsUpdate = true
  haveVideo = true
  dbg.textContent = `vídeo: OK ${videoImg.naturalWidth}×${videoImg.naturalHeight}`
  dbg.style.color = '#22c55e'
}
videoImg.addEventListener('load', markVideoReady)
videoImg.addEventListener('error', () => {
  dbg.textContent = 'vídeo: ERROR cargando /video — ¿está el Bridge en marcha (:8080)?'
  dbg.style.color = '#f87171'
  panelMat.map = makePlaceholderTexture('SIN VIDEO\n¿Bridge encendido?')
  panelMat.needsUpdate = true
})
videoImg.src = '/video'
if (videoImg.decode) videoImg.decode().then(markVideoReady).catch(() => {})

// ── Mandos (controllers) con rayo verde ───────────────────────────────────────
for (let i = 0; i < 2; i++) {
  const controller = renderer.xr.getController(i)
  const ray = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -1)]),
    new THREE.LineBasicMaterial({ color: 0x22c55e })
  )
  ray.scale.z = 3
  controller.add(ray)
  scene.add(controller)

  // Un cubito para "ver" el mando en el espacio
  const grip = renderer.xr.getControllerGrip(i)
  grip.add(new THREE.Mesh(
    new THREE.BoxGeometry(0.05, 0.05, 0.12),
    new THREE.MeshBasicMaterial({ color: 0x9ca3af })
  ))
  scene.add(grip)
}

// ── Control con los mandos de la Quest ─────────────────────────────────────────
// Reutiliza el mismo protocolo que el teclado (ws.send('MOVE'/'STOP'/...)) y las
// mismas velocidades, para que el perro responda igual que en el panel normal.
const SPEED = 0.7            // adelante/atrás (igual que ControlPad)
const TURN  = 1.7            // giro (igual que ControlPad)
const DEADZONE = 0.15        // zona muerta del stick (evita deriva)
const SEND_INTERVAL = 100    // ms → 10 Hz, como el control manual

ws.connect()

// Indicador de control (visible en la página 2D, para depurar en el emulador)
const ctrlDbg = document.createElement('div')
ctrlDbg.style.cssText = 'position:fixed;top:40px;left:8px;z-index:10;font:14px monospace;color:#93c5fd;background:#000a;padding:6px 10px;border-radius:6px'
ctrlDbg.textContent = 'control: esperando mando…'
document.body.appendChild(ctrlDbg)

let lastSend = 0
let wasMoving = false
let triggerWasPressed = false

const dz = (v) => (Math.abs(v) < DEADZONE ? 0 : v)

// Devuelve [x, y] del stick: en los Touch de la Quest está en axes[2],[3];
// si el mando solo expone 2 ejes, usa [0],[1].
function stick(gp) {
  const a = gp.axes
  return a.length >= 4 ? [a[2] || 0, a[3] || 0] : [a[0] || 0, a[1] || 0]
}

function handleControls(now) {
  const session = renderer.xr.getSession()
  if (!session) return

  let moveX = 0, turnZ = 0, anyTrigger = false, haveRight = false

  for (const src of session.inputSources) {
    const gp = src.gamepad
    if (!gp) continue
    if (gp.buttons[0]?.pressed) anyTrigger = true          // gatillo = parada de emergencia
    if (src.handedness === 'right') {
      haveRight = true
      const [ax, ay] = stick(gp)
      moveX = -dz(ay) * SPEED   // stick arriba (ay<0) = adelante
      turnZ = -dz(ax) * TURN    // stick izquierda (ax<0) = girar a la izquierda
    }
  }

  // Parada de emergencia — solo en el flanco de subida (no repetir mientras se mantiene)
  if (anyTrigger && !triggerWasPressed) {
    ws.send('EMERGENCY_STOP')
    ctrlDbg.textContent = 'control: ⚠ PARADA DE EMERGENCIA'
    ctrlDbg.style.color = '#f87171'
  }
  triggerWasPressed = anyTrigger

  // MOVE a 10 Hz mientras el stick esté movido; STOP una vez al soltarlo
  const moving = moveX !== 0 || turnZ !== 0
  if (now - lastSend >= SEND_INTERVAL) {
    lastSend = now
    if (moving) {
      ws.send('MOVE', { x: +moveX.toFixed(2), y: 0, z: +turnZ.toFixed(2) })
      wasMoving = true
      if (!anyTrigger) {
        ctrlDbg.textContent = `control: MOVE x=${moveX.toFixed(2)} z=${turnZ.toFixed(2)}`
        ctrlDbg.style.color = '#93c5fd'
      }
    } else if (wasMoving) {
      ws.send('STOP')
      wasMoving = false
      if (!anyTrigger) {
        ctrlDbg.textContent = haveRight ? 'control: STOP (stick centrado)' : 'control: sin mando derecho'
        ctrlDbg.style.color = '#93c5fd'
      }
    }
  }
}

// ── Bucle de render (setAnimationLoop es obligatorio para XR) ──────────────────
renderer.setAnimationLoop((time) => {
  markVideoReady()
  if (haveVideo) videoTex.needsUpdate = true   // sube el frame MJPEG más reciente a la GPU
  handleControls(time)
  renderer.render(scene, camera)
})

// ── Redimensionar (fuera de VR, en la ventana del navegador) ───────────────────
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
})

// ── Utilidad: genera una textura de texto para el placeholder ──────────────────
function makePlaceholderTexture(text) {
  const c = document.createElement('canvas')
  c.width = 1024; c.height = 576
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, c.width, c.height)
  ctx.fillStyle = '#6b7280'; ctx.font = 'bold 56px system-ui, sans-serif'
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  text.split('\n').forEach((line, i) => ctx.fillText(line, c.width / 2, c.height / 2 - 30 + i * 70))
  return new THREE.CanvasTexture(c)
}
