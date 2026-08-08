import BusinessGlossaryEditor from "@/components/BusinessGlossaryEditor";

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-[1300px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-pwc-orange">Business workspace</p>
      <h1 className="mt-1 text-2xl font-bold text-gray-900">Business Glossary</h1>
      <p className="mt-1 max-w-3xl text-sm text-gray-500">
        Govern the business meaning behind every answer. Edits re-embed into LanceDB so future SQL generation uses the
        updated definition.
      </p>
      <div className="mt-5">
        <BusinessGlossaryEditor />
      </div>
    </div>
  );
}
