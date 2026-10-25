import { useTree } from "../context/TreeContext";
import type { Route } from "../useRoute";

export function Header({ route }: { route: Route }) {
  const { meta } = useTree();
  return (
    <header className="site-header">
      <a className="wordmark" href="#/" aria-label="OCBC Tree, employee view">
        <span className="wm-ocbc">OCBC</span>
        <span className="wm-tree">Tree</span>
      </a>
      <p className="motto">Get to the root of every answer.</p>

      <nav className="nav" aria-label="Views">
        <a href="#/" className={route === "employee" ? "active" : ""} aria-current={route === "employee" ? "page" : undefined}>
          Employee
        </a>
        <a href="#/admin" className={route === "admin" ? "active" : ""} aria-current={route === "admin" ? "page" : undefined}>
          Admin
        </a>
      </nav>

      <div className="badges">
        {meta?.llm_badge && <span className="mock-badge">{meta.llm_badge}</span>}
        {meta && <span className="data-badge">{meta.data_label}</span>}
        {meta && <span className="data-badge">Demo date {meta.demo_date}</span>}
      </div>
    </header>
  );
}
