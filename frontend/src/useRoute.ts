import { useEffect, useState } from "react";

export type Route = "employee" | "admin";

const read = (): Route => (window.location.hash.startsWith("#/admin") ? "admin" : "employee");

/** Two views, no router dependency: #/ is the employee chat, #/admin is the backend inspector. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
