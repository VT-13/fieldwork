"use client";
import { useEffect } from "react";
export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const unload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    const navigate = (e: MouseEvent) => {
      const target =
        e.target instanceof Element ? e.target.closest("a[href]") : null;
      if (
        target instanceof HTMLAnchorElement &&
        target.target !== "_blank" &&
        !(
          target.pathname === window.location.pathname &&
          target.search === window.location.search
        ) &&
        target.href !== window.location.href &&
        !window.confirm("Leave this page and discard your unsaved edits?")
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", navigate, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", navigate, true);
    };
  }, [dirty]);
}
