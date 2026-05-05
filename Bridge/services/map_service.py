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
    def __init__(self):
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        ROUTES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Mapas ──────────────────────────────────────────────────────

    def list_maps(self) -> list:
        result = []
        for f in MAPS_DIR.glob("*.json"):
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return result

    def create(self, name: str) -> dict:
        m = {
            "id": str(uuid.uuid4()),
            "name": name,
            "waypoints": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (MAPS_DIR / f"{m['id']}.json").write_text(json.dumps(m), encoding="utf-8")
        return m

    def get_map(self, map_id: str) -> Optional[dict]:
        p = MAPS_DIR / f"{map_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def delete_map(self, map_id: str) -> bool:
        p = MAPS_DIR / f"{map_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    # ── Rutas ──────────────────────────────────────────────────────

    def list_routes(self) -> list:
        result = []
        for f in ROUTES_DIR.glob("*.json"):
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return result

    def save_route(self, route: dict) -> dict:
        if "id" not in route:
            route["id"] = str(uuid.uuid4())
        (ROUTES_DIR / f"{route['id']}.json").write_text(json.dumps(route), encoding="utf-8")
        return route

    def get_route(self, route_id: str) -> Optional[dict]:
        p = ROUTES_DIR / f"{route_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def delete_route(self, route_id: str) -> bool:
        p = ROUTES_DIR / f"{route_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False
