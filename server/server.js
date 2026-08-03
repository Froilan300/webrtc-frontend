/**
 * Servidor de empresa (version LOCAL).
 *
 * Es la "caja del medio" de la arquitectura: se pone DELANTE del Bridge y:
 *   1. Sirve el frontend ya compilado (frontend/dist).
 *   2. Reenvia /api, /video y /ws al Bridge (reverse proxy).
 *   3. Exige login: sin sesion no se llega ni al panel, ni al video, ni al /ws.
 *
 * El Bridge NO se toca y NO se expone: aqui apunta a localhost:8080 (donde corre
 * hoy). En produccion, ese localhost sera la IP de la Pi por la VPN.
 *
 * El login de aqui es un stand-in para desarrollar. En produccion se sustituye
 * por la puerta de identidad (Cloudflare Access / Authelia) con MFA.
 */
const path = require('path')
const fs = require('fs')
const express = require('express')
const session = require('express-session')
const bcrypt = require('bcryptjs')
const cookie = require('cookie')
const signature = require('cookie-signature')
const { createProxyMiddleware } = require('http-proxy-middleware')

// ─── Configuracion (via env, con valores por defecto para local) ──────────────
const PORT        = process.env.PORT || 3000
const BRIDGE_URL  = process.env.BRIDGE_URL || 'http://localhost:8080'
const SECRET      = process.env.SESSION_SECRET || 'cambia-esto-en-produccion'
const COOKIE_NAME = 'go2.sid'
const FRONTEND    = path.resolve(__dirname, '..', 'frontend', 'dist')
const USERS_FILE  = path.join(__dirname, 'users.json')

// ─── Usuarios: se siembra admin/admin en el primer arranque ───────────────────
if (!fs.existsSync(USERS_FILE)) {
  fs.writeFileSync(USERS_FILE, JSON.stringify({ admin: bcrypt.hashSync('admin', 10) }, null, 2))
  console.warn('  users.json creado con admin/admin  ->  CAMBIALO ya (npm run hash <clave>)')
}
const loadUsers = () => JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'))

// ─── App ──────────────────────────────────────────────────────────────────────
const app = express()
app.set('trust proxy', 1)   // detras de un proxy/tunel en produccion

const store = new session.MemoryStore()
const sessionMiddleware = session({
  name: COOKIE_NAME,
  secret: SECRET,
  store,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 1000 * 60 * 60 * 8 }, // 8 h
})
app.use(sessionMiddleware)
app.use(express.urlencoded({ extended: false }))

// ─── Login ──────────────────────────────────────────────────────────────────
app.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/')
  res.sendFile(path.join(__dirname, 'public', 'login.html'))
})

app.post('/login', (req, res) => {
  const { username, password } = req.body
  const hash = loadUsers()[username]
  if (hash && bcrypt.compareSync(password || '', hash)) {
    req.session.user = username
    console.log(`[AUTH] login OK: ${username} (${req.ip})`)
    return res.redirect('/')
  }
  console.warn(`[AUTH] login FALLIDO: ${username || '(vacio)'} (${req.ip})`)
  res.redirect('/login?error=1')
})

app.post('/logout', (req, res) => req.session.destroy(() => res.redirect('/login')))

// ─── Puerta: todo lo de abajo exige sesion ────────────────────────────────────
function requireAuth(req, res, next) {
  if (req.session && req.session.user) return next()
  // Las llamadas de datos devuelven 401 (el frontend las maneja);
  // la navegacion normal va a la pantalla de login.
  // Usamos originalUrl porque en un middleware montado (/api, /video) req.path
  // viene recortado del prefijo del mount.
  const url = req.originalUrl || req.url
  if (url.startsWith('/api') || url.startsWith('/video')) {
    return res.status(401).json({ error: 'no autenticado' })
  }
  res.redirect('/login')
}

// ─── Reverse proxy al Bridge ──────────────────────────────────────────────────
// Filtro + mount en la RAIZ para conservar la ruta completa. Si montaramos el
// proxy en '/api', Express quitaria ese prefijo y el Bridge recibiria '/status'
// en vez de '/api/status' (y devolveria 404).
const bridgeProxy = createProxyMiddleware({
  target: BRIDGE_URL,
  changeOrigin: true,
  pathFilter: (pathname) => pathname.startsWith('/api') || pathname === '/video',
})
const wsProxy = createProxyMiddleware({ target: BRIDGE_URL, changeOrigin: true, ws: true })

app.use(['/api', '/video'], requireAuth)   // exige sesion en esas rutas
app.use(bridgeProxy)                        // reenvia /api y /video al Bridge intactos
// El /ws (WebSocket) se autoriza en el evento 'upgrade' de mas abajo.

// ─── Frontend compilado (detras del login) ────────────────────────────────────
app.use(requireAuth, express.static(FRONTEND))
app.get('*', requireAuth, (req, res) => res.sendFile(path.join(FRONTEND, 'index.html')))

// ─── Arranque ─────────────────────────────────────────────────────────────────
const server = app.listen(PORT, () => {
  console.log(`Servidor de empresa (local)  ->  http://localhost:${PORT}`)
  console.log(`  frontend:  ${FRONTEND}`)
  console.log(`  proxy   ->  ${BRIDGE_URL}`)
})

// ─── Autorizacion del WebSocket ───────────────────────────────────────────────
// El handshake del WS no pasa por los middleware de Express (es un evento
// 'upgrade' del servidor HTTP), asi que validamos la sesion aqui a mano:
// leemos la cookie firmada, sacamos el id y consultamos el store.
function sessionFromUpgrade(req) {
  return new Promise((resolve) => {
    const raw = cookie.parse(req.headers.cookie || '')[COOKIE_NAME]
    if (!raw || !raw.startsWith('s:')) return resolve(null)
    const sid = signature.unsign(raw.slice(2), SECRET)
    if (!sid) return resolve(null)
    store.get(sid, (err, sess) => resolve(err ? null : sess))
  })
}

server.on('upgrade', async (req, socket, head) => {
  if (!req.url.startsWith('/ws')) return
  const sess = await sessionFromUpgrade(req)
  if (sess && sess.user) {
    wsProxy.upgrade(req, socket, head)
  } else {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n')
    socket.destroy()
  }
})
