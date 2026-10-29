"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";

export function IntroSplash(): React.JSX.Element | null {
  const [visible, setVisible] = useState(false);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    try {
      const alreadyShown = sessionStorage.getItem("telemetra_intro_shown");
      if (!alreadyShown) {
        setVisible(true);
        sessionStorage.setItem("telemetra_intro_shown", "true");

        // Hold for 800ms, then trigger 1.8s fade out
        const fadeTimer = setTimeout(() => {
          setFading(true);
        }, 800);

        // Remove from DOM after 800ms + 1800ms = 2600ms
        const removeTimer = setTimeout(() => {
          setVisible(false);
        }, 2600);

        return () => {
          clearTimeout(fadeTimer);
          clearTimeout(removeTimer);
        };
      }
    } catch {
      // If sessionStorage fails (e.g. strict privacy mode), do not block UI
      setVisible(false);
    }
  }, []);

  if (!visible) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#15151E] pointer-events-none transition-opacity duration-[1800ms] ease-out ${
        fading ? "opacity-0" : "opacity-100"
      }`}
    >
      <div className="flex flex-col items-center gap-4 animate-in fade-in zoom-in-95 duration-700">
        <div className="relative w-28 h-28 sm:w-36 sm:h-36">
          <Image
            src="/brand/logo-transparent.png"
            alt="Telemetra"
            fill
            priority
            sizes="144px"
            className="object-contain"
          />
        </div>
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-wider text-white font-heading uppercase">
            Telemetra
          </h1>
          <p className="text-xs tracking-widest text-[#9E9EB0] uppercase font-mono mt-1">
            Formula 1 Telemetry & Strategy
          </p>
        </div>
      </div>
    </div>
  );
}

