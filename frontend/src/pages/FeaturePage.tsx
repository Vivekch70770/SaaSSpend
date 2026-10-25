
import { Page, Card } from "../ui";

type FeaturePageProps = {
  title: string;
};

const descriptions: Record<string, string> = {
  Licenses: "Track purchased seats, assigned users, and unused licenses.",
  Renewals: "Review upcoming contract renewals and renewal risks.",
  "Shadow IT": "Review applications being used outside approved procurement.",
  Access: "Review application users and access assignments.",
  Security: "Review potential SaaS security and access risks.",
  Reports: "Explore SaaS spending, utilization, and savings reports.",
};

export default function FeaturePage({ title }: FeaturePageProps) {
  return (
    <Page title={title} sub="SaaSSpend management">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">{title} overview</h2>
          <p className="mt-2 text-sm text-stone-500">
            {descriptions[title] ?? "Manage your SaaS operations."}
          </p>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold">Getting started</h2>
          <p className="mt-2 text-sm text-stone-500">
            This page is connected to navigation. Next, we can add working
            tables, forms, and backend data.
          </p>
        </Card>
      </div>
    </Page>
  );
}
