import { Navigate, Route, Routes } from "react-router-dom";
import { AppStateProvider } from "./state/AppStateContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Placeholder } from "./pages/Placeholder";

function App() {
  return (
    <AppStateProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Placeholder title="ダッシュボード" />} />
            <Route path="/approvals" element={<Placeholder title="承認キュー" />} />
            <Route path="/documents" element={<Placeholder title="ドキュメント" />} />
            <Route path="/activity" element={<Placeholder title="活動ログ" />} />
            <Route path="/import-export" element={<Placeholder title="Import-Export" />} />
            <Route path="/agent-control" element={<Placeholder title="エージェント制御" />} />
            <Route path="/costs" element={<Placeholder title="コスト" />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppStateProvider>
  );
}

export default App;
