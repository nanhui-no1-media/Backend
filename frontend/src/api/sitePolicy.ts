import { useEffect, useState } from "react";
import { createRequest } from "./shared";

const request = createRequest("");

export interface SitePolicy {
  verification_enabled: boolean;
  registration_enabled: boolean;
  register_per_ip_per_day: number;
  resend_verification_per_ip_per_hour: number;
  feedback_anon_per_ip_per_day: number;
  sync_upload_max_bytes: number;
  tus_media_max_bytes: number;
}

const DEFAULTS: SitePolicy = {
  verification_enabled: true,
  registration_enabled: true,
  register_per_ip_per_day: 5,
  resend_verification_per_ip_per_hour: 5,
  feedback_anon_per_ip_per_day: 10,
  sync_upload_max_bytes: 50 * 1024 * 1024,
  tus_media_max_bytes: 500 * 1024 * 1024,
};

let snapshot: SitePolicy = DEFAULTS;
const listeners = new Set<() => void>();

export function getSitePolicy(): SitePolicy {
  return snapshot;
}

function notify() {
  listeners.forEach((fn) => fn());
}

export function subscribeSitePolicy(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function useSitePolicy(): SitePolicy {
  const [policy, setPolicy] = useState(snapshot);
  useEffect(() => subscribeSitePolicy(() => setPolicy(getSitePolicy())), []);
  return policy;
}

export function fetchSitePolicy(): Promise<void> {
  return request<SitePolicy>("/site-policy/")
    .then((data) => {
      snapshot = { ...DEFAULTS, ...data };
      notify();
    })
    .catch(() => {
      // Keep defaults if the public endpoint is unreachable.
    });
}
