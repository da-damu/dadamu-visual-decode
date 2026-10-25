#!/usr/bin/env node
/**
 * Capture a website at desktop / tablet / mobile widths and extract computed
 * design tokens. Requires Playwright; the script prints install instructions
 * and exits with code 2 when it is missing.
 *
 * Usage:
 *   node probe_site.js https://example.com --out outputs/example
 */

const fs = require("fs");
const path = require("path");

function printInstall() {
  console.error("[error] Playwright is not installed in this project.");
  console.error("install:");
  console.error("  npm init -y");
  console.error("  npm i playwright");
  console.error("  npx playwright install chromium");
  console.error("or point NODE_PATH at a project that already has playwright:");
  console.error("  NODE_PATH=/path/to/project/node_modules node scripts/probe_site.js <url>");
}

function loadPlaywright() {
  for (const name of ["playwright", "playwright-core"]) {
    try {
      return require(name);
    } catch (_) {
      // try next
    }
  }
  printInstall();
  process.exit(2);
}

async function launchBrowser(chromium) {
  try {
    return await chromium.launch({ headless: true });
  } catch (bundledError) {
    // playwright-core does not download browsers. Fall back to an installed
    // Chrome / Edge so the script still works on a normal desktop.
    for (const channel of ["chrome", "msedge"]) {
      try {
        console.log(`[info] bundled Chromium unavailable, trying ${channel}`);
        return await chromium.launch({ headless: true, channel });
      } catch (_) {
        // try next channel
      }
    }
    throw bundledError;
  }
}

function parseArgs(argv) {
  const args = {
    url: null,
    out: null,
    widths: [1440, 768, 390],
    wait: 1500,
    timeout: 45000,
    fullPage: true,
  };
  const rest = [];
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (item === "--out") args.out = argv[++i];
    else if (item === "--widths") args.widths = argv[++i].split(",").map((v) => parseInt(v.trim(), 10)).filter(Boolean);
    else if (item === "--wait") args.wait = parseInt(argv[++i], 10);
    else if (item === "--timeout") args.timeout = parseInt(argv[++i], 10);
    else if (item === "--no-full-page") args.fullPage = false;
    else if (item === "--help" || item === "-h") {
      console.log("node probe_site.js <url> [--out DIR] [--widths 1440,768,390] [--wait 1500] [--timeout 45000] [--no-full-page]");
      process.exit(0);
    } else if (!item.startsWith("-") && !args.url) args.url = item;
    else rest.push(item);
  }
  if (!args.url) {
    console.error("[error] missing URL");
    console.error("usage: node probe_site.js <url> [--out DIR]");
    process.exit(1);
  }
  return args;
}

function safeName(value) {
  return String(value).replace(/^https?:\/\//, "").replace(/[^\w\u4e00-\u9fff.-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "site";
}

async function analyzePage(page) {
  return page.evaluate(() => {
    const bump = (map, key) => {
      if (key === undefined || key === null || key === "") return;
      map[key] = (map[key] || 0) + 1;
    };
    const top = (map, limit = 25) =>
      Object.entries(map)
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit)
        .map(([value, count]) => ({ value, count }));

    const elements = Array.from(document.querySelectorAll("*")).slice(0, 4000);
    const fonts = {};
    const sizes = {};
    const weights = {};
    const lineHeights = {};
    const colors = {};
    const backgrounds = {};
    const radii = {};
    const shadows = {};
    const paddings = {};
    const margins = {};
    const gaps = {};
    const transitions = {};
    const animations = {};
    const displays = {};
    const positions = {};

    for (const el of elements) {
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      const style = window.getComputedStyle(el);
      bump(fonts, style.fontFamily);
      bump(sizes, style.fontSize);
      bump(weights, style.fontWeight);
      bump(lineHeights, style.lineHeight);
      bump(colors, style.color);
      bump(backgrounds, style.backgroundColor);
      bump(radii, style.borderRadius);
      bump(shadows, style.boxShadow);
      if (style.padding && !/^0(px)?$/.test(style.padding)) bump(paddings, style.padding);
      if (style.margin && !/^0(px)?$/.test(style.margin)) bump(margins, style.margin);
      if (style.gap && !/^(normal|0px)$/.test(style.gap)) bump(gaps, style.gap);
      bump(transitions, style.transition);
      bump(animations, style.animationName);
      bump(displays, style.display);
      bump(positions, style.position);
    }

    const pick = (selector) => {
      const el = document.querySelector(selector);
      if (!el) return null;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const fields = [
        "fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing",
        "color", "backgroundColor", "borderRadius", "boxShadow", "padding",
        "margin", "display", "position", "transition", "animationName",
        "textTransform", "gap", "gridTemplateColumns", "maxWidth", "width",
        "height", "border", "backdropFilter", "opacity",
      ];
      const out = {};
      for (const field of fields) out[field] = style[field];
      return {
        selector,
        tag: el.tagName.toLowerCase(),
        text: (el.innerText || "").trim().slice(0, 200),
        rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
        style: out,
      };
    };

    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6")).slice(0, 40).map((el) => {
      const style = window.getComputedStyle(el);
      return {
        tag: el.tagName.toLowerCase(),
        text: (el.innerText || "").trim().slice(0, 200),
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
        lineHeight: style.lineHeight,
        color: style.color,
      };
    });

    const images = Array.from(document.querySelectorAll("img")).slice(0, 80).map((img) => {
      const rect = img.getBoundingClientRect();
      return {
        src: (img.currentSrc || img.src || "").slice(0, 300),
        alt: img.alt || "",
        natural: { width: img.naturalWidth, height: img.naturalHeight },
        displayed: { width: Math.round(rect.width), height: Math.round(rect.height) },
      };
    });

    const cssVariables = {};
    const mediaQueries = new Set();
    for (const sheet of Array.from(document.styleSheets)) {
      let rules;
      try {
        rules = sheet.cssRules;
      } catch (_) {
        continue;
      }
      for (const rule of Array.from(rules || [])) {
        if (rule.type === CSSRule.STYLE_RULE && rule.style) {
          for (const name of Array.from(rule.style)) {
            if (name.startsWith("--")) cssVariables[name] = rule.style.getPropertyValue(name).trim();
          }
        }
        if (rule.type === CSSRule.MEDIA_RULE) {
          mediaQueries.add(rule.conditionText);
        }
      }
    }

    const fontFaces = Array.from(document.fonts || []).map((font) => ({
      family: font.family,
      weight: font.weight,
      style: font.style,
      status: font.status,
    }));

    const animationsList = (document.getAnimations ? document.getAnimations() : []).slice(0, 50).map((anim) => {
      const timing = anim.effect && anim.effect.getTiming ? anim.effect.getTiming() : {};
      return {
        name: anim.animationName || anim.constructor.name,
        duration: timing.duration,
        iterations: timing.iterations,
        easing: timing.easing,
      };
    });

    return {
      url: location.href,
      title: document.title,
      lang: document.documentElement.lang || null,
      metaDescription: (document.querySelector('meta[name="description"]') || {}).content || null,
      metaViewport: (document.querySelector('meta[name="viewport"]') || {}).content || null,
      favicon: (document.querySelector('link[rel~="icon"]') || {}).href || null,
      colorScheme: {
        dark: window.matchMedia("(prefers-color-scheme: dark)").matches,
        reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      },
      page: {
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      },
      counts: {
        elements: document.querySelectorAll("*").length,
        buttons: document.querySelectorAll("button").length,
        links: document.querySelectorAll("a").length,
        inputs: document.querySelectorAll("input,textarea,select").length,
        images: document.querySelectorAll("img").length,
        svgs: document.querySelectorAll("svg").length,
        videos: document.querySelectorAll("video").length,
        sections: document.querySelectorAll("section").length,
        cards: document.querySelectorAll('[class*="card" i]').length,
        navs: document.querySelectorAll("nav").length,
      },
      tokens: {
        fontFamilies: top(fonts),
        fontSizes: top(sizes),
        fontWeights: top(weights),
        lineHeights: top(lineHeights),
        textColors: top(colors),
        backgroundColors: top(backgrounds),
        borderRadii: top(radii),
        boxShadows: top(shadows),
        paddings: top(paddings),
        margins: top(margins),
        gaps: top(gaps),
        transitions: top(transitions),
        animationNames: top(animations),
        displays: top(displays),
        positions: top(positions),
        cssVariables,
        mediaQueries: Array.from(mediaQueries).slice(0, 40),
        fontFaces: fontFaces.slice(0, 40),
        animations: animationsList,
      },
      keyElements: {
        header: pick("header"),
        nav: pick("nav"),
        h1: pick("h1"),
        h2: pick("h2"),
        p: pick("p"),
        button: pick("button"),
        primaryButton: pick("button, .btn, [class*='button' i]"),
        link: pick("a"),
        input: pick("input"),
        card: pick("[class*='card' i]"),
        image: pick("img"),
        section: pick("section"),
        footer: pick("footer"),
      },
      headings,
      images,
    };
  });
}

async function capture(browser, url, width, args, outDir) {
  const isMobile = width < 600;
  const context = await browser.newContext({
    viewport: { width, height: isMobile ? 844 : 900 },
    deviceScaleFactor: 1,
    isMobile,
    hasTouch: isMobile,
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const failedRequests = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 500));
  });
  page.on("requestfailed", (request) => {
    failedRequests.push({ url: request.url().slice(0, 300), error: request.failure() ? request.failure().errorText : "unknown" });
  });

  let response = null;
  try {
    response = await page.goto(url, { waitUntil: "networkidle", timeout: args.timeout });
  } catch (_) {
    try {
      response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: args.timeout });
    } catch (error) {
      await context.close();
      throw error;
    }
  }
  await page.waitForTimeout(args.wait);

  const label = isMobile ? "mobile" : width < 1100 ? "tablet" : "desktop";
  const base = path.join(outDir, `${label}-${width}`);
  const viewportPath = `${base}-viewport.png`;
  const fullPath = `${base}-full.png`;
  await page.screenshot({ path: viewportPath, fullPage: false });
  if (args.fullPage) await page.screenshot({ path: fullPath, fullPage: true });

  const analysis = await analyzePage(page);
  const result = {
    requestedUrl: url,
    finalUrl: page.url(),
    status: response ? response.status() : null,
    capturedAt: new Date().toISOString(),
    viewport: { width, height: isMobile ? 844 : 900, isMobile },
    screenshots: { viewport: viewportPath, full: args.fullPage ? fullPath : null },
    consoleErrors: consoleErrors.slice(0, 40),
    failedRequests: failedRequests.slice(0, 40),
    ...analysis,
  };
  await context.close();
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { chromium } = loadPlaywright();
  const outDir = path.resolve(args.out || path.join("outputs", `${safeName(args.url)}-probe`));
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await launchBrowser(chromium);
  const results = [];
  try {
    for (const width of args.widths) {
      console.log(`[capture] ${args.url} @ ${width}px`);
      const result = await capture(browser, args.url, width, args, outDir);
      results.push(result);
      const label = width < 600 ? "mobile" : width < 1100 ? "tablet" : "desktop";
      fs.writeFileSync(path.join(outDir, `site-probe-${label}-${width}.json`), JSON.stringify(result, null, 2));
      console.log(`[ok] ${result.status} ${result.title}`);
      console.log(`     viewport: ${result.screenshots.viewport}`);
      if (result.screenshots.full) console.log(`     full: ${result.screenshots.full}`);
    }
  } finally {
    await browser.close();
  }

  fs.writeFileSync(path.join(outDir, "site-probe.json"), JSON.stringify(results, null, 2));
  console.log(`[ok] combined JSON: ${path.join(outDir, "site-probe.json")}`);
}

main().catch((error) => {
  console.error(`[error] ${error && error.stack ? error.stack : error}`);
  process.exit(3);
});
