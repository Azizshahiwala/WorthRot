import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

const ToastContext = createContext(null);
const TOAST_DURATION = 5000;
const TOAST_EXIT_DURATION = 200;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(0);
  const timers = useRef(new Map());

  const removeToast = useCallback((id) => {
    timers.current.delete(id);
    setToasts((currentToasts) => currentToasts.filter((toast) => toast.id !== id));
  }, []);

  const dismissToast = useCallback(
    (id) => {
      const timer = timers.current.get(id);
      if (timer) clearTimeout(timer);
      setToasts((currentToasts) =>
        currentToasts.map((toast) =>
          toast.id === id ? { ...toast, leaving: true } : toast,
        ),
      );
      timers.current.set(
        id,
        setTimeout(() => removeToast(id), TOAST_EXIT_DURATION),
      );
    },
    [removeToast],
  );

  const showToast = useCallback(
    (message, type = "info") => {
      const id = ++nextId.current;
      setToasts((currentToasts) => [
        ...currentToasts,
        { id, message, type, leaving: false },
      ]);
      timers.current.set(
        id,
        setTimeout(() => dismissToast(id), TOAST_DURATION),
      );
    },
    [dismissToast],
  );

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      timers.current.clear();
    },
    [],
  );

  const value = useMemo(
    () => ({ toasts, showToast, dismissToast }),
    [toasts, showToast, dismissToast],
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider.");
  }
  return context;
}
