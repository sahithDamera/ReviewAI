import Link from "next/link";
import { Brand } from "@/components/Brand";

export default function Home() {
  return <main className="mx-auto max-w-6xl px-6 py-8">
    <nav className="flex items-center justify-between"><Brand /><Link href="/login" className="button secondary">Owner login</Link></nav>
    <div className="grid gap-12 py-20 md:grid-cols-[1.2fr_1fr] md:items-center md:py-32">
      <section><p className="eyebrow">Thoughtful feedback. Less effort.</p>
        <h1 className="my-6 text-5xl font-semibold md:text-7xl">Real experiences.<br /><span className="text-[#568264]">In their own words.</span></h1>
        <p className="muted max-w-lg text-lg leading-relaxed">Give your customers a simpler way to share what made their visit theirs. Start by setting up your business.</p>
        <Link href="/signup" className="button mt-9">Create your business account <span aria-hidden>↗</span></Link>
        <p className="muted mt-4 text-sm">One business. A little less friction.</p>
      </section>
      <aside className="panel rotate-1"><div className="mb-8 flex h-14 w-14 items-center justify-center rounded-full bg-[#edf2e7] text-2xl" aria-hidden>✦</div>
        <p className="eyebrow">A good place to start</p><h2 className="mt-4 text-3xl font-semibold">Make room for<br />honest feedback.</h2>
        <ol className="mt-8 space-y-6">{["Create your owner account", "Tell us about your business", "Connect your Google review page"].map((line, index) => <li key={line} className="flex items-center gap-4"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#cbd6c7] text-sm">{index + 1}</span>{line}</li>)}</ol>
        <p className="muted mt-8 border-t border-[#e0e5db] pt-5 text-sm">Customers stay in control of their reviews.</p>
      </aside>
    </div>
  </main>;
}
