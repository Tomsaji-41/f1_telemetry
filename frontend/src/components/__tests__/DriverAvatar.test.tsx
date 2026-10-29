import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DriverAvatar } from "../DriverAvatar";

describe("DriverAvatar", () => {
  it("renders image tag when headshotUrl is provided", () => {
    render(
      <DriverAvatar
        headshotUrl="https://example.com/headshots/ver.png"
        name="Max Verstappen"
        teamColor="#3671C6"
      />
    );

    const img = screen.getByTestId("driver-avatar-img") as HTMLImageElement;
    expect(img).toBeDefined();
    expect(img.src).toBe("https://example.com/headshots/ver.png");
    expect(img.alt).toBe("Max Verstappen");
  });

  it("renders monogram initials avatar when headshotUrl is missing", () => {
    render(
      <DriverAvatar
        headshotUrl={null}
        name="Yuki Tsunoda"
        teamColor="#6692FF"
      />
    );

    const avatar = screen.getByTestId("driver-avatar-initials");
    expect(avatar).toBeDefined();
    expect(avatar.textContent).toBe("YT");
    expect(avatar.style.color).toBe("rgb(102, 146, 255)");
  });

  it("falls back to initials avatar when image fails to load (onError triggered)", () => {
    render(
      <DriverAvatar
        headshotUrl="https://example.com/broken-headshot.png"
        name="Arvid Lindblad"
        teamColor="#3671C6"
      />
    );

    const img = screen.getByTestId("driver-avatar-img");
    expect(img).toBeDefined();

    // Trigger broken image load
    fireEvent.error(img);

    // Image should now be gone, and initials avatar should be rendered
    expect(screen.queryByTestId("driver-avatar-img")).toBeNull();
    const initials = screen.getByTestId("driver-avatar-initials");
    expect(initials).toBeDefined();
    expect(initials.textContent).toBe("AL");
  });
});

