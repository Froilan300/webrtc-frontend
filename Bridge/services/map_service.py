"""
map_service — persistencia de mapas y rutas de patrulla.

Guarda cada mapa y cada ruta como un archivo JSON en `data/maps` y `data/routes`.
Ofrece el CRUD que consumen los endpoints `/api/maps` y `/api/routes`. Una ruta
es una lista de waypoints (con posición) y una bandera `is_loop`; el
`patrol_service` la lee por `get_route` al iniciar una patrulla.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MAPS_DIR = Path("data/maps")
ROUTES_DIR = Path("data/routes")


class MapService:
    """CRUD de mapas y rutas sobre archivos JSON en disco."""

    def __init__(self):
        """Asegura que existan las carpetas de mapas y rutas."""
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        ROUTES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Mapas ──────────────────────────────────────────────────────

    def list_maps(self) -> list:
        """Devuelve todos los mapas guardados (ignora archivos corruptos)."""
        result = []
        for f in MAPS_DIR.glob("*.json"):
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return result

    def create(self, name: str) -> dict:
        """Crea un mapa nuevo (con id y timestamp), lo guarda y lo devuelve."""
        m = {
            "id": str(uuid.uuid4()),
            "name": name,
            "waypoints": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (MAPS_DIR / f"{m['id']}.json").write_text(json.dumps(m), encoding="utf-8")
        return m

    def get_map(self, map_id: str) -> Optional[dict]:
        """Devuelve un mapa por su id, o None si no existe."""
        p = MAPS_DIR / f"{map_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def delete_map(self, map_id: str) -> bool:
        """Borra un mapa por su id. Devuelve True si existía."""
        p = MAPS_DIR / f"{map_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    # ── Rutas ──────────────────────────────────────────────────────

    def list_routes(self) -> list:
        """Devuelve todas las rutas guardadas (ignora archivos corruptos)."""
        result = []
        for f in ROUTES_DIR.glob("*.json"):
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return result

    def save_route(self, route: dict) -> dict:
        """Guarda una ruta (le asigna id si no lo trae) y la devuelve."""
        if "id" not in route:
            route["id"] = str(uuid.uuid4())
        (ROUTES_DIR / f"{route['id']}.json").write_text(json.dumps(route), encoding="utf-8")
        return route

    def get_route(self, route_id: str) -> Optional[dict]:
        """Devuelve una ruta por su id, o None. La usa el patrol_service al iniciar."""
        p = ROUTES_DIR / f"{route_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def delete_route(self, route_id: str) -> bool:
        """Borra una ruta por su id. Devuelve True si existía."""
        p = ROUTES_DIR / f"{route_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False
