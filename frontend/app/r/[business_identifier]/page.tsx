import { PublicReviewFlow } from "@/components/PublicReviewFlow";

export const dynamic = "force-dynamic";

export default async function PublicReviewPage({ params, searchParams }: { params: Promise<{ business_identifier: string }>; searchParams: Promise<{ source?: string }> }) {
  const { business_identifier } = await params;
  const query = await searchParams;
  return <PublicReviewFlow identifier={business_identifier} entrySource={query.source === "qr" ? "qr" : "direct"} />;
}
