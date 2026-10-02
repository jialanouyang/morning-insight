#!/usr/bin/env node
/* eslint-disable */
/**
 * 晨析界面截图脚本（开发辅助）。
 *
 * 原理：启动本机 Chrome（headless），通过 Chrome DevTools Protocol 驱动页面，
 * 完成登录后逐路由截图，输出到 docs/screenshots/。
 *
 * 用法：
 *   node scripts/shot.cjs              # 默认 http://127.0.0.1:5173
 *   BASE=http://127.0.0.1:4173 node scripts/shot.cjs
 */
"use strict";

const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const CHROME =
  process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = process.env.BASE || "http://127.0.0.1:5173";
const OUT = process.env.OUT || path.join(__dirname, "..", "docs", "screenshots");
const EMAIL = process.env.DEMO_EMAIL || "demo@example.com";
const PASSWORD = process.env.DEMO_PASSWORD || "demo1234";

const PAGES = [
  ["02-dashboard", "/dashboard"],
  ["03-reports", "/reports"],
  ["04-knowledge", "/knowledge"],
  ["05-competitors", "/competitors"],
  ["06-alerts", "/alerts"],
  ["07-periodicals", "/periodicals"],
  ["08-plugins", "/plugins"],
  ["09-settings", "/settings"],
  ["10-admin", "/admin"],
  ["11-about", "/about"],
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function getJson(url) {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let buf = "";
        res.on("data", (d) => (buf += d));
        res.on("end", () => {
          try {
            resolve(JSON.parse(buf));
          } catch (e) {
            reject(e);
          }
        });
      })
      .on("error", reject);
  });
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const port = 9337;
  const userData = path.join(process.env.TEMP || "/tmp", "mi-shot-profile");
  // 每次运行使用全新浏览器档案，确保从登录页开始（避免复用上次的登录态）
  fs.rmSync(userData, { recursive: true, force: true });
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${userData}`,
      "--window-size=1440,900",
      "about:blank",
    ],
    { stdio: "ignore" }
  );
  chrome.on("error", (e) => {
    console.error("Chrome 启动失败：", e.message);
    process.exit(1);
  });

  try {
    // 等待调试端口就绪
    let targets = null;
    for (let i = 0; i < 50; i++) {
      try {
        targets = await getJson(`http://127.0.0.1:${port}/json`);
        if (targets && targets.length) break;
      } catch {}
      await sleep(300);
    }
    if (!targets) throw new Error("调试端口未就绪");
    const page = targets.find((t) => t.type === "page");
    if (!page) throw new Error("未找到页面目标");

    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = rej;
    });

    let seq = 0;
    const pending = new Map();
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
      }
    };
    const send = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const id = ++seq;
        pending.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });

    await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });

    const nav = async (route, waitMs = 2500) => {
      await send("Page.navigate", { url: BASE + route });
      await sleep(waitMs);
    };
    const evalJs = async (expr) => {
      const r = await send("Runtime.evaluate", {
        expression: expr,
        awaitPromise: true,
        returnByValue: true,
      });
      if (r.exceptionDetails) {
        throw new Error(r.exceptionDetails.exception?.description || "evaluate 失败");
      }
      return r.result && r.result.value;
    };
    const shot = async (name) => {
      const r = await send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(r.data, "base64"));
      console.log("✓", name);
    };

    // 登录（等待登录表单挂载后再截图，避免截到空白页）
    await nav("/", 2000);
    for (let i = 0; i < 20; i++) {
      const ready = await evalJs(
        "!!document.querySelector('input[type=email], input[type=password]')"
      );
      if (ready) break;
      await sleep(500);
    }
    await shot("01-login");
    await evalJs(`(() => {
      const set = (el, v) => {
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
        el.dispatchEvent(new Event('input', { bubbles: true }));
      };
      const inputs = [...document.querySelectorAll('input')];
      const email = inputs.find(i => i.type === 'email') || inputs[0];
      const pwd = inputs.find(i => i.type === 'password');
      set(email, ${JSON.stringify(EMAIL)});
      set(pwd, ${JSON.stringify(PASSWORD)});
      const btn = [...document.querySelectorAll('button')].find(b => b.type === 'submit')
        || [...document.querySelectorAll('button')].pop();
      btn.click();
      return 'ok';
    })()`);
    await sleep(3500);

    const url = await evalJs("location.pathname");
    if (url === "/") {
      console.error("✗ 登录未跳转，当前仍在", await evalJs("location.href"));
      const txt = await evalJs("document.body.innerText.slice(0, 300)");
      console.error("页面内容：", txt);
      process.exitCode = 1;
    }

    // 逐页截图
    for (const [name, route] of PAGES) {
      await nav(route);
      await shot(name);
    }
    await ws.close();
    console.log("完成 →", OUT);
  } finally {
    try {
      chrome.kill();
    } catch {}
  }
}

main().catch((e) => {
  console.error("✗", e.message);
  process.exit(1);
});
