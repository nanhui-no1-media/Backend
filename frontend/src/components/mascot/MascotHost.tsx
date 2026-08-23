import { useEffect, useState } from "react";
import "./mascot.css";

const STORAGE_KEY = "mascot.enabled";
const NARROW_MAX = 1024;
const REDUCE_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

type Presentation = "none" | "chip" | "widget";

function readEnabled(): boolean {
  return localStorage.getItem(STORAGE_KEY) !== "off";
}

function writeEnabled(on: boolean): void {
  localStorage.setItem(STORAGE_KEY, on ? "on" : "off");
}

function computePresentation(): Presentation {
  if (window.innerWidth <= NARROW_MAX) return "none";
  if (window.matchMedia(REDUCE_MOTION_QUERY).matches) return "none";
  return readEnabled() ? "widget" : "chip";
}

/**
 * Site-wide 看板娘 host. App.tsx learns only `<MascotHost />`.
 * Three presentations (widget / chip / none); Cubism is lazy and never
 * remounts on hash changes because this host sits outside <Routes>.
 */
export default function MascotHost() {
  const [presentation, setPresentation] = useState<Presentation>(computePresentation);

  useEffect(() => {
    const motionMq = window.matchMedia(REDUCE_MOTION_QUERY);
    const narrowMq = window.matchMedia(`(max-width: ${NARROW_MAX}px)`);
    const sync = () => setPresentation(computePresentation());
    window.addEventListener("resize", sync);
    motionMq.addEventListener("change", sync);
    narrowMq.addEventListener("change", sync);
    window.visualViewport?.addEventListener("resize", sync);
    return () => {
      window.removeEventListener("resize", sync);
      motionMq.removeEventListener("change", sync);
      narrowMq.removeEventListener("change", sync);
      window.visualViewport?.removeEventListener("resize", sync);
    };
  }, []);

  useEffect(() => {
    if (presentation !== "widget") return;
    let cancelled = false;
    let unmount: (() => void) | undefined;

    import(/* webpackChunkName: "mascot-widget" */ "./loadWidget")
      .then((mod) => {
        if (cancelled) return undefined;
        return mod.mountMascotWidget({
          onClose: () => {
            writeEnabled(false);
            setPresentation("chip");
          },
        });
      })
      .then((handle) => {
        if (!handle) return;
        if (cancelled) {
          handle.unmount();
          return;
        }
        unmount = handle.unmount;
      })
      .catch(() => {
        // Catalog / script failure: leave the corner empty this session.
      });

    return () => {
      cancelled = true;
      unmount?.();
    };
  }, [presentation]);

  if (presentation !== "chip") return null;

  return (
    <button
      type="button"
      className="mascot-chip"
      aria-label="看板娘"
      onClick={() => {
        writeEnabled(true);
        setPresentation("widget");
      }}
    >
      看板娘
    </button>
  );
}
