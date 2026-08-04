type ScopedCourseChatLoadOptions<T> = {
  load: () => Promise<T>;
  isCurrent: () => boolean;
  onSuccess: (value: T) => void;
  onError: (error: unknown) => void;
  onSettled: () => void;
};

export async function runScopedCourseChatLoad<T>({
  load,
  isCurrent,
  onSuccess,
  onError,
  onSettled,
}: ScopedCourseChatLoadOptions<T>) {
  try {
    const value = await load();
    if (!isCurrent()) {
      return;
    }
    onSuccess(value);
  } catch (error) {
    if (!isCurrent()) {
      return;
    }
    onError(error);
  } finally {
    if (isCurrent()) {
      onSettled();
    }
  }
}

type ScopedCourseChatSendOptions<TResponse, TRefresh> = {
  send: () => Promise<TResponse>;
  refresh: (response: TResponse) => Promise<TRefresh>;
  isCurrent: () => boolean;
  onSuccess: (response: TResponse, refreshedValue: TRefresh) => void;
  onError: (error: unknown) => void;
  onSettled: () => void;
};

export async function runScopedCourseChatSend<TResponse, TRefresh>({
  send,
  refresh,
  isCurrent,
  onSuccess,
  onError,
  onSettled,
}: ScopedCourseChatSendOptions<TResponse, TRefresh>) {
  try {
    const response = await send();
    if (!isCurrent()) {
      return;
    }
    const refreshedValue = await refresh(response);
    if (!isCurrent()) {
      return;
    }
    onSuccess(response, refreshedValue);
  } catch (error) {
    if (!isCurrent()) {
      return;
    }
    onError(error);
  } finally {
    if (isCurrent()) {
      onSettled();
    }
  }
}
