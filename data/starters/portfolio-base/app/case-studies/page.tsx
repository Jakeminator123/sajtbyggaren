import { CaseStudyList } from "@/components/case-study-list";

export const metadata = {
  title: "",
  description: "",
};

export default function CaseStudiesPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <CaseStudyList />
    </main>
  );
}
