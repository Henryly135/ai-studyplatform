import { useEffect, useMemo, useState, type ReactNode } from "react";

import { LocaleContext } from "./locale";
import { localeMessages, LOCALE_STORAGE_KEY, type AppLocale } from "./localeMessages";

function resolveInitialLocale(): AppLocale {
  return "en";
}

function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(() => resolveInitialLocale());

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  const value = useMemo(
    () => ({
      locale,
      setLocale: setLocaleState,
      text: localeMessages[locale],
    }),
    [locale]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export default LocaleProvider;
