import { useEffect, useRef, useState } from "react";
import { animate } from "framer-motion";

export function useCountUp(target, duration = 0.6) {
  const [display, setDisplay] = useState(target);
  const prevTarget = useRef(target);
  const firstRun = useRef(true);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      prevTarget.current = target;
      setDisplay(target);
      return;
    }
    const controls = animate(prevTarget.current, target, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(v),
    });
    prevTarget.current = target;
    return () => controls.stop();
  }, [target, duration]);

  return display;
}
