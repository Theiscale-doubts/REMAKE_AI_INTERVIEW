import PoweredByIScale from "@/components/PoweredByIScale";

const AUTHOR_NAME = import.meta.env.VITE_AUTHOR_NAME || "";

/**
 * Shared page footer: copyright, the author credit, and the iScale partner
 * mark. Used on every page so the credit line can't drift out of one of them.
 *
 * Layout: stacked and centered on narrow screens, spread across a single row
 * from the `sm` breakpoint up.
 */
export default function SiteFooter({ maxWidth = "max-w-5xl" }: { maxWidth?: string }) {
  return (
    <footer className="border-t border-hairline">
      <div
        className={`${maxWidth} mx-auto px-4 sm:px-7 py-4 sm:py-[18px] flex flex-col items-center gap-2 text-center sm:flex-row sm:justify-between sm:gap-4 sm:text-left text-[12px] sm:text-[13px] text-txt-low`}
      >
        <p>© {new Date().getFullYear()} VoxHire. All rights reserved.</p>
        {AUTHOR_NAME && (
          <p className="text-[9.5px] font-medium uppercase tracking-[0.18em] text-txt-low opacity-65">
            Developed &amp; managed by {AUTHOR_NAME}
          </p>
        )}
        <PoweredByIScale />
      </div>
    </footer>
  );
}
