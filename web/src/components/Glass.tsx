import type { ComponentPropsWithoutRef, ElementType } from "react";

type Props<T extends ElementType> = { as?: T } & Omit<ComponentPropsWithoutRef<T>, "as">;

/** A frosted-glass panel. The only place backdrop-filter is applied, so it stays cheap. */
export function Glass<T extends ElementType = "section">({ as, className = "", ...rest }: Props<T> & { className?: string }) {
  const Tag = (as ?? "section") as ElementType;
  return <Tag className={`glass ${className}`.trim()} {...rest} />;
}

/** Slow drifting colour behind the glass. Transform-only animation. */
export function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}
