# Blueprint Técnico: Arquitectura Multi-Agente SkyBrandMX

Este documento define la estructura y responsabilidades para la operación bajo el modelo de agentes especializados.

## 1. Roles y Responsabilidades

### @Director (Arquitecto de Software)
- **Alcance**: Integridad del repositorio, flujo de datos global, orquestación entre servicios y CI/CD.
- **Objetivo**: Asegurar que el Frontend y el Backend hablen el mismo idioma (API) y que el proyecto escale correctamente.

### @Stichy (Frontend - Astro + Tailwind)
- **Alcance**: Directorio `frontend/`.
- **Tareas**: Creación de componentes UI, vistas del Dashboard, gestión de estados en cliente y consumo de APIs.
- **Tecnologías**: Astro, TailwindCSS, TypeScript/JavaScript.

### @Backend (Ingeniero Python - FastAPI)
- **Alcance**: Directorio `backend/`.
- **Tareas**: Lógica de negocio, modelos de base de datos, integración con APIs externas (Skydropx, Facturapi, Meta) y seguridad.
- **Tecnologías**: Python 3.x, FastAPI, SQLAlchemy/SQLModel, PostgreSQL.

## 2. Estructura de Directorios

Se propone la siguiente separación física para evitar conflictos y delimitar áreas de trabajo:

```text
skybrandmx_all/
├── frontend/               # Gestionado por @Stichy
│   ├── src/
│   │   ├── components/     # Componentes atómicos (Botones, Tarjetas, Modales)
│   │   ├── layouts/        # Estructuras de Dashboard y Landing
│   │   ├── pages/          # Rutas de Astro (index.astro, dashboard/index.astro)
│   │   └── styles/         # Configuraciones de Tailwind
│   ├── public/             # Imágenes, iconos y assets estáticos
│   ├── astro.config.mjs
│   ├── package.json
│   └── tailwind.config.mjs
│
├── backend/                # Gestionado por @Backend
│   ├── app/
│   │   ├── api/            # Endpoints organizados por versiones (v1)
│   │   ├── core/           # Configuraciones globales, Seguridad/CORS, Auth
│   │   ├── db/             # Conexión a DB y Sesiones
│   │   ├── integrations/   # Módulos para Skydropx, Facturapi, Meta, etc.
│   │   ├── models/         # Modelos de Base de Datos (ORM)
│   │   ├── schemas/        # Esquemas de Pydantic (Validación de entrada/salida)
│   │   └── main.py         # Punto de entrada de FastAPI
│   ├── requirements.txt    # Dependencias de Python
│   └── .env                # Variables de entorno (Secrets)
│
├── docker-compose.yml      # Orquestación de ambos servicios para desarrollo local
├── backend_schema.sql      # Backup del esquema de la DB
└── README.md               # Guía general del proyecto
```

## 3. Protocolo de Comunicación
- El Frontend se comunicará con el Backend exclusivamente a través de la REST API (v1).
- Se utilizarán **Schemas de Pydantic** en el Backend como fuente de verdad para la documentación de la API (Swagger UI).
- @Stichy debe esperar a que @Backend defina los endpoints antes de implementar funcionalidades de datos complejos.

## 4. Próximos Pasos
1. **Aprobación**: El usuario revisa y aprueba esta estructura.
2. **Reorganización**: Mover archivos de Astro a la carpeta `frontend/`.
3. **Primera Tarea Backend**: @Backend implementará el esquema base para el manejo de clientes e inventario.
