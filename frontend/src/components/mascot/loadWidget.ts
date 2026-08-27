/**
 * Cubism 2 blog-widget adapter. Lives in the "mascot-widget" chunk only.
 * Cubism (`live2d.min.js`) is injected as a script tag so ts-loader never parses it.
 *
 * Models are driven from the local catalog.json via loadlive2d.
 */

const LIVE2D_BASE = "/static/live2d/";
const WIDGET_BASE = `${LIVE2D_BASE}widget/`;
const RUNTIME_JS = `${LIVE2D_BASE}runtime/live2d.min.js`;
const CUBISM5_CORE_JS = `${LIVE2D_BASE}runtime/live2dcubismcore.min.js`;
const CATALOG_URL = `${LIVE2D_BASE}catalog.json`;
const WAIFU_DISPLAY_KEY = "waifu-display";
const SENTINEL_ATTR = "data-mascot-sentinel";

type CatalogModel = { id: string; name: string; entry: string };
type Catalog = { version: number; models: CatalogModel[] };

type Live2dLoader = (canvasId: string, modelPath: string) => void;

declare global {
  interface Window {
    initWidget?: (config: {
      waifuPath: string;
      apiPath?: string;
      cubism2Path?: string;
      cubism5Path?: string;
      tools?: string[];
    }) => void;
    loadlive2d?: Live2dLoader;
  }
}

export type MountMascotWidgetOptions = {
  onClose: () => void;
};

export type MascotWidgetHandle = {
  unmount: () => void;
};

let scriptsPromise: Promise<void> | null = null;

function loadCss(href: string): Promise<void> {
  if (document.querySelector(`link[href="${href}"]`)) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.onload = () => resolve();
    link.onerror = () => reject(new Error(`Failed to load ${href}`));
    document.head.appendChild(link);
  });
}

function loadScript(src: string, module = false): Promise<void> {
  if (document.querySelector(`script[src="${src}"]`)) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = false;
    if (module) script.type = "module";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

function ensureScripts(): Promise<void> {
  if (!scriptsPromise) {
    scriptsPromise = Promise.all([
      loadCss(`${WIDGET_BASE}waifu.css`),
      loadScript(RUNTIME_JS),
      loadScript(CUBISM5_CORE_JS),
      loadScript(`${WIDGET_BASE}waifu-tips.js`, true),
    ]).then(() => undefined);
  }
  return scriptsPromise;
}

function modelUrl(entry: string): string {
  return `${LIVE2D_BASE}${entry}`;
}

/** Cubism sample tapEvent reads these arrays; most demo packs omit them and throw on click. */
const FALLBACK_HIT_AREAS_CUSTOM = {
  head_x: [-0.35, 0.6],
  head_y: [0.19, -0.2],
  body_x: [-0.3, -0.25],
  body_y: [0.3, -0.9],
};

export function fillHitAreasCustom(data: unknown): unknown {
  if (!data || typeof data !== "object") return data;
  const rec = data as Record<string, unknown>;
  if (typeof rec.model !== "string" || !Array.isArray(rec.textures)) return data;
  if (rec.hit_areas_custom != null) return data;
  rec.hit_areas_custom = { ...FALLBACK_HIT_AREAS_CUSTOM };
  return data;
}

function installHitAreasFallback(): () => void {
  const original = JSON.parse.bind(JSON);
  const wrapped = ((text: string, reviver?: (this: unknown, key: string, value: unknown) => unknown) =>
    fillHitAreasCustom(original(text, reviver as never))) as typeof JSON.parse;
  JSON.parse = wrapped;
  return () => {
    if (JSON.parse === wrapped) JSON.parse = original;
  };
}

function removeStockNodes(): void {
  document.getElementById("waifu")?.remove();
  document.getElementById("waifu-toggle")?.remove();
  document.querySelector(`[${SENTINEL_ATTR}]`)?.remove();
}

/** Keep #waifu-tips so leftover stock intervals/listeners do not throw after unmount. */
function placeTipsSentinel(): void {
  if (document.getElementById("waifu-tips")) return;
  const sentinel = document.createElement("div");
  sentinel.id = "waifu-tips";
  sentinel.hidden = true;
  sentinel.setAttribute(SENTINEL_ATTR, "1");
  document.body.appendChild(sentinel);
}

function loadCatalogModel(loader: Live2dLoader, entry: string): void {
  loader("live2d", modelUrl(entry));
}

export async function mountMascotWidget(
  options: MountMascotWidgetOptions,
): Promise<MascotWidgetHandle> {
  await ensureScripts();

  const catalog: Catalog = await fetch(CATALOG_URL).then((res) => {
    if (!res.ok) throw new Error(`catalog.json ${res.status}`);
    return res.json();
  });
  const models = catalog.models;
  if (!models?.length) {
    throw new Error("catalog.json has no models");
  }

  if (typeof window.initWidget !== "function" || typeof window.loadlive2d !== "function") {
    throw new Error("Live2D widget globals missing after script injection");
  }

  const restoreJsonParse = installHitAreasFallback();

  removeStockNodes();
  localStorage.removeItem(WAIFU_DISPLAY_KEY);

  let index = 0;
  const origLoadlive2d = window.loadlive2d.bind(window);
  window.loadlive2d = (canvasId: string, path: string) => {
    if (typeof path === "string" && path.includes(`${LIVE2D_BASE}models/`)) {
      origLoadlive2d(canvasId, path);
      return;
    }
    const entry = models[index]?.entry ?? models[0].entry;
    origLoadlive2d(canvasId, modelUrl(entry));
  };

  window.initWidget({
    waifuPath: `${WIDGET_BASE}waifu-tips.json`,
    cubism2Path: RUNTIME_JS,
    cubism5Path: CUBISM5_CORE_JS,
    tools: ["hitokoto", "switch-model", "photo", "info", "quit"],
  });

  document.getElementById("waifu-toggle")?.setAttribute("hidden", "");

  loadCatalogModel(origLoadlive2d, models[0].entry);

  // Capture on document so we run before stock span listeners and so SVG
  // hits inside the icons still match. stopPropagation keeps waifu-display idle.
  const onToolClick = (event: Event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("#waifu-tool-switch-model")) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      index = (index + 1) % models.length;
      loadCatalogModel(origLoadlive2d, models[index].entry);
      return;
    }
    if (target.closest("#waifu-tool-quit")) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      localStorage.removeItem(WAIFU_DISPLAY_KEY);
      options.onClose();
    }
  };
  document.addEventListener("click", onToolClick, true);

  let unmounted = false;
  return {
    unmount: () => {
      if (unmounted) return;
      unmounted = true;
      document.removeEventListener("click", onToolClick, true);
      window.loadlive2d = origLoadlive2d;
      restoreJsonParse();
      removeStockNodes();
      placeTipsSentinel();
      localStorage.removeItem(WAIFU_DISPLAY_KEY);
    },
  };
}
