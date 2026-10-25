import { Header } from "./components/Header";
import { useTree } from "./context/TreeContext";
import { useRoute } from "./useRoute";
import { AdminView } from "./views/AdminView";
import { EmployeeView } from "./views/EmployeeView";

export default function App() {
  const route = useRoute();
  const { error } = useTree();
  return (
    <div className="app">
      <Header route={route} />
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {route === "admin" ? <AdminView /> : <EmployeeView />}
    </div>
  );
}
