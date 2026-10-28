"use client";

/**
 * Plot.tsx — uPlot wrapper with synced cursor, resize observer, and band painting.
 * Every canvas chart uses this component.
 */
import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { cssVar } from "@/lib/css";

export interface PlotSeries {
  label: string;
  colour: string;
  dash?: boolean;
}

export interface PlotBand {
  bits: number[];
  colour: string;
}

interface PlotProps {
  x: number[];
  ys: (number | null)[][];
  series: PlotSeries[];
  syncKey?: string;
  height?: number;
  xLabel?: string;
  yLabel?: string;
  bands?: PlotBand[];
  step?: boolean;
  invertY?: boolean;
}

function paintBands(u: uPlot, b: PlotBand) {
  const { ctx } = u;
  const { left, top, width, height } = u.bbox;
  ctx.save();
  ctx.fillStyle = b.colour;
  let start: number | null = null;
  for (let i = 0; i < b.bits.length; i++) {
    if (b.bits[i] && start === null) start = i;
    if ((!b.bits[i] || i === b.bits.length - 1) && start !== null) {
      const x0 = u.valToPos(u.data[0][start], "x", true);
      const x1 = u.valToPos(u.data[0][i], "x", true);
      ctx.fillRect(x0, top, Math.max(1, x1 - x0), height);
      start = null;
    }
  }
  ctx.restore();
}

export default function Plot({
  x,
  ys,
  series,
  syncKey = "default",
  height = 180,
  xLabel,
  yLabel,
  bands,
  step,
  invertY,
}: PlotProps) {
  const host = useRef<HTMLDivElement>(null);
  const inst = useRef<uPlot | null>(null);

  useEffect(() => {
    if (!host.current || !x?.length) return;

    const grid = cssVar("--border");
    const txt = cssVar("--text-3");
    const mono = `12px ${cssVar("--font-num") || "monospace"}`;

    const opts: uPlot.Options = {
      width: host.current.clientWidth || 640,
      height,
      cursor: {
        sync: { key: syncKey },
        drag: { x: true, y: false },
      },
      scales: {
        x: { time: false },
        y: invertY ? { dir: -1 as const } : {},
      },
      legend: { show: false },
      axes: [
        {
          stroke: txt,
          font: mono,
          grid: { stroke: grid, width: 1 },
          label: xLabel,
          labelFont: mono,
        },
        {
          stroke: txt,
          font: mono,
          grid: { stroke: grid, width: 1 },
          label: yLabel,
          labelFont: mono,
          size: 56,
        },
      ],
      series: [
        {},
        ...series.map((s) => ({
          label: s.label,
          stroke: s.colour,
          width: 1.5,
          dash: s.dash ? [6, 4] : undefined,
          spanGaps: false,
          points: { show: false },
          paths: step
            ? uPlot.paths.stepped!({ align: 1 })
            : undefined,
        })),
      ],
      hooks: {
        drawClear: [
          (u: uPlot) => {
            bands?.forEach((b) => paintBands(u, b));
          },
        ],
      },
    };

    inst.current = new uPlot(
      opts,
      [x, ...ys] as uPlot.AlignedData,
      host.current
    );

    const ro = new ResizeObserver(() => {
      if (host.current && inst.current) {
        inst.current.setSize({
          width: host.current.clientWidth,
          height,
        });
      }
    });
    ro.observe(host.current);

    // Double-click to reset zoom
    const el = host.current;
    const handleDblClick = () => {
      inst.current?.setScale("x", {
        min: x[0],
        max: x[x.length - 1],
      });
    };
    el.addEventListener("dblclick", handleDblClick);

    return () => {
      el.removeEventListener("dblclick", handleDblClick);
      ro.disconnect();
      inst.current?.destroy();
      inst.current = null;
    };
  }, [x, ys, series, height, syncKey, xLabel, yLabel, bands, step, invertY]);

  return (
    <div
      ref={host}
      style={{ width: "100%", minHeight: height }}
    />
  );
}
