import { useState } from "react";
import { ExperimentList } from "./components/ExperimentList";
import { TaskList } from "./components/TaskList";
import "./App.css";

function App() {
  const [activeTab, setActiveTab] = useState<"experiments" | "tasks">("experiments");

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Dashboard</h1>
        <div className="tab-navigation">
          <button
            className={`tab-button ${activeTab === "experiments" ? "active" : ""}`}
            onClick={() => setActiveTab("experiments")}
          >
            実験一覧
          </button>
          <button
            className={`tab-button ${activeTab === "tasks" ? "active" : ""}`}
            onClick={() => setActiveTab("tasks")}
          >
            タスク一覧
          </button>
        </div>
      </header>
      <main className="app-main">
        {activeTab === "experiments" && <ExperimentList />}
        {activeTab === "tasks" && <TaskList />}
      </main>
    </div>
  );
}

export default App;
