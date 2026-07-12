import { useEffect, useRef, useState, ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { setSupersedeHandler, SupersedeTakeover } from "../api/shared";
import { api } from "../api/client";
import SessionSupersedeModal from "./SessionSupersedeModal";

const POLL_INTERVAL_MS = 60000;

export default function SessionGuard({ children }: { children: ReactNode }) {
  const [takeover, setTakeover] = useState<SupersedeTakeover | null>(null);
  const navigate = useNavigate();
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    setSupersedeHandler((t) => {
      setTakeover((prev) => prev ?? t); // idempotent: don't overwrite an already-shown popup
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current); // kicked: stop polling
        intervalRef.current = null;
      }
    });

    intervalRef.current = window.setInterval(() => {
      api.me().catch(() => {}); // supersede 401 is handled by shared.ts interceptor; other errors swallowed
    }, POLL_INTERVAL_MS);

    return () => {
      setSupersedeHandler(null);
      if (intervalRef.current !== null) window.clearInterval(intervalRef.current);
    };
  }, []);

  function handleConfirm() {
    setTakeover(null);
    navigate("/login", { replace: true });
  }

  return (
    <>
      {children}
      <SessionSupersedeModal takeover={takeover} onConfirm={handleConfirm} />
    </>
  );
}
