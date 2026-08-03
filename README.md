# Control Unitree Go2

Panel de teleoperación para el robot cuadrúpedo Unitree Go2: conducción, cámara,
audio, LiDAR y patrullas por waypoints, desde el navegador.

## Arquitectura

Tres piezas independientes:

```
  Navegador ──HTTP/WS──▶ Servidor empresa (:3000) ──proxy──▶ Bridge (:8080) ──WebRTC──▶ Go2 🐕
   (operador)             login + sirve frontend               conexión al robot
```

- **Bridge** (`Bridge/`, Python/FastAPI) — habla con el robot por WebRTC y lo expone
  como WebSocket + HTTP. Corre en el **:8080**.
- **Frontend** (`frontend/`, React/Vite) — la interfaz. Se **compila** a archivos
  estáticos que sirve el servidor de empresa.
- **Servidor de empresa** (`server/`, Node/Express) — sirve el frontend, exige
  **login** y reenvía `/api`, `/video` y `/ws` al Bridge. Corre en el **:3000**.

> El servidor de empresa apunta a `localhost:8080`. Cuando el Bridge se mude a una
> Raspberry Pi, solo cambia la variable `BRIDGE_URL` a la IP de la Pi (por VPN).

---

## Requisitos

- **Python 3.11+** (probado con 3.13) para el Bridge.
- **Node 18+** (probado con 22) para el frontend y el servidor.
- Para manejar el robot: el PC (o la Pi) conectado al **WiFi del Go2** (modo LocalAP).

---

## 1. Bridge (`:8080`)

Es lo que habla con el robot. Se ejecuta **desde dentro de `Bridge/`** (usa rutas
relativas para `data/`).

```bash
cd Bridge
pip install -r requirements.txt
pip install sounddevice          # falta en requirements.txt pero el audio lo necesita
python main.py
```

Arranca aunque el robot esté apagado: queda **en espera** y se conecta solo cuando
el perro emite señal (y reconecta solo si se cae a mitad).

> ⚠️ **Solo un Bridge a la vez** en el :8080. Si un arranque falla con
> `address already in use`, hay un Bridge zombi de antes ocupando el puerto; ciérralo
> antes de relanzar.

---

## 2. Frontend (compilar)

El servidor de empresa sirve el frontend **ya compilado**. Cada vez que cambies
código del frontend, hay que recompilar:

```bash
cd frontend
npm install        # solo la primera vez
npm run build      # genera frontend/dist
```

---

## 3. Servidor de empresa (`:3000`)

Sirve el frontend compilado, pide login y reenvía al Bridge.

```bash
cd server
npm install        # solo la primera vez
npm start
```

Abre **http://localhost:3000** → login con **admin / admin** (cámbialo, ver abajo).

---

## Orden de arranque (uso normal)

1. Conecta el PC al **WiFi del robot**.
2. Arranca el **Bridge** (`cd Bridge && python main.py`).
3. Asegúrate de tener el frontend compilado (`cd frontend && npm run build`).
4. Arranca el **servidor** (`cd server && npm start`).
5. Abre **http://localhost:3000**, haz login y maneja el perro.

Los pasos 2 y 4 son dos procesos separados: cada uno en su terminal. El Bridge **no**
se arranca solo con el servidor.

---

## Modo desarrollo del frontend (opcional, sin login)

Para iterar la interfaz rápido, sin recompilar ni pasar por el login, usa el
servidor de desarrollo de Vite (recarga en caliente). Reenvía él mismo al Bridge:

```bash
cd frontend
npm run dev        # http://localhost:5173
```

Necesita el **Bridge** corriendo en el :8080. No pasa por el servidor de empresa
ni por el login — es solo para desarrollo.

---

## Usuarios del login

Viven en `server/users.json` (no se sube a git). **Cambia el admin/admin**:

```bash
cd server
npm run hash miClaveSegura      # imprime un hash
# pega el hash en users.json, p. ej.:  { "froilan": "$2a$10$..." }
```

## Puertos

| Componente            | Puerto | Comando                          |
|-----------------------|--------|----------------------------------|
| Bridge                | 8080   | `cd Bridge && python main.py`    |
| Servidor de empresa   | 3000   | `cd server && npm start`         |
| Frontend (desarrollo) | 5173   | `cd frontend && npm run dev`     |

Más detalle del servidor y su configuración (variables de entorno, producción con
MFA) en [`server/README.md`](server/README.md).
