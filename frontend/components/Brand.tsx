import Link from "next/link";

export function Brand() {
  return <Link href="/" aria-label="ReviewFlow home" className="flex items-center gap-2 text-xl font-bold no-underline"><span aria-hidden className="rounded-xl bg-[#236b52] px-3 py-1.5 text-white">r<span className="text-[#c8dfaa]">.</span></span>ReviewFlow<span className="self-start text-[10px] text-[#668173]">AI</span></Link>;
}
