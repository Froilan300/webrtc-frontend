# src — Código de la aplicación

Todo el código React del dashboard. Punto de entrada: `main.jsx` → `App.jsx`.

## Archivos raíz

| Archivo | Descripción |
|---|---|
| `main.jsx` | Bootstrap: monta `<App />` en el `#root` del HTML. |
| `App.jsx` | Layout de 2 columnas y conmutador **Mapa SLAM ⇄ Nube LiDAR**. Abre el WebSocket al arrancar. |
| `index.css` | Directivas de Tailwind. |

## Carpetas

| Carpeta | Contenido |
|---|---|
| [`components/`](components/README.md) | Componentes de UI (cámara, mapa, controles, patrulla, audio…). |
| [`services/`](services/README.md) | Cliente WebSocket (comunicación con el backend). |
| [`stores/`](stores/README.md) | Estado global con Zustand (robot y mapa). |

## Cómo fluye el estado

```
Backend ──WebSocket──> websocketService ──> stores (Zustand) ──> componentes (se repintan)
Componentes ──ws.send()──> websocketService ──WebSocket──> Backend ──> robot
```

- Los **componentes leen** del store (`useRobotStore`, `useMapStore`) y se
  repintan solos cuando cambia el estado.
- Los **componentes escriben** enviando comandos con `ws.send(...)`.
- `websocketService` es quien vuelca la telemetría entrante al store.
