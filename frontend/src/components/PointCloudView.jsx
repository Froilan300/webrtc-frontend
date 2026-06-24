import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { ws } from '../services/websocketService'

export function PointCloudView() {
  const mountRef = useRef(null)
  const cloudRef = useRef(null)
  const dataRef  = useRef({ positions: null, colors: null, count: 0 })
  const [status, setStatus] = useState('waiting')
  const [count, setCount]   = useState(0)

  useEffect(() => {
    const mount = mountRef.current
    const W = mount.clientWidth  || 960
    const H = mount.clientHeight || 540

    // ── Escena ──────────────────────────────────────────────────────────────
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x333333)

    const camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 1000)
    // Vista cenital para ver la planta rectangular de la sala (ya auto-alineada)
    camera.position.set(0, 150, 60)
    camera.lookAt(0, 0, 0)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 0, 0)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.maxPolarAngle = Math.PI
    controls.screenSpacePanning = true
    controls.update()

    scene.add(new THREE.AmbientLight(0x555555, 0.5))
    const dirLight = new THREE.DirectionalLight(0xffffff, 1)
    dirLight.position.set(0, 100, 0)
    scene.add(dirLight)
    scene.add(new THREE.AxesHelper(5))

    // ── Animación ───────────────────────────────────────────────────────────
    let animId
    const animate = () => {
      animId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      if (!w || !h) return
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    })
    ro.observe(mount)

    // ── Datos LiDAR — reemplaza la nube cada frame (mapa actual, tiempo real) ──
    const onMsg = (msg) => {
      if (msg.type !== 'LIDAR_DATA') return
      const points  = msg.data?.points  || []
      const scalars = msg.data?.scalars || []
      if (!points.length) return

      setStatus('receiving')

      if (cloudRef.current) {
        scene.remove(cloudRef.current)
        cloudRef.current.geometry.dispose()
        cloudRef.current.material.dispose()
        cloudRef.current = null
      }

      const geometry = new THREE.BufferGeometry()
      const vertices = new Float32Array(points.flat())
      geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3))

      const colors = new Float32Array(scalars.length * 3)
      let maxScalar = 0
      for (let i = 0; i < scalars.length; i++) {
        if (scalars[i] > maxScalar) maxScalar = scalars[i]
      }
      if (maxScalar === 0) maxScalar = 1
      const color = new THREE.Color()
      for (let i = 0; i < scalars.length; i++) {
        color.setHSL(scalars[i] / maxScalar, 1.0, 0.5)
        colors[i * 3]     = color.r
        colors[i * 3 + 1] = color.g
        colors[i * 3 + 2] = color.b
      }
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

      const material = new THREE.PointsMaterial({ size: 0.3, vertexColors: true })
      const cloud = new THREE.Points(geometry, material)
      cloudRef.current = cloud
      scene.add(cloud)

      dataRef.current = { positions: vertices, colors, count: points.length }
      setCount(points.length)
    }

    ws.on(onMsg)

    return () => {
      cancelAnimationFrame(animId)
      ws.off(onMsg)
      ro.disconnect()
      controls.dispose()
      renderer.dispose()
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [])

  // ── Exportar el mapa actual a .ply (abrible en CloudCompare / MeshLab) ────
  const exportMap = () => {
    const { positions: pos, colors: col, count: n } = dataRef.current
    if (!n || !pos) return
    const lines = new Array(n)
    for (let i = 0; i < n; i++) {
      const r = Math.round(col[i * 3]     * 255)
      const g = Math.round(col[i * 3 + 1] * 255)
      const b = Math.round(col[i * 3 + 2] * 255)
      lines[i] = `${pos[i * 3].toFixed(3)} ${pos[i * 3 + 1].toFixed(3)} ${pos[i * 3 + 2].toFixed(3)} ${r} ${g} ${b}`
    }
    const header =
      'ply\nformat ascii 1.0\n' +
      `element vertex ${n}\n` +
      'property float x\nproperty float y\nproperty float z\n' +
      'property uchar red\nproperty uchar green\nproperty uchar blue\n' +
      'end_header\n'
    const blob = new Blob([header + lines.join('\n') + '\n'], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `mapa_lidar_${Date.now()}.ply`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full gap-1">
      <div className="relative w-full aspect-video">
        <div
          ref={mountRef}
          className="rounded-lg border border-gray-700 w-full h-full overflow-hidden"
        />

        <div className="absolute top-2 left-2 flex gap-2">
          <button
            onClick={exportMap}
            className="text-xs px-2 py-1 rounded bg-gray-900/80 border border-gray-600 text-gray-200 hover:bg-gray-700 transition-colors"
          >
            Guardar .ply
          </button>
        </div>

        {status === 'waiting' && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="bg-gray-900/80 rounded px-3 py-1 text-xs text-gray-400">
              Esperando datos LiDAR...
            </div>
          </div>
        )}
        {status === 'receiving' && (
          <div className="absolute top-2 right-2 pointer-events-none">
            <div className="bg-green-900/80 rounded px-2 py-0.5 text-xs text-green-300">
              ● {count.toLocaleString()} puntos
            </div>
          </div>
        )}
      </div>
      <p className="text-xs text-gray-500">
        Clic + arrastrar para rotar · Scroll para zoom · Colores por distancia
      </p>
    </div>
  )
}
