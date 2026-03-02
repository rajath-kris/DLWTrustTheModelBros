import { Outlet, Route, Routes } from "react-router-dom";
import { CourseProvider } from "./context/CourseContext";
import { BrainStateProvider } from "./context/BrainStateContext";
import { AppSidebar } from "./components/AppSidebar";
import {
  MissionControlPage,
  KnowledgeGapsPage,
  SchedulePage,
  StudyPlannerPage,
  DocumentHubPage,
  SessionHistoryPage,
  AskSentinelPage,
  QuizPage,
  PreferencesPage,
} from "./pages";

function Layout() {
  return (
    <div className="app-layout">
      <AppSidebar />
      <main className="app-main">
        <div className="page-fade-wrap">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrainStateProvider>
      <CourseProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<MissionControlPage />} />
            <Route path="gaps" element={<KnowledgeGapsPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="planner" element={<StudyPlannerPage />} />
            <Route path="documents" element={<DocumentHubPage />} />
            <Route path="history" element={<SessionHistoryPage />} />
            <Route path="ask" element={<AskSentinelPage />} />
            <Route path="quiz" element={<QuizPage />} />
            <Route path="preferences" element={<PreferencesPage />} />
          </Route>
        </Routes>
      </CourseProvider>
    </BrainStateProvider>
  );
}
