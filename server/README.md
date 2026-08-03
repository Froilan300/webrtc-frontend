# Servidor de empresa (local)

La "caja del medio" de la arquitectura, en versión local. Se pone **delante del
Bridge** y hace tres cosas:

1. Sirve el frontend ya compilado (`frontend/dist`).
2. Reenvía `/api`, `/video` y `/ws` al Bridge (reverse proxy).
3. Exige **login**: sin sesión no se llega ni al panel, ni al vídeo, ni al `/ws`.

El Bridge no se toca ni se expone. Aquí se apunta a `localhost:8080` (donde corre
hoy). En producción ese `localhost` será la IP de la Pi a través de la VPN.

```
  Navegador ──▶ Servidor empresa (:3000) ──▶ Bridge (:8080) ──WebRTC──▶ Go2
                 login + proxy + frontend
```

## Arrancar

```bash
# 1. Compilar el frontend (una vez, o cada vez que lo cambies)
cd frontend
npm install       # si no está ya
npm run build

# 2. Levantar el servidor de empresa
cd ../server
npm install       # solo la primera vez
npm start
```

Abre http://localhost:3000 → te lleva al login.

Usuario por defecto (creado en el primer arranque): **admin / admin**.
El Bridge debe estar corriendo aparte en `localhost:8080` para que el vídeo, la
telemetría y los comandos funcionen; sin él, el login y el panel cargan pero el
robot sale como "desconectado".

## Gestionar usuarios

Los usuarios viven en `server/users.json` (no se sube a git). Cada entrada es
`"usuario": "<hash bcrypt>"`. Para añadir o cambiar uno:

```bash
npm run hash miClaveSegura      # imprime el hash
# pega el hash en users.json, p.ej.:  { "froilan": "$2a$10$..." }
```

**Cambia el admin/admin por defecto antes de nada.**

## Configuración (variables de entorno, opcionales)

| Variable          | Por defecto                     | Para qué |
|-------------------|---------------------------------|----------|
| `PORT`            | `3000`                          | Puerto del servidor |
| `BRIDGE_URL`      | `http://localhost:8080`         | Dónde está el Bridge (en prod: IP de la Pi por VPN) |
| `SESSION_SECRET`  | `cambia-esto-en-produccion`     | Clave para firmar la cookie de sesión |

## Qué es esto y qué NO es

Este login es un **stand-in para desarrollar en local**. En producción, con
acceso desde cualquier ordenador por internet, se sustituye por una **puerta de
identidad con MFA** (Cloudflare Access o Authelia) delante de este mismo proxy.
La lógica de proxy y de servir el frontend se mantiene; lo que cambia es de dónde
viene la autenticación.
