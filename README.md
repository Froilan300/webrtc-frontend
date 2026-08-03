# Unitree Go2 Control System (`webrtc-frontend`)

Sistema de control, monitoreo y teleoperación en tiempo real para el robot cuadrúpedo **Unitree Go2** mediante **WebRTC** y **WebSockets**.

---

## 📌 ¿Qué es y en qué consiste?

Este proyecto proporciona una plataforma integral para interactuar con el robot **Unitree Go2** desde una interfaz web moderna. Permite la teleoperación remota, transmisión de streaming de video en tiempo real, visualización 3D de la nube de puntos LiDAR, comunicación de audio bidireccional, gestión de waypoints/mapas y ejecución de rutinas de patrullaje autónomo.

El proyecto está estructurado en dos partes principales:

1. **`Bridge` (Backend - Python / FastAPI)**:
   - Actúa como puente entre la interfaz web y el robot mediante el SDK de Unitree (`unitree_webrtc_connect`).
   - Gestiona las conexiones WebRTC con el robot y mantiene una comunicación bidireccional en tiempo real con el frontend mediante **WebSockets** (`/ws`).
   - Proporciona servicios dedicados para control de movimiento, cámara (video streaming MJPEG), audio (micrófono y altavoz), escaneo LiDAR 3D, mapas y patrullaje.

2. **`frontend` (Interfaz Web - React + Vite + TailwindCSS + Three.js)**:
   - Panel de control web SPA (Single Page Application) moderno, modular y responsivo.
   - **Componentes clave**:
     - 🎮 **ControlPad**: Joystick y controles interactivos de movimiento y posturas.
     - 📹 **CameraView**: Transmisión de video en vivo de la cámara frontal con opción de captura/grabación.
     - 🌐 **PointCloudView**: Renderizado 3D en tiempo real de la nube de puntos LiDAR utilizando **Three.js**.
     - 🗺️ **MapView & PatrolPanel**: Creación de mapas, asignación de waypoints y control de patrullaje autónomo.
     - 🔊 **AudioControls**: Transmisión y recepción de audio (hablar/escuchar).
     - 🔋 **StatusBar & BatteryAlert**: Monitoreo en tiempo real del estado de batería y conexión.

---

## 🛠️ Requisitos Previos

Antes de comenzar, asegúrate de contar con los siguientes elementos instalados en tu sistema:

- **Python 3.10 o superior**
- **Node.js 18.x o superior** y **npm**
- Conexión a la red local/Wi-Fi del robot **Unitree Go2**

---

## 📦 Instalación de Dependencias

### 1. Backend (`Bridge`)

Abre una terminal en la raíz del proyecto y dirígete a la carpeta `Bridge`:

```bash
cd Bridge
```

Crear y activar un entorno virtual de Python:

- **Windows (PowerShell)**:
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
- **Linux / macOS**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

Instalar las dependencias de Python:

```bash
pip install -r requirements.txt
```

### 2. Frontend (`frontend`)

En otra terminal, dirígete a la carpeta `frontend`:

```bash
cd frontend
npm install
```

---

## 🚀 Cómo Arrancar el Proyecto

Para que el sistema funcione correctamente, se deben ejecutar **ambos servicios** (Backend Bridge y Frontend Web).

### Paso 1: Iniciar el servidor Backend (`Bridge`)

1. Asegúrate de estar dentro del directorio `Bridge` y tener el entorno virtual activado.
2. Ejecuta el servidor principal:

```bash
python main.py
```

*El backend se iniciará en `http://localhost:8080` (servidor WebSocket disponible en `ws://localhost:8080/ws`).*

### Paso 2: Iniciar la interfaz Frontend (`frontend`)

1. En tu otra terminal, asegúrate de estar dentro del directorio `frontend`.
2. Inicia el servidor de desarrollo Vite:

```bash
npm run dev
```

3. Abre el navegador web e ingresa a la dirección indicada por Vite (por defecto: `http://localhost:5173`).

---

## 📁 Estructura del Proyecto

```text
webrtc-frontend/
├── Bridge/                     # Servidor Backend (Python + FastAPI)
│   ├── data/                   # Mapas y rutas guardadas
│   ├── services/               # Servicios del SDK (movimiento, cámara, LiDAR, audio, patrullaje)
│   ├── main.py                 # Punto de entrada FastAPI y WebSocket handler
│   └── requirements.txt        # Dependencias de Python
├── frontend/                   # Interfaz de usuario (React + Vite + TailwindCSS)
│   ├── public/                 # Archivos estáticos
│   ├── src/
│   │   ├── components/         # Componentes UI (ControlPad, CameraView, PointCloudView, etc.)
│   │   ├── services/           # Cliente WebSocket y API REST
│   │   ├── stores/             # Estado global con Zustand
│   │   ├── App.jsx             # Componente principal
│   │   └── main.jsx            # Punto de entrada de React
│   ├── package.json            # Dependencias de Node.js
│   └── vite.config.js          # Configuración de Vite
└── README.md                   # Documentación principal del proyecto
```