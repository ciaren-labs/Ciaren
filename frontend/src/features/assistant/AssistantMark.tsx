/** The assistant's mark: two inputs wired into one node, drawn like the canvas. */
export function AssistantMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path
        d="M7.5 6.5c4.5 0 4 5.5 9 5.5M7.5 17.5c4.5 0 4-5.5 9-5.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        opacity=".7"
      />
      <circle cx="5" cy="6.5" r="2.6" fill="currentColor" />
      <circle cx="5" cy="17.5" r="2.6" fill="currentColor" />
      <circle
        cx="18.6"
        cy="12"
        r="3.2"
        fill="currentColor"
        stroke="currentColor"
        strokeWidth="1.2"
      />
    </svg>
  );
}
