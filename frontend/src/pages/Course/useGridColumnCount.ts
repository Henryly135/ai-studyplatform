import { useEffect, useState, type RefObject } from "react";

function countGridColumns(node: HTMLElement) {
  const templateColumns = window.getComputedStyle(node).gridTemplateColumns;

  if (!templateColumns || templateColumns === "none") {
    return 0;
  }

  return templateColumns.split(" ").filter(Boolean).length;
}

function scheduleAnimationFrame(callback: () => void) {
  if (typeof window === "undefined") {
    callback();
    return 0;
  }

  return window.requestAnimationFrame(callback);
}

function cancelScheduledAnimationFrame(frameId: number) {
  if (typeof window === "undefined" || frameId === 0) {
    return;
  }

  window.cancelAnimationFrame(frameId);
}

export function useGridColumnCount(ref: RefObject<HTMLElement | null>) {
  const [columnCount, setColumnCount] = useState(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return undefined;
    }

    let frameId = 0;

    const updateColumnCount = () => {
      setColumnCount((current) => {
        const next = countGridColumns(node);
        return current === next ? current : next;
      });
    };

    const scheduleUpdate = () => {
      cancelScheduledAnimationFrame(frameId);
      frameId = scheduleAnimationFrame(updateColumnCount);
    };

    scheduleUpdate();

    const observer = new ResizeObserver(() => {
      scheduleUpdate();
    });

    observer.observe(node);

    return () => {
      observer.disconnect();
      cancelScheduledAnimationFrame(frameId);
    };
  }, [ref]);

  return columnCount;
}
