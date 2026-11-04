import { Outlet } from "react-router-dom";
import { useToast } from "../contexts/ToastContext.jsx";
import NavBar from "./NavBar.jsx";
import Toast from "../components/ui/Toast.jsx";

export default function Layout() {
  const { toasts, dismissToast } = useToast();

  return (
    <>
      <NavBar />
      <Outlet />
      <div className="toast-host" aria-label="Notifications">
        {toasts.map((toast) => (
          <Toast key={toast.id} {...toast} onDismiss={dismissToast} />
        ))}
      </div>
    </>
  );
}
