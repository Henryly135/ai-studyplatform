export type AppRefreshScope =
  | "admin:educator-requests"
  | "admin:users"
  | "course:catalog"
  | "course:detail"
  | "course:enrollment"
  | "course:managed"
  | "course:materials"
  | "course:progress"
  | "course:quiz"
  | "notifications";

type AppRefreshEventDetail = {
  scope: AppRefreshScope;
  courseUuid?: string;
  moduleUuid?: string;
};

const APP_REFRESH_EVENT = "learning-hub:refresh";

export function emitAppRefresh(detail: AppRefreshEventDetail) {
  window.dispatchEvent(new CustomEvent<AppRefreshEventDetail>(APP_REFRESH_EVENT, { detail }));
}

export function subscribeAppRefresh(
  scopes: AppRefreshScope[],
  callback: (detail: AppRefreshEventDetail) => void
) {
  const scopeSet = new Set(scopes);
  const handler = (event: Event) => {
    const detail = (event as CustomEvent<AppRefreshEventDetail>).detail;
    if (detail && scopeSet.has(detail.scope)) {
      callback(detail);
    }
  };

  window.addEventListener(APP_REFRESH_EVENT, handler);
  return () => window.removeEventListener(APP_REFRESH_EVENT, handler);
}
