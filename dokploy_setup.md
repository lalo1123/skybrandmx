# Deploy SkyBrandMX en Dokploy (Hostinger VPS)

## 1. Instalar Dokploy en tu VPS

Conéctate a tu VPS por SSH y ejecuta:

```bash
curl -sSL https://dokploy.com/install.sh | sh
```

Después de la instalación, accede a Dokploy en `http://TU-IP-VPS:3000` y crea tu cuenta admin.

## 2. Subir el repo a GitHub

Si aún no lo tienes en GitHub, créalo y sube:

```bash
git remote add origin https://github.com/TU-USUARIO/skybrandmx.git
git push -u origin master
```

## 3. Crear proyecto en Dokploy

1. En Dokploy, ve a **Projects** > **Create Project** (nombre: "skybrandmx")
2. Dentro del proyecto, crea un servicio **Compose**:
   - Source: **GitHub** > selecciona tu repo
   - Branch: `master`
   - Compose Path: `docker-compose.yml`
3. Click **Deploy**

## 4. Configurar variables de entorno

En Dokploy, en la sección **Environment** del servicio compose, agrega:

```
DB_PASSWORD=tu-password-seguro
ADMIN_EMAIL=serratos@skybrandmx.com
ADMIN_PASSWORD=tu-password-admin
SECRET_KEY=una-clave-aleatoria-larga
```

## 5. Configurar dominio

1. En Dokploy, ve a tu servicio **frontend**
2. En **Domains**, agrega `skybrandmx.com`
3. Activa **HTTPS** (Dokploy usa Let's Encrypt automáticamente)
4. En Hostinger (o tu proveedor DNS), crea un registro **A** apuntando a la IP de tu VPS:
   - `skybrandmx.com` → `TU-IP-VPS`
   - `www.skybrandmx.com` → `TU-IP-VPS`

## 6. Verificar

- Landing page: `https://skybrandmx.com`
- API docs: `https://skybrandmx.com/api/docs`
- API health: `https://skybrandmx.com/api/v1/`

## Arquitectura

```
Internet → Traefik (SSL) → Nginx (frontend:80)
                                  ├── /          → Archivos estáticos Astro
                                  └── /api/*     → Proxy → FastAPI (backend:8000)
                                                              └── PostgreSQL (db:5432)
```
