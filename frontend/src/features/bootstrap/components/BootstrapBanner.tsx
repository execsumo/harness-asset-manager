import { useState } from "react";
import { useBootstrapPlanQuery, useDismissBootstrapMutation } from "../queries";
import { BootstrapReviewSheet } from "./BootstrapReviewSheet";

export function BootstrapBanner() {
  const { data: plan, isLoading } = useBootstrapPlanQuery();
  const dismissMutation = useDismissBootstrapMutation();
  const [reviewOpen, setReviewOpen] = useState(false);

  if (isLoading || !plan || plan.dismissed || plan.linkableCount === 0) {
    return null;
  }

  const count = plan.linkableCount;
  const itemLabel = count === 1 ? "asset" : "assets";

  return (
    <>
      <div
        className="bootstrap-banner"
        role="region"
        aria-label="New device bootstrap"
      >
        <div className="bootstrap-banner__content">
          <span className="bootstrap-banner__icon" aria-hidden="true">
            ✦
          </span>
          <span className="bootstrap-banner__text">
            <strong>New device detected:</strong> {count} {itemLabel} from your
            synced store are ready to bootstrap onto this device.
          </span>
        </div>

        <div className="bootstrap-banner__actions">
          <button
            type="button"
            className="action-pill action-pill--primary"
            onClick={() => setReviewOpen(true)}
          >
            Review &amp; Bootstrap
          </button>
          <button
            type="button"
            className="action-pill"
            onClick={() => dismissMutation.mutate()}
            disabled={dismissMutation.isPending}
            title="Dismiss bootstrap banner on this device"
          >
            Dismiss
          </button>
        </div>
      </div>

      {reviewOpen && (
        <BootstrapReviewSheet
          open={reviewOpen}
          onOpenChange={setReviewOpen}
          plan={plan}
        />
      )}
    </>
  );
}
