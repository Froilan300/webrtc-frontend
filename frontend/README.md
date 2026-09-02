# 🖥️ Frontend — Dashboard (React / Vite)

Interfaz web para controlar el robot. Se comunica con el [backend](../Bridge/README.md)
por WebSocket (comandos + telemetría) y HTTP (vídeo + REST). **No habla nunca
directamente con el robot.**

## Stack

| Tecnología | Uso |
|---|---|
| **React 18 + Vite** | Componentes y dev server con recarga en caliente |
| **TailwindCSS** | Estilos (clases utilitarias) |
| **Zustand** | Estado global (robot y mapa) |
| **Three.js** | Visor 3D de la nube de puntos LiDAR |
| **Canvas 2D** | Mapa SLAM |

## Arranque

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

El dev server hace de **proxy** de `/ws`, `/video` y `/api` hacia el backend en
`:8080` (ver `vite.config.js`), así que solo necesitas abrir
**http://localhost:5173**.

## Estructura

| Carpeta / archivo | Contenido |
|---|---|
| `index.html` | Página raíz donde se monta React. |
| `vite.config.js` | Dev server + proxy al backend. |
| `tailwind.config.js`, `postcss.config.js` | Configuración de estilos. |
| `public/` | Recursos estáticos (logo, iconos). |
| `src/` | Todo el código de la app ([README](src/README.md)). |

## Scripts (`package.json`)

| Comando | Qué hace |
|---|---|
| `npm run dev` | Arranca el dev server (desarrollo). |
| `npm run build` | Genera la build de producción en `dist/`. |
| `npm run preview` | Sirve la build de producción para probarla. |

Ver el [README principal](../README.md) para la arquitectura completa.
