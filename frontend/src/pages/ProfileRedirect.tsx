import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useLoginModal } from "../components/LoginModalProvider";

/** /profile → /u/<我的id>。需先取 me.id，所以是一个独立组件而不是静态 redirect。 */
export default function ProfileRedirect() {
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();
  useEffect(() => {
    api.me()
      .then((d: any) => navigate(`/u/${d.user.id}`, { replace: true }))
      .catch(() => openLogin());
  }, [navigate, openLogin]);
  return null;
}
