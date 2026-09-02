# data — Mapas y rutas guardadas

Almacenamiento en disco que gestiona [`map_service.py`](../services/map_service.py).
Se crea automáticamente al arrancar el backend.

| Carpeta | Contenido |
|---|---|
| `maps/` | Mapas guardados (un `.json` por mapa). |
| `routes/` | Rutas de patrulla (un `.json` por ruta). |

## Formato de una ruta (`routes/*.json`)

```json
{
  "id": "eb72b48f-6e49-4a93-97ad-47940a209ebe",
  "name": "Ronda salón",
  "is_loop": false,
  "waypoints": [
    { "id": "...", "label": "WP1", "position": { "x": 1.0, "y": 0.5 } },
    { "id": "...", "label": "WP2", "position": { "x": 2.3, "y": 0.5 } }
  ]
}
```

| Campo | Significado |
|---|---|
| `id` | Identificador único (uuid). Es también el nombre del archivo. |
| `name` | Nombre visible en el panel de patrulla. |
| `is_loop` | Si `true`, la patrulla vuelve al primer punto al terminar (bucle). |
| `waypoints` | Lista de puntos con su posición `{x, y}` en metros (frame del mapa). |

Cuando inicias una patrulla, `patrol_service` lee la ruta por su `id` y recorre
sus `waypoints` en orden.

> Estos archivos los genera la app (al **Guardar** una ruta en el panel). No hace
> falta editarlos a mano.
