/**
 * React Hook: useClaudeUsageTracker
 * Custom hook for consuming the Claude Usage Tracker API
 * Provides usage statistics, cost tracking, and project analytics
 */

import { useState, useEffect, useCallback } from 'react';

/**
 * Usage statistics returned from the API
 */
export interface UsageStats {
  totalRequests: number;
  totalTokens: number;
  totalCost: number;
  monthlySpend: number;
  monthlyBudget: number;
  batchRequests: number;
  regularRequests: number;
  topModels: Array<{ modelId: string; requests: number; cost: number }>;
  topTaskTypes: Array<{ taskType: string; requests: number; cost: number }>;
  costBreakdown: Record<string, number>;
}

/**
 * Project statistics
 */
export interface ProjectStats {
  projectId: string;
  totalRequests: number;
  totalCost: number;
  monthlySpend: number;
  monthlyBudget: number;
  costTrend: Array<{ date: string; cost: number }>;
  modelDistribution: Record<string, number>;
}

/**
 * Cost breakdown by model
 */
export interface ModelCostBreakdown {
  [modelId: string]: {
    requests: number;
    tokens: number;
    cost: number;
  };
}

/**
 * Hook return type
 */
export interface UseClaudeUsageTrackerReturn {
  // Data
  monthlyStats: UsageStats | null;
  projectStats: ProjectStats | null;
  costByModel: ModelCostBreakdown | null;
  batchSavings: number | null;

  // Loading states
  loading: boolean;
  monthlyLoading: boolean;
  projectLoading: boolean;

  // Errors
  error: string | null;

  // Actions
  recordUsage: (
    projectId: string,
    taskType: string,
    modelId: string,
    inputTokens: number,
    outputTokens: number,
    isBatch: boolean,
    durationMs: number
  ) => Promise<void>;
  loadMonthlyStats: () => Promise<void>;
  loadProjectStats: (projectId: string) => Promise<void>;
  loadCostBreakdown: () => Promise<void>;
  loadBatchSavings: () => Promise<void>;
  setProjectBudget: (projectId: string, budgetUSD: number) => Promise<void>;
  generateReport: (projectId?: string) => Promise<string>;

  // Computed values
  budgetUsagePercent: number;
  isOverBudget: boolean;
  budgetRemaining: number;
}

/**
 * Custom hook for Claude Usage Tracker
 */
export function useClaudeUsageTracker(
  apiBaseUrl: string = 'http://localhost:3000'
): UseClaudeUsageTrackerReturn {
  // Data state
  const [monthlyStats, setMonthlyStats] = useState<UsageStats | null>(null);
  const [projectStats, setProjectStats] = useState<ProjectStats | null>(null);
  const [costByModel, setCostByModel] = useState<ModelCostBreakdown | null>(null);
  const [batchSavings, setBatchSavings] = useState<number | null>(null);

  // Loading state
  const [loading, setLoading] = useState(false);
  const [monthlyLoading, setMonthlyLoading] = useState(false);
  const [projectLoading, setProjectLoading] = useState(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  /**
   * Load monthly statistics
   */
  const loadMonthlyStats = useCallback(async () => {
    setMonthlyLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/usage/monthly`);
      if (!response.ok) throw new Error('Failed to load monthly stats');
      const data = await response.json();
      setMonthlyStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setMonthlyLoading(false);
    }
  }, [apiBaseUrl]);

  /**
   * Load project statistics
   */
  const loadProjectStats = useCallback(
    async (projectId: string) => {
      setProjectLoading(true);
      setError(null);
      try {
        const response = await fetch(`${apiBaseUrl}/api/usage/project/${projectId}`);
        if (!response.ok) throw new Error('Failed to load project stats');
        const data = await response.json();
        setProjectStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setProjectLoading(false);
      }
    },
    [apiBaseUrl]
  );

  /**
   * Load cost breakdown by model
   */
  const loadCostBreakdown = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/usage/cost-by-model`);
      if (!response.ok) throw new Error('Failed to load cost breakdown');
      const data = await response.json();
      setCostByModel(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  /**
   * Load batch savings
   */
  const loadBatchSavings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/usage/batch-savings`);
      if (!response.ok) throw new Error('Failed to load batch savings');
      const data = await response.json();
      setBatchSavings(data.savingsUSD);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  /**
   * Record usage event
   */
  const recordUsage = useCallback(
    async (
      projectId: string,
      taskType: string,
      modelId: string,
      inputTokens: number,
      outputTokens: number,
      isBatch: boolean,
      durationMs: number
    ) => {
      setError(null);
      try {
        const response = await fetch(`${apiBaseUrl}/api/track-usage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            projectId,
            taskType,
            modelId,
            inputTokens,
            outputTokens,
            isBatch,
            durationMs,
          }),
        });

        if (!response.ok) throw new Error('Failed to record usage');

        // Refresh stats after recording
        await loadMonthlyStats();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    },
    [apiBaseUrl, loadMonthlyStats]
  );

  /**
   * Set project budget
   */
  const setProjectBudget = useCallback(
    async (projectId: string, budgetUSD: number) => {
      setError(null);
      try {
        const response = await fetch(`${apiBaseUrl}/api/budget/set-project`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ projectId, monthlyBudgetUSD: budgetUSD }),
        });

        if (!response.ok) throw new Error('Failed to set budget');

        // Refresh project stats
        await loadProjectStats(projectId);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    },
    [apiBaseUrl, loadProjectStats]
  );

  /**
   * Generate report
   */
  const generateReport = useCallback(
    async (projectId?: string) => {
      setError(null);
      try {
        const url = projectId
          ? `${apiBaseUrl}/api/usage/report?projectId=${projectId}`
          : `${apiBaseUrl}/api/usage/report`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to generate report');
        const text = await response.text();
        return text;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        return '';
      }
    },
    [apiBaseUrl]
  );

  /**
   * Load initial data on mount
   */
  useEffect(() => {
    loadMonthlyStats();
    loadCostBreakdown();
    loadBatchSavings();
  }, [loadMonthlyStats, loadCostBreakdown, loadBatchSavings]);

  /**
   * Computed values
   */
  const budgetUsagePercent = monthlyStats
    ? (monthlyStats.monthlySpend / monthlyStats.monthlyBudget) * 100
    : 0;

  const isOverBudget = monthlyStats ? monthlyStats.monthlySpend > monthlyStats.monthlyBudget : false;

  const budgetRemaining = monthlyStats
    ? Math.max(0, monthlyStats.monthlyBudget - monthlyStats.monthlySpend)
    : 0;

  return {
    // Data
    monthlyStats,
    projectStats,
    costByModel,
    batchSavings,

    // Loading states
    loading,
    monthlyLoading,
    projectLoading,

    // Errors
    error,

    // Actions
    recordUsage,
    loadMonthlyStats,
    loadProjectStats,
    loadCostBreakdown,
    loadBatchSavings,
    setProjectBudget,
    generateReport,

    // Computed values
    budgetUsagePercent,
    isOverBudget,
    budgetRemaining,
  };
}

export default useClaudeUsageTracker;
