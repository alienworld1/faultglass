import { useState } from "react";
export function useMotionTiming(token: "short" | "medium" | "long") {
  const [transition] = useState(() => {
    const style = getComputedStyle(document.documentElement);
    const value = style.getPropertyValue(`--motion-${token}`);
    const numbers = style
      .getPropertyValue("--ease-standard")
      .match(/[\d.]+/g)
      ?.map(Number);
    const ease =
      numbers?.length === 4
        ? (numbers as [number, number, number, number])
        : ("linear" as const);
    return { duration: Number.parseFloat(value) / 1000 || 0, ease };
  });
  return transition;
}
