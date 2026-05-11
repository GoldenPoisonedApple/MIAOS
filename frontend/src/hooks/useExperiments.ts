import { useState, useEffect, useCallback } from "react";
import { apiClient } from "../api/client";
import type { components } from "../api/schema";

type Experiment = components["schemas"]["Model"];

export const useExperiments = () => {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchExperiments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data, error } = await apiClient.GET("/api/experiments");
      if (error) {
        throw new Error(error);
      }
      if (data) {
        setExperiments(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch experiments"));
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteExperiment = async (id: number) => {
    try {
      const { error } = await apiClient.DELETE("/api/experiments/{id}", {
        params: { path: { id } },
      });
      if (error) {
        throw new Error(error);
      }
      await fetchExperiments(); // Refresh list after deletion
    } catch (err) {
      console.error(err);
      alert("Failed to delete experiment");
    }
  };

  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  return { experiments, loading, error, deleteExperiment, refetch: fetchExperiments };
};
