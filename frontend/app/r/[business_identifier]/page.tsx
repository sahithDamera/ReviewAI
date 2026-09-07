import { PublicReviewFlow } from "@/components/PublicReviewFlow";

export const dynamic = "force-dynamic";

export default async function PublicReviewPage({ params }: { params: Promise<{ business_identifier: string }> }) {
  const { business_identifier } = await params;
  return <PublicReviewFlow identifier={business_identifier} />;
}
