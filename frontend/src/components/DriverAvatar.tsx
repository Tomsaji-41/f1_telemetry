"use client";

import React, { useState } from "react";

export interface DriverAvatarProps {
  headshotUrl?: string | null;
  name: string;
  teamColor?: string;
  className?: string;
  size?: number; // in pixels, default 48
}

export function DriverAvatar({
  headshotUrl,
  name,
  teamColor = "var(--accent)",
  className = "",
  size = 48,
}: DriverAvatarProps): React.JSX.Element {
  const [imageFailed, setImageFailed] = useState(false);

  const monogram = (name || "DR")
    .split(" ")
    .filter(Boolean)
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "D";

  if (!headshotUrl || imageFailed) {
    return (
      <div
        data-testid="driver-avatar-initials"
        className={`rounded-full flex items-center justify-center font-bold font-mono border border-[var(--border)] shrink-0 select-none ${className}`}
        style={{
          width: size,
          height: size,
          backgroundColor: "var(--raised)",
          color: teamColor,
          fontSize: Math.max(10, Math.round(size * 0.32)),
        }}
        title={name}
      >
        {monogram}
      </div>
    );
  }

  return (
    <img
      src={headshotUrl}
      alt={name}
      loading="lazy"
      decoding="async"
      width={size}
      height={size}
      data-testid="driver-avatar-img"
      className={`rounded-full object-cover border border-[var(--border)] bg-[var(--surface-2)] shrink-0 ${className}`}
      style={{
        width: size,
        height: size,
      }}
      onError={() => setImageFailed(true)}
    />
  );
}

export default DriverAvatar;

