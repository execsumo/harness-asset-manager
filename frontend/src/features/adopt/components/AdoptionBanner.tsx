import { useState } from "react";
import { useAdoptionPlanQuery, useDismissAdoptionMutation } from "../queries";
import { AdoptionReviewSheet } from "./AdoptionReviewSheet";

export function AdoptionBanner() {
  const { data: plan, isLoading } = useAdoptionPlanQuery();
  const dismissMutation = useDismissAdoptionMutation();
  const [reviewOpen, setReviewOpen] = useState(false);

  if (isLoading || !plan || plan.dismissed || plan.linkableCount === 0) {
    return null;
  }

  const count = plan.linkableCount;
  const itemLabel = count === 1 ? "asset" : "assets";

  return (
    <>
      <div
        className="adoption-banner"
        role="region"
        aria-label="New device adoption"
      >
        <div className="adoption-banner__content">
          <span className="adoption-banner__icon" aria-hidden="true">
            ✦
          </span>
          <span className="adoption-banner__text">
            <strong>New device detected:</strong> {count} {itemLabel} from your
            synced store can be adopted into your local harnesses.
          </span>
        </div>

        <div className="adoption-banner__actions">
          <button
            type="button"
            className="action-pill action-pill--primary"
            onClick={() => setReviewOpen(true)}
          >
            Review &amp; Adopt
          </button>
          <button
            type="button"
            className="action-pill"
            onClick={() => dismissMutation.mutate()}
            disabled={dismissMutation.isPending}
            title="Dismiss adoption banner on this device"
          >
            Dismiss
          </button>
        </div>
      </div>

      {reviewOpen && (
        <AdoptionReviewSheet
          open={reviewOpen}
          onOpenChange={setReviewOpen}
          plan={plan}
        />
      )}
    </>
  );
}
