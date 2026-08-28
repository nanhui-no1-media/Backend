import { useEffect, useState } from "react";
import { createRequest } from "./shared";

const request = createRequest("");

export interface SitePolicy {
  verification_enabled: boolean;
  content_review_enabled: boolean;
  registration_enabled: boolean;
  register_per_ip_per_day: number;
  resend_verification_per_ip_per_hour: number;
  login_per_ip_per_hour: number;
  login_per_username_per_hour: number;
  feedback_anon_per_ip_per_day: number;
  reports_per_user_per_day: number;
  sync_upload_max_bytes: number;
  tus_media_max_bytes: number;
  auto_update_enabled: boolean;
  update_poll_interval_seconds: number;
  update_timezone: string;
  update_window_start_hour: number;
  update_window_end_hour: number;
  update_apply_cutoff_minutes_before_end: number;
  update_release_keep: number;
  update_db_backup_keep: number;
  comment_max_depth: number;
}

const DEFAULTS: SitePolicy = {
  verification_enabled: true,
  content_review_enabled: true,
  registration_enabled: true,
  register_per_ip_per_day: 5,
  resend_verification_per_ip_per_hour: 5,
  login_per_ip_per_hour: 30,
  login_per_username_per_hour: 10,
  feedback_anon_per_ip_per_day: 10,
  reports_per_user_per_day: 10,
  sync_upload_max_bytes: 50 * 1024 * 1024,
  tus_media_max_bytes: 500 * 1024 * 1024,
  auto_update_enabled: true,
  update_poll_interval_seconds: 900,
  update_timezone: "Asia/Shanghai",
  update_window_start_hour: 1,
  update_window_end_hour: 3,
  update_apply_cutoff_minutes_before_end: 30,
  update_release_keep: 3,
  update_db_backup_keep: 5,
  comment_max_depth: 8,
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
