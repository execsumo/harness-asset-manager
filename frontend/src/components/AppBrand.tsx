/* Sidebar lockup. Drawn inline rather than loaded from
 * assets/harness_asset_manager_logo.svg so the brackets inherit the current
 * theme's text colour while the square keeps the fixed brand amber. */
export function AppBrand() {
  return (
    <span className="app-brand">
      <svg
        className="app-brand__mark"
        viewBox="0 0 46 31"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M 2 0 L 14 0 L 14 5 L 5 5 L 5 26 L 14 26 L 14 31 L 2 31 L 0 29 L 0 2 Z"
          fill="currentColor"
        />
        <rect x="17" y="10" width="12" height="12" rx="2.5" fill="#fbbf24" />
        <path
          d="M 0 0 L 12 0 L 14 2 L 14 29 L 12 31 L 0 31 L 0 26 L 9 26 L 9 5 L 0 5 Z"
          fill="currentColor"
          transform="translate(32, 0)"
        />
      </svg>
      <span className="app-brand__wordmark">HarnessAM</span>
    </span>
  );
}
