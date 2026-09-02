# media — Fotos y vídeos capturados

Aquí se guardan las **fotos** y **vídeos** que capturas desde la cámara en vivo.
La carpeta la gestiona [`media_service.py`](../services/media_service.py) y se
crea automáticamente.

| Tipo | Formato | Nombre |
|---|---|---|
| Foto | `.jpg` (calidad 92) | `foto_AAAAMMDD_HHMMSS.jpg` |
| Vídeo | `.mp4` (codec mp4v, 20 fps) | `video_AAAAMMDD_HHMMSS.mp4` |

## Cómo se usan

1. En el panel de la cámara pulsas **foto** o **vídeo**.
2. El backend guarda el archivo aquí.
3. El navegador lo **descarga automáticamente** a tu carpeta de Descargas
   (endpoint `GET /api/media/{nombre}`).

> El vídeo se graba sincronizado con el tiempo real, así que dura lo mismo que la
> grabación (no sale acelerado).
