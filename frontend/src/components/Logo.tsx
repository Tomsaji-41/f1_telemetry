"use client";

/**
 * Logo component — renders the app logo from brand.ts.
 * Uses next/image for optimized loading with fixed aspect ratio.
 */
import Image from "next/image";
import { brand } from "@/config/brand";

interface LogoProps {
  height?: number;
  className?: string;
}

export function Logo({ height = 28, className }: LogoProps) {
  const width = Math.round(height * brand.logoRatio);
  return (
    <Image
      src={brand.logo}
      alt={brand.appName}
      width={width}
      height={height}
      className={className}
      priority
      style={{ height, width: "auto", objectFit: "contain" }}
    />
  );
}
