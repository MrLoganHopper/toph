import {defineConfig,devices} from '@playwright/test';
const baseURL=process.env.E2E_BASE_URL||'http://127.0.0.1:5173';
export default defineConfig({
 testDir:'./e2e',fullyParallel:false,workers:1,retries:process.env.CI?1:0,
 reporter:[['list'],['html',{open:'never'}]],
 use:{baseURL,trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
 webServer:process.env.E2E_BASE_URL?undefined:{command:'npm run dev',url:baseURL,reuseExistingServer:!process.env.CI,timeout:60000},
});
