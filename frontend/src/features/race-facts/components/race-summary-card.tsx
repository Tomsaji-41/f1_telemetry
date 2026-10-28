"use client";

import React from "react";
import { Trophy, MapPin, Calendar, CheckCircle2 } from "lucide-react";
import { RaceFacts } from "../types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/primitives/card";
import { Badge } from "@/components/primitives/badge";

interface RaceSummaryCardProps {
  data: RaceFacts;
}

export function RaceSummaryCard({ data }: RaceSummaryCardProps): React.JSX.Element {
  return (
    <Card className="border-red-900/30 bg-gradient-to-br from-slate-900/90 via-slate-950 to-red-950/20">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <Badge variant="f1" className="mb-2">Grand Prix Session</Badge>
            <CardTitle className="text-2xl font-black text-white">{data.event_name}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="cyan" className="px-3 py-1 text-sm">Round {data.round} • {data.year}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-2">
          <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
            <div className="flex items-center gap-2 text-xs text-amber-400 font-semibold mb-1">
              <Trophy className="h-4 w-4" /> Race Winner
            </div>
            <p className="text-lg font-bold text-white tracking-wide">{data.winner}</p>
          </div>

          <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
            <div className="flex items-center gap-2 text-xs text-teal-400 font-semibold mb-1">
              <MapPin className="h-4 w-4" /> Location
            </div>
            <p className="text-sm font-medium text-slate-200 truncate">{data.location}</p>
          </div>

          <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
            <div className="flex items-center gap-2 text-xs text-sky-400 font-semibold mb-1">
              <Calendar className="h-4 w-4" /> Official Date
            </div>
            <p className="text-sm font-medium text-slate-200">{data.official_event_date.split(" ")[0]}</p>
          </div>

          <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
            <div className="flex items-center gap-2 text-xs text-rose-400 font-semibold mb-1">
              <CheckCircle2 className="h-4 w-4" /> Total Laps
            </div>
            <p className="text-lg font-bold text-white">{data.total_laps}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
