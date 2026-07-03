"use client";

import { useEffect, useState } from "react";

const DESKTOP = 1024; // matches the `lg:` breakpoint used in the layout

/**
 * Owns the knowledge-panel open state. Inline on desktop (open by default) but an
 * overlay drawer on mobile (closed by default). Opens when we cross up into the
 * desktop layout and closes when we cross down into mobile, so it never lingers
 * open over the chat. We only act on an actual breakpoint crossing, leaving the
 * user's manual toggles intact between crossings.
 */
export function useResponsivePanel() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let wasDesktop = window.innerWidth >= DESKTOP;
    setOpen(wasDesktop);
    const onResize = () => {
      const isDesktop = window.innerWidth >= DESKTOP;
      if (isDesktop !== wasDesktop) {
        wasDesktop = isDesktop;
        setOpen(isDesktop);
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return [open, setOpen] as const;
}
