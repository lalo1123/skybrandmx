# Guía de Despliegue en Dokploy: Skybrandmx (Astro)

Astro se puede desplegar en Dokploy de dos formas principales: como **Sitio Estático (SSG)** o como **Aplicación SSR**. Dado que esta es una landing page, el enfoque estático es el más recomendado por su velocidad y costo casi nulo.

## Opción 1: Static Site (Recomendada)

1. **Build en Local/CI:**
   Asegúrate de que el comando `npm run build` genere la carpeta `dist/`.

2. **Configuración en Dokploy:**
   - Ve a **Applications** -> **Create Application**.
   - Selecciona tu repositorio de GitHub/GitLab.
   - En **Build Type**, selecciona **Static**.
   - **Build Command:** `npm install && npm run build`
   - **Publish Directory:** `dist`

3. **Dominio:**
   Configura `skybrandmx.com` en la sección de **Domains** dentro de la aplicación en Dokploy y apunta tus registros CNAME/A según las instrucciones del panel.

---

## Opción 2: Docker (Estandarizada)

Si prefieres usar un `Dockerfile`, crea uno en la raíz con este contenido:

```dockerfile
# Build
FROM node:lts-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Runtime (Nginx para servir estáticos)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

En Dokploy, selecciona **Build Type: Dockerfile** y él se encargará de todo.

---

## Variables de Entorno (Opcional)
Si implementas un formulario de contacto directo (sin WhatsApp), necesitarás configurar estas variables en el panel de Dokploy:
- `CONTACT_EMAIL`: Correo donde recibirás leads.
- `API_KEY_SERVICE`: Si usas algún servicio como SendGrid o Resend.
