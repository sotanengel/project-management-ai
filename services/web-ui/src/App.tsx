import { Navigate, Route, Routes } from "react-router-dom";
import { AppStateProvider } from "./state/AppStateContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Approvals } from "./pages/Approvals";
import { ApprovalHistory } from "./pages/ApprovalHistory";
import { DocumentViewer } from "./pages/DocumentViewer";
import { ActivityLog } from "./pages/ActivityLog";
import { EntityEditor } from "./pages/EntityEditor";
import { ImportExport } from "./pages/ImportExport";
import { Placeholder } from "./pages/Placeholder";

function App() {
  return (
    <AppStateProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/approvals/history" element={<ApprovalHistory />} />
            <Route path="/documents" element={<DocumentViewer />} />
            <Route path="/documents/:kind" element={<DocumentViewer />} />
            <Route path="/documents/:kind/:id" element={<DocumentViewer />} />
            <Route path="/edit/:kind/:id" element={<EntityEditor />} />
            <Route path="/activity" element={<ActivityLog />} />
            <Route path="/import-export" element={<ImportExport />} />
            <Route
              path="/agent-control"
              element={<Placeholder title="エージェント制御" />}
            />
            <Route path="/costs" element={<Placeholder title="コスト" />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppStateProvider>
  );
}

export default App;
