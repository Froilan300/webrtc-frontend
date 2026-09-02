# public — Recursos estáticos

Archivos que Vite sirve tal cual desde la raíz (`/`). Se referencian con ruta
absoluta en el código, p. ej. `<img src="/logo.png">`.

| Archivo | Dónde se usa | Descripción |
|---|---|---|
| `logo.png` | `StatusBar` | Logo de la marca, arriba a la izquierda. |
| `icono-foto.png` | `CameraView` | Icono del botón de hacer foto. |
| `icono-video.png` | `CameraView` | Icono del botón de grabar vídeo. |
| `pantalla-completa.png` | `CameraView` | Icono del botón de pantalla completa. |

## Notas

- Si un icono no carga, el componente muestra un **emoji de reserva** (📷, ⏺, ⛶),
  así que la app funciona aunque falte la imagen.
- Para **cambiar un icono o el logo**, sustituye el archivo por otro con el mismo
  nombre (no hay que tocar código).
