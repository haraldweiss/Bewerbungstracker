/**
 * Usage Tracker Service
 * Integration layer for tracking Claude API usage across multiple projects
 * Provides analytics, cost reporting, and usage statistics
 */

import { CostCalculator } from './costCalculator';

/**
 * Usage event recorded for each API call
 */
export interface UsageEvent {
  timestamp: Date;
  projectId: string;
  taskType: string;
  modelId: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  isBatch: boolean;
  durationMs: number;
  userId?: string;
  metadata?: Record<string, any>;
}

/**
 * Period-based usage statistics
 */
export interface UsagePeriod {
  startDate: Date;
  endDate: Date;
  totalRequests: number;
  totalTokens: number;
  totalCost: number;
  averageCostPerRequest: number;
  batchRequests: number;
  regularRequests: number;
  topModels: Array<{ modelId: string; requests: number; cost: number }>;
  topTaskTypes: Array<{ taskType: string; requests: number; cost: number }>;
  costBreakdown: Record<string, number>;
}

/**
 * Project-level usage statistics
 */
export interface ProjectStats {
  projectId: string;
  totalRequests: number;
  totalCost: number;
  monthlySpend: number;
  monthlyBudget: number;
  costTrend: Array<{ date: Date; cost: number }>;
  modelDistribution: Record<string, number>;
}

/**
 * Usage Tracker for monitoring Claude API consumption
 */
export class UsageTracker {
  private events: UsageEvent[] = [];
  private costCalculator: CostCalculator;
  private projectBudgets: Map<string, number> = new Map();

  constructor(defaultMonthlyBudget: number = 100) {
    this.costCalculator = new CostCalculator(defaultMonthlyBudget);
  }

  /**
   * Record a usage event (called after successful API call)
   */
  recordUsage(
    projectId: string,
    taskType: string,
    modelId: string,
    inputTokens: number,
    outputTokens: number,
    isBatch: boolean,
    durationMs: number,
    userId?: string,
    metadata?: Record<string, any>
  ): UsageEvent {
    const event: UsageEvent = {
      timestamp: new Date(),
      projectId,
      taskType,
      modelId,
      inputTokens,
      outputTokens,
      totalTokens: inputTokens + outputTokens,
      cost: 0, // Will be calculated below
      isBatch,
      durationMs,
      userId,
      metadata,
    };

    // Calculate cost using CostCalculator
    this.costCalculator.logUsage(modelId, inputTokens, outputTokens, taskType, isBatch);
    const logs = this.costCalculator.getLogs();
    if (logs.length > 0) {
      event.cost = logs[logs.length - 1].actualCost;
    }

    this.events.push(event);

    // Check budget
    this.checkProjectBudget(projectId);

    return event;
  }

  /**
   * Get usage statistics for a time period
   */
  getUsageForPeriod(startDate: Date, endDate: Date): UsagePeriod {
    const periodEvents = this.events.filter(
      (e) => e.timestamp >= startDate && e.timestamp <= endDate
    );

    const totalCost = periodEvents.reduce((sum, e) => sum + e.cost, 0);
    const batchRequests = periodEvents.filter((e) => e.isBatch).length;
    const totalTokens = periodEvents.reduce((sum, e) => sum + e.totalTokens, 0);

    // Top models
    const modelMap: Record<string, { requests: number; cost: number }> = {};
    periodEvents.forEach((e) => {
      if (!modelMap[e.modelId]) {
        modelMap[e.modelId] = { requests: 0, cost: 0 };
      }
      modelMap[e.modelId].requests++;
      modelMap[e.modelId].cost += e.cost;
    });
    const topModels = Object.entries(modelMap)
      .map(([modelId, stats]) => ({ modelId, ...stats }))
      .sort((a, b) => b.cost - a.cost)
      .slice(0, 5);

    // Top task types
    const taskMap: Record<string, { requests: number; cost: number }> = {};
    periodEvents.forEach((e) => {
      if (!taskMap[e.taskType]) {
        taskMap[e.taskType] = { requests: 0, cost: 0 };
      }
      taskMap[e.taskType].requests++;
      taskMap[e.taskType].cost += e.cost;
    });
    const topTaskTypes = Object.entries(taskMap)
      .map(([taskType, stats]) => ({ taskType, ...stats }))
      .sort((a, b) => b.cost - a.cost)
      .slice(0, 5);

    // Cost breakdown
    const costBreakdown: Record<string, number> = {};
    periodEvents.forEach((e) => {
      if (!costBreakdown[e.projectId]) {
        costBreakdown[e.projectId] = 0;
      }
      costBreakdown[e.projectId] += e.cost;
    });

    return {
      startDate,
      endDate,
      totalRequests: periodEvents.length,
      totalTokens,
      totalCost,
      averageCostPerRequest: periodEvents.length > 0 ? totalCost / periodEvents.length : 0,
      batchRequests,
      regularRequests: periodEvents.length - batchRequests,
      topModels,
      topTaskTypes,
      costBreakdown,
    };
  }

  /**
   * Get stats for the current month
   */
  getMonthlyStats(): UsagePeriod {
    const now = new Date();
    const startDate = new Date(now.getFullYear(), now.getMonth(), 1);
    const endDate = new Date(now.getFullYear(), now.getMonth() + 1, 0);

    return this.getUsageForPeriod(startDate, endDate);
  }

  /**
   * Get project-specific statistics
   */
  getProjectStats(projectId: string): ProjectStats {
    const projectEvents = this.events.filter((e) => e.projectId === projectId);
    const totalCost = projectEvents.reduce((sum, e) => sum + e.cost, 0);

    // Monthly spend (current month)
    const monthlyStats = this.getMonthlyStats();
    const monthlySpend = monthlyStats.costBreakdown[projectId] || 0;
    const monthlyBudget = this.projectBudgets.get(projectId) || 100;

    // Cost trend (last 30 days, grouped by day)
    const now = new Date();
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    const trendEvents = projectEvents.filter((e) => e.timestamp >= thirtyDaysAgo);

    const dailyCosts: Record<string, number> = {};
    trendEvents.forEach((e) => {
      const dateKey = e.timestamp.toISOString().split('T')[0];
      dailyCosts[dateKey] = (dailyCosts[dateKey] || 0) + e.cost;
    });

    const costTrend = Object.entries(dailyCosts)
      .map(([date, cost]) => ({
        date: new Date(date),
        cost,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    // Model distribution
    const modelDist: Record<string, number> = {};
    projectEvents.forEach((e) => {
      modelDist[e.modelId] = (modelDist[e.modelId] || 0) + 1;
    });

    return {
      projectId,
      totalRequests: projectEvents.length,
      totalCost,
      monthlySpend,
      monthlyBudget,
      costTrend,
      modelDistribution: modelDist,
    };
  }

  /**
   * Set budget limit for a project
   */
  setProjectBudget(projectId: string, monthlyBudgetUSD: number): void {
    this.projectBudgets.set(projectId, monthlyBudgetUSD);
  }

  /**
   * Check if project is approaching or exceeding budget
   */
  private checkProjectBudget(projectId: string): void {
    const budget = this.projectBudgets.get(projectId);
    if (!budget) return;

    const monthlyStats = this.getMonthlyStats();
    const spent = monthlyStats.costBreakdown[projectId] || 0;

    if (spent >= budget) {
      console.warn(`⚠️ Project ${projectId} has EXCEEDED budget: $${spent.toFixed(2)} / $${budget}`);
    } else if (spent >= budget * 0.8) {
      console.warn(
        `⚠️ Project ${projectId} is at ${((spent / budget) * 100).toFixed(0)}% of budget: $${spent.toFixed(2)} / $${budget}`
      );
    }
  }

  /**
   * Get all recorded events
   */
  getEvents(filters?: {
    projectId?: string;
    modelId?: string;
    startDate?: Date;
    endDate?: Date;
  }): UsageEvent[] {
    let filtered = this.events;

    if (filters?.projectId) {
      filtered = filtered.filter((e) => e.projectId === filters.projectId);
    }
    if (filters?.modelId) {
      filtered = filtered.filter((e) => e.modelId === filters.modelId);
    }
    if (filters?.startDate) {
      filtered = filtered.filter((e) => e.timestamp >= filters.startDate!);
    }
    if (filters?.endDate) {
      filtered = filtered.filter((e) => e.timestamp <= filters.endDate!);
    }

    return filtered;
  }

  /**
   * Generate comprehensive usage report
   */
  generateReport(projectId?: string): string {
    const monthlyStats = this.getMonthlyStats();

    let report = `\n${'='.repeat(60)}\n`;
    report += `Claude API Usage Report - ${new Date().toLocaleDateString()}\n`;
    report += `${'='.repeat(60)}\n\n`;

    if (projectId) {
      const projectStats = this.getProjectStats(projectId);
      report += `Project: ${projectId}\n`;
      report += `-`.repeat(40) + '\n';
      report += `Total Requests: ${projectStats.totalRequests}\n`;
      report += `Total Cost: $${projectStats.totalCost.toFixed(4)}\n`;
      report += `Monthly Spend: $${projectStats.monthlySpend.toFixed(2)} / $${projectStats.monthlyBudget}\n`;
      report += `Budget Usage: ${((projectStats.monthlySpend / projectStats.monthlyBudget) * 100).toFixed(0)}%\n\n`;

      report += `Model Distribution:\n`;
      Object.entries(projectStats.modelDistribution)
        .sort((a, b) => b[1] - a[1])
        .forEach(([model, count]) => {
          report += `  ${model}: ${count} requests\n`;
        });
    } else {
      report += `Period: ${monthlyStats.startDate.toLocaleDateString()} - ${monthlyStats.endDate.toLocaleDateString()}\n\n`;
      report += `Total Requests: ${monthlyStats.totalRequests}\n`;
      report += `Total Tokens: ${monthlyStats.totalTokens.toLocaleString()}\n`;
      report += `Total Cost: $${monthlyStats.totalCost.toFixed(4)}\n`;
      report += `Avg Cost/Request: $${monthlyStats.averageCostPerRequest.toFixed(4)}\n`;
      report += `Batch Requests: ${monthlyStats.batchRequests} (${((monthlyStats.batchRequests / monthlyStats.totalRequests) * 100).toFixed(0)}%)\n\n`;

      report += `Top Models:\n`;
      monthlyStats.topModels.forEach((model) => {
        report += `  ${model.modelId}: ${model.requests} requests, $${model.cost.toFixed(4)}\n`;
      });

      report += `\nTop Task Types:\n`;
      monthlyStats.topTaskTypes.forEach((task) => {
        report += `  ${task.taskType}: ${task.requests} requests, $${task.cost.toFixed(4)}\n`;
      });

      report += `\nCost by Project:\n`;
      Object.entries(monthlyStats.costBreakdown)
        .sort((a, b) => b[1] - a[1])
        .forEach(([proj, cost]) => {
          report += `  ${proj}: $${cost.toFixed(4)}\n`;
        });
    }

    report += `\n${'='.repeat(60)}\n`;

    return report;
  }

  /**
   * Export events as JSON
   */
  exportEvents(): string {
    return JSON.stringify(
      this.events.map((e) => ({
        ...e,
        timestamp: e.timestamp.toISOString(),
      })),
      null,
      2
    );
  }

  /**
   * Clear all events (use with caution)
   */
  clearEvents(): void {
    this.events = [];
  }

  /**
   * Get usage events for a specific user
   */
  getUserUsage(userId: string): UsageEvent[] {
    return this.events.filter((e) => e.userId === userId);
  }

  /**
   * Calculate savings from batch processing
   */
  calculateBatchSavings(): number {
    const batchEvents = this.events.filter((e) => e.isBatch);
    let savings = 0;

    batchEvents.forEach((e) => {
      // Batch provides 50% savings
      savings += e.cost * 0.5;
    });

    return savings;
  }

  /**
   * Get detailed cost breakdown by model
   */
  getCostByModel(): Record<string, { requests: number; tokens: number; cost: number }> {
    const breakdown: Record<string, { requests: number; tokens: number; cost: number }> = {};

    this.events.forEach((e) => {
      if (!breakdown[e.modelId]) {
        breakdown[e.modelId] = { requests: 0, tokens: 0, cost: 0 };
      }
      breakdown[e.modelId].requests++;
      breakdown[e.modelId].tokens += e.totalTokens;
      breakdown[e.modelId].cost += e.cost;
    });

    return breakdown;
  }
}

export default UsageTracker;
