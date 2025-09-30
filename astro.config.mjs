// @ts-check
import { defineConfig } from 'astro/config';
import serviceWorker from "astrojs-service-worker";

import db from '@astrojs/db';

// https://astro.build/config
export default defineConfig({
  //output: 'server', // Required change. Pick either hybrid or server.output: 'server',
  integrations: [db(), serviceWorker()]
});