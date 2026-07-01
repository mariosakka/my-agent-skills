---
name: playwright-cli
description: >-
  Run Playwright (the CLI + @playwright/test library) inside a colete-online dev
  container to drive a browser — write/run E2E tests, `playwright codegen`, take
  screenshots, scrape a page, or automate the local app. Use this WHENEVER the user
  wants browser automation / E2E / "test it in a real browser" from inside a dev
  stack, and especially if Claude thinks it "has no Playwright access" — it does, via
  the shell: there is no Playwright MCP tool, you drive Playwright by running
  `npx playwright …` or a small `node` script with `require('playwright')`. These
  containers are Alpine, so ONLY Chromium is available (the system binary at
  /usr/bin/chromium-browser) — Firefox/WebKit are not. Do NOT report "no browser
  tool" and stop; reach for this skill and run the CLI.
---

# playwright-cli

Playwright is installed in the colete-online dev containers (`playwright` +
`@playwright/test`), but **its bundled browser downloads don't run on Alpine/musl**.
So browser download is skipped (`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`) and everything
drives the **system Chromium** at `/usr/bin/chromium-browser` (also in
`$PW_CHROMIUM_PATH`). **Chromium only** — Firefox/WebKit are unavailable here.

There is no Playwright MCP server/tool — and you don't need one. Drive Playwright by
running the CLI / a script in the shell.

## The one rule that makes it work

Launch Chromium by `executablePath` with `--no-sandbox` (containers can't use the
Chromium sandbox) and `--disable-dev-shm-usage` (the default /dev/shm is tiny), headless.

### `playwright test` — `playwright.config.ts`
```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  use: {
    headless: true,
    launchOptions: {
      executablePath: process.env.PW_CHROMIUM_PATH || "/usr/bin/chromium-browser",
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
  },
  // The app under test, if you've started it, is on :3000 inside the container:
  // baseURL: "http://127.0.0.1:3000",
});
```
Run: `NODE_ENV=local npx playwright test` (or one spec: `npx playwright test e2e/login.spec.ts`).

### Library / ad-hoc script (`.cjs`, with the global module path)
```bash
export NODE_PATH=$(npm root -g)   # playwright is installed globally
node -e '
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM_PATH || "/usr/bin/chromium-browser",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const p = await b.newPage();
  await p.goto("http://127.0.0.1:3000/");
  console.log(await p.title());
  await p.screenshot({ path: "/app/server/shot.png" });
  await b.close();
})();
'
```

### codegen / open
```bash
PW_CHROMIUM_PATH=/usr/bin/chromium-browser \
  npx playwright codegen --browser chromium http://127.0.0.1:3000/
```
If `codegen` can't find a browser, fall back to the `executablePath` launch form above —
that path always works here.

## Notes
- Verified working: `chromium.launch({ executablePath, args:["--no-sandbox","--disable-dev-shm-usage"] })` launches, navigates, and screenshots.
- The egress firewall (if the stack has it on) blocks `10.0.0.0/8` — Playwright can hit
  `localhost` + public sites but not internal `10.x`.
- Sanity: `npx playwright --version` and `chromium-browser --version`.
