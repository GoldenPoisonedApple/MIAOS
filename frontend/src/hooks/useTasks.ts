import { useState, useEffect, useCallback } from "react";
import { apiClient } from "../api/client";
import type { components } from "../api/schema";

type Task = components["schemas"]["Task"];

export const useTasks = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data, error } = await apiClient.GET("/api/tasks");
      if (error) {
        throw new Error(error);
      }
      if (data) {
        setTasks(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch tasks"));
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteTask = async (id: string) => {
    try {
      const { error } = await apiClient.DELETE("/api/tasks/{id}", {
        params: { path: { id } },
      });
      if (error) {
        throw new Error(error);
      }
      await fetchTasks(); // Refresh list after deletion
    } catch (err) {
      console.error(err);
      alert("Failed to delete task");
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return { tasks, loading, error, deleteTask, refetch: fetchTasks };
};
