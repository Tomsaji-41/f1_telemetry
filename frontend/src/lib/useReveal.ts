"use client";

import { useEffect, useRef } from "react";

let sharedObserver: IntersectionObserver | null = null;
const observedElements = new Set<Element>();

function getSharedObserver(): IntersectionObserver | null {
  if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
    return null;
  }
  if (!sharedObserver) {
    sharedObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            observer.unobserve(entry.target);
            observedElements.delete(entry.target);
          }
        });
      },
      {
        threshold: 0.12,
        rootMargin: "0px 0px -8% 0px",
      }
    );
  }
  return sharedObserver;
}

export function useReveal() {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // If browser supports animation-timeline: view(), CSS handles it natively
    if (
      typeof CSS !== "undefined" &&
      CSS.supports &&
      CSS.supports("animation-timeline", "view()")
    ) {
      return;
    }

    // Check reduced-motion
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    const observer = getSharedObserver();
    if (!observer || !containerRef.current) return;

    const targets = containerRef.current.querySelectorAll<HTMLElement>(".reveal");
    targets.forEach((el, idx) => {
      // Set stagger index up to 6
      el.style.setProperty("--i", String(Math.min(idx, 6)));
      if (!observedElements.has(el)) {
        observedElements.add(el);
        observer.observe(el);
      }
    });

    return () => {
      targets.forEach((el) => {
        if (observedElements.has(el)) {
          observer.unobserve(el);
          observedElements.delete(el);
        }
      });
    };
  }, []);

  return containerRef;
}

export default useReveal;

