import GovernedRulesEditor from "@/components/GovernedRulesEditor";

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-[1300px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-pwc-orange">Business workspace</p>
      <h1 className="mt-1 text-2xl font-bold text-gray-900">Governed Rules</h1>
      <p className="mt-1 max-w-3xl text-sm text-gray-500">
        The business-owned thresholds and escalation actions agents cite instead of inventing one.
        Editing a rule demotes it to draft — activate it to make the change governing again. Every
        change is audited with who made it and why.
      </p>
      <div className="mt-5">
        <GovernedRulesEditor />
      </div>
    </div>
  );
}
