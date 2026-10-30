import React from "react";
import Link from "next/link";
import { EmptyState } from "@/components/primitives/kit";

export default function CircuitsNotFound(): React.JSX.Element {
  return (
    <div className="p-8 max-w-2xl mx-auto space-y-4">
      <EmptyState
        title="Circuit Not Found"
        message="The requested Formula 1 circuit does not exist in championship records."
      />
      <div className="text-center">
        <Link
          href="/circuits"
          className="inline-block px-4 py-2 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono text-[var(--text)] hover:bg-[var(--surface-2)] transition"
        >
          Return to Circuits Catalog
        </Link>
      </div>
    </div>
  );
}
