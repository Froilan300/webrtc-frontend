# 🐍 Bridge — Backend (Python / FastAPI)

Puente entre el navegador y el robot Unitree Go2. Es **el único proceso que habla
con el robot** (por WebRTC); el navegador solo habla con este backend.

## ¿Qué hace?

- Abre un **WebSocket** (`/ws`) para recibir comandos en tiempo real y repartir
  telemetría a todos los clientes conectados.
- Sirve el **vídeo** de la cámara como MJPEG (`/video`).
- Expone una **API REST** (`/api/...`) para foto/vídeo, estado, mapas y rutas.
- Orquesta ocho **servicios**, cada uno con una responsabilidad (ver
  [`services/`](services/README.md)).

## Archivos

| Archivo | Descripción |
|---|---|
| `main.py` | Punto de entrada. Crea los servicios, define el WebSocket, los endpoints HTTP y enruta cada comando. |
| `requirements.txt` | Dependencias de Python. |
| `services/` | Lógica por dominio (SDK, movimiento, cámara, audio, media, mapas, patrulla, LiDAR). |
| `data/` | Mapas y rutas de patrulla guardados (JSON). Se crea solo. |
| `media/` | Fotos y vídeos capturados. Se crea solo. |

## Arranque

```bash
cd Bridge
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
pip install sounddevice av        # necesario para el audio bidireccional
python main.py                    # http://localhost:8080
```

> El backend debe ejecutarse **desde la carpeta `Bridge/`** (usa rutas relativas
> `data/` y `media/`).

## Flujo de un comando

```
Navegador  --WebSocket JSON-->  main._handle()  -->  servicio  -->  robot (WebRTC)
Robot      --telemetría------>  servicio        -->  main.broadcast()  -->  Navegador
```

## Puerto y topics

- **Puerto:** `8080` (Uvicorn).
- **Topics del robot** a los que se suscribe: `SPORT_MOD_STATE` (posición),
  `LOW_STATE` (rumbo IMU + batería), `rt/utlidar/voxel_map_compressed` (LiDAR).

Ver el [README principal](../README.md) para la arquitectura completa y el
protocolo WebSocket / REST.
