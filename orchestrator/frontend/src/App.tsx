import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { ExperimentList } from "./pages/Experiments/ExperimentList";
import { TaskList } from "./pages/Tasks/TaskList";
import { FilterList } from "./pages/Filters/FilterList";
import "./App.css"; // We will remove this later or keep global styles here

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/experiments" replace />} />
          <Route path="experiments" element={<ExperimentList />} />
          <Route path="tasks" element={<TaskList />} />
          <Route path="filters" element={<FilterList />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
