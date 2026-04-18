"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/empty";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="space-y-3">
      <ErrorState
        title="Something went wrong."
        detail={error.message ?? "Unknown error"}
      />
      <button className="btn" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
