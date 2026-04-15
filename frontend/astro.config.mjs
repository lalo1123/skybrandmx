import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import icon from "astro-icon";

export default defineConfig({
    integrations: [tailwind(), icon()],
    server: { port: 4005 },
    vite: {
        server: {
            proxy: {
                '/api': 'http://localhost:8000'
            }
        }
    }
});
