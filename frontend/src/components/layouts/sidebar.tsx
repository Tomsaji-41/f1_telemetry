"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Shield,
  Users,
  Trophy,
  MapPin,
  Radio,
  LineChart,
  Zap,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import en from "@/content/en.json";

export function Sidebar(): React.JSX.Element {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  const navItems = [
    { label: en.nav.dashboard, href: "/", icon: LayoutDashboard, pageId: "dashboard" },
    { label: en.nav.constructors, href: "/teams", icon: Shield, pageId: "teams" },
    { label: en.nav.drivers, href: "/drivers", icon: Users, pageId: "drivers" },
    { label: "Circuits", href: "/circuits", icon: MapPin, pageId: "circuits" },
    { label: "Legends", href: "/legends", icon: Trophy, pageId: "legends" },
    { label: en.nav.live, href: "/live-feed", icon: Radio, pageId: "live" },
    { label: en.nav.analytics, href: "/analytics", icon: LineChart, pageId: "analytics" },
    { label: en.nav.teleport, href: "/telemetry", icon: Zap, pageId: "teleport" },
    { label: en.nav.pitboss, href: "/pit-boss", icon: MessageSquare, pageId: "chat" },
  ];

  return (
    <aside
      className={`shrink-0 border-r border-[var(--border)] bg-[var(--surface)] transition-all duration-[var(--dur-2)] ${
        collapsed ? "w-16" : "w-58"
      } hidden md:flex flex-col justify-between p-3 select-none`}
    >
      <div className="space-y-4">
        {/* Toggle Collapse */}
        <div className="flex items-center justify-end">
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--raised)] rounded transition-colors"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation items */}
        <nav aria-label="Modules" className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                data-page={item.pageId}
                aria-current={isActive ? "page" : undefined}
                className={`nav-item flex items-center gap-3 px-2.5 py-2 text-[13px] font-medium rounded transition-colors ${
                  isActive
                    ? "font-semibold"
                    : "text-[var(--text-2)] hover:bg-[var(--raised)] hover:text-[var(--text)]"
                }`}
                title={collapsed ? item.label : undefined}
                style={{ borderRadius: "var(--radius-s)" }}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    isActive ? "text-[var(--accent)]" : "text-[var(--text-3)]"
                  }`}
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Docked Pit Boss Quick-key Indicator */}
      {!collapsed && (
        <div className="p-2 border border-[var(--border)] rounded bg-[var(--raised)] text-[11px] text-[var(--text-3)] flex items-center justify-between">
          <span>Quick Chat</span>
          <kbd className="px-1.5 py-0.5 bg-[var(--surface)] border border-[var(--border)] rounded font-mono text-[10px]">
            Key P
          </kbd>
        </div>
      )}
    </aside>
  );
}
