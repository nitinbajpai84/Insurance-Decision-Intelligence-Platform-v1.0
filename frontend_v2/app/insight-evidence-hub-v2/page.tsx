import { Suspense } from "react";
import InsightEvidenceHubV2 from "@/components/InsightEvidenceHubV2";

export default function Page() {
  return (
    <Suspense
      fallback={<div className="mx-auto w-full max-w-[1500px] px-6 py-10 text-sm text-gray-400">Loading Evidence Hub…</div>}
    >
      <InsightEvidenceHubV2 />
    </Suspense>
  );
}
