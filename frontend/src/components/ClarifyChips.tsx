"use client";

import React, { useEffect } from "react";
import { ChevronRight, X } from "lucide-react";

export interface ClarifyOption {
  label: string;
  value: any;
  action?: string;
  page?: number;
}

interface ClarifyChipsProps {
  options: ClarifyOption[];
  onSelect: (value: any, label: string, action?: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  selectedValue?: any;
  isActiveTurn?: boolean;
}

export function ClarifyChips({
  options,
  onSelect,
  onCancel,
  disabled = false,
  selectedValue,
  isActiveTurn = true,
}: ClarifyChipsProps): React.JSX.Element | null {
  // Keyboard listener: 1-6 pick chips, Esc cancels
  // Hook must run unconditionally — guard is inside the effect
  useEffect(() => {
    // B1: refuse to handle keyboard when fewer than 2 options
    if (!options || options.length < 2) return;
    if (disabled || !isActiveTurn) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
        if (e.key === "Escape" && onCancel) {
          e.preventDefault();
          onCancel();
        }
        return;
      }

      if (e.key === "Escape" && onCancel) {
        e.preventDefault();
        onCancel();
        return;
      }

      const num = parseInt(e.key, 10);
      if (!isNaN(num) && num >= 1 && num <= 6 && num <= options.length) {
        e.preventDefault();
        const chosen = options[num - 1];
        if (chosen) {
          onSelect(chosen.value, chosen.label, chosen.action);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [options, disabled, isActiveTurn, onSelect, onCancel]);

  // B1: The UI must refuse to render a clarification with fewer than 2 options.
  // Early return AFTER all hooks
  if (!options || options.length < 2) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-2">
      {options.map((opt, idx) => {
        const isSelected = selectedValue !== undefined && selectedValue === opt.value;
        const keyNumber = idx < 6 ? idx + 1 : null;
        const isMore = opt.action === "page_more" || opt.label === "More races";
        const isCancel = opt.action === "cancel" || opt.value === "cancel";

        return (
          <button
            key={`${opt.label}-${idx}`}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(opt.value, opt.label, opt.action)}
            className={`text-[12px] h-7 px-2.5 rounded border transition-colors flex items-center gap-1.5 font-medium ${
              isSelected
                ? "bg-[var(--accent)] text-white border-[var(--accent)] font-semibold shadow-sm"
                : isCancel
                ? "border-[var(--border)] bg-[var(--surface)] text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--raised)]"
                : "border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--raised)] hover:border-[var(--border-strong)]"
            } ${disabled && !isSelected ? "opacity-50 cursor-not-allowed" : ""}`}
            style={{ borderRadius: "var(--radius-s)" }}
          >
            {keyNumber && isActiveTurn && !disabled && !isCancel && (
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded bg-[var(--raised)] text-[9px] font-mono text-[var(--text-3)]">
                {keyNumber}
              </span>
            )}
            <span>{opt.label}</span>
            {isMore && <ChevronRight className="h-3 w-3 text-[var(--text-3)]" />}
            {isCancel && <X className="h-3 w-3 text-[var(--text-3)]" />}
          </button>
        );
      })}
    </div>
  );
}
