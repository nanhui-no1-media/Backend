import type { ReactNode } from "react";
import AppShell from "./AppShell";
import { useEmbedMode } from "../embed";

/** Skip site chrome when mounted in the review desk or an admin iframe (`?embed=1`). */
export default function PageChrome({
  embedded,
  children,
}: {
  embedded?: boolean;
  children: ReactNode;
}) {
  const urlEmbed = useEmbedMode();
  if (embedded || urlEmbed) return <div className="cs embed-root">{children}</div>;
  return <AppShell>{children}</AppShell>;
}
