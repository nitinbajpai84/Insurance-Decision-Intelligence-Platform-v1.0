import { Suspense } from "react";
import AIIntelligenceV2 from "@/components/AIIntelligenceV2";

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto w-full max-w-[1500px] px-6 py-10 text-sm text-gray-400">Loading AI Intelligence…</div>}>
      <AIIntelligenceV2 />
    </Suspense>
  );
}
