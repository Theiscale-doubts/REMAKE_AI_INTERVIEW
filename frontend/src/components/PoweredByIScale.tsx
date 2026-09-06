import { useState } from "react";

/**
 * "Powered by iScale" partner mark. Renders the real logo from
 * /iscale-logo.png (drop the file in client/public); falls back to a
 * text wordmark if the asset is missing. Logo is red-on-transparent —
 * renders directly on the dark background, no chip behind it.
 */
export default function PoweredByIScale({ className = "" }: { className?: string }) {
  const [imgOk, setImgOk] = useState(true);
  return (
    <span className={`inline-flex items-center gap-2 text-[9.5px] font-medium uppercase tracking-[0.18em] text-txt-low opacity-65 ${className}`}>
      Powered by
      {imgOk ? (
        <img
          src="/iscale-logo.png"
          alt="The iScale"
          className="h-4 w-auto"
          onError={() => setImgOk(false)}
        />
      ) : (
        <span className="font-semibold text-txt-mid normal-case tracking-normal">The iScale</span>
      )}
    </span>
  );
}
