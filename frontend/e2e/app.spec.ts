import {test,expect,type Page} from '@playwright/test';
const password=process.env.E2E_PASSWORD||'';
test.skip(!password,'Set E2E_PASSWORD to the private development seed password. No published default exists.');
async function login(page:Page,username='demo.admin'){
 await page.goto('/login');await page.getByLabel('Username',{exact:true}).fill(username);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Log in',exact:true}).click();
 await expect(page).toHaveURL(username.includes('worker')?/\/worker\//:/\/admin\/.*\/welcome/);
}
test('dashboard, expandable detail, filters, real catalogs, and route refresh',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await login(page);
 // Sidebar link is intentionally distinct from the welcome map overlay.
 await page.locator('.sidebar').getByRole('link',{name:'Dashboard',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();await expect(page.getByText('Scheduled Now',{exact:true})).toBeVisible();await expect(page.getByText('Extraction Confidence',{exact:true})).toBeVisible();
 await expect(page.getByRole('columnheader',{name:'Activity / Fertilizer',exact:true})).toBeVisible();
 const view=page.getByRole('button',{name:'View',exact:true}).first();await expect(view).toBeVisible();await view.click();await expect(page.getByText('Summary',{exact:true})).toBeVisible();await page.screenshot({path:'test-results/dashboard-expanded.png',fullPage:true});
 await page.getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('button',{name:'Filter',exact:true}).click();
 const fertilizer=page.getByLabel('Fertilizer',{exact:true});await expect(fertilizer).toBeVisible();const value=await fertilizer.locator('option').nth(1).getAttribute('value');expect(value).toBeTruthy();await fertilizer.selectOption(value!);await expect(page).toHaveURL(/fertilizer_id=/);
 await page.keyboard.press('Escape');await page.reload();await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();await expect(page).toHaveURL(/fertilizer_id=/);
 await page.locator('.sidebar').getByRole('link',{name:'Activity Logs',exact:true}).click();await expect(page.getByRole('heading',{name:'Activity Logs',exact:true})).toBeVisible();
 await expect(page.locator('.log-card').first()).toBeVisible();expect(errors).toEqual([]);
});
test('map selection uses a shared report grid',async({page})=>{
 await login(page);await page.locator('.sidebar').getByRole('link',{name:'Map',exact:true}).click();await expect(page.getByTestId('field-map')).toBeVisible();
 const selector=page.getByLabel('Select a field');await expect(selector).toBeVisible();await selector.selectOption({index:1});await expect(page.locator('.log-card').first()).toBeVisible();expect(await page.locator('.log-card').count()).toBeLessThanOrEqual(10);
});
test('mobile worker home and recording-ready screen contain no admin controls',async({page})=>{
 await page.setViewportSize({width:393,height:852});await login(page,'demo.worker1');await expect(page.locator('.sidebar')).toHaveCount(0);await page.getByRole('link',{name:'Record your work'}).click();
 await expect(page.getByRole('heading',{name:'TOPH',exact:true})).toBeVisible();await expect(page.locator('.voice-ring')).toBeVisible();await expect(page.getByText('TOPH is an AI assistant. This conversation is recorded and saved for your farm.')).toBeVisible();await page.screenshot({path:'test-results/worker-ready.png',fullPage:true});
 // Live microphone/WebRTC and real-device media tests remain separate, credentialed smoke tests.
});
