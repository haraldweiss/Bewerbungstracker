/**
 * Cost Calculation & Tracking Module
 * Estimates and logs API costs for budget management
 */

import { MODEL_CONFIG } from "./claudeModelRouter";

/**
 * Cost estimate breakdown
 */
export interface CostEstimate {
  modelId: keyof typeof MODEL_CONFIG;
  inputTokens: number;
  outputTokens: number;
  inputCost: number;
  outputCost: number;
  totalCost: number;
  isBatchEligible: boolean;
  batchCost?: number;
  costSavingsWithBatch?: number;
}

/**
 * Usage log entry
 */
export interface UsageLog {
  timestamp: string;
  modelId: keyof typeof MODEL_CONFIG;
  inputTokens: number;
  outputTokens: number;
  actualCost: number;
  isBatch: boolean;
  taskType: string;
}

/**
 * Cost calculator and tracker
 */
export class CostCalculator {
  private logs: UsageLog[] = [];
  private monthlyBudget: number = Infinity;

  /**
   * Initialize with optional monthly budget in USD
   *
   * @param monthlyBudgetUSD Monthly budget limit in USD
   */
  constructor(monthlyBudgetUSD?: number) {
    if (monthlyBudgetUSD) {
      this.monthlyBudget = monthlyBudgetUSD;
    }
  }

  /**
   * Estimate cost for a request
   *
   * @param modelId Model to calculate cost for
   * @param inputTokens Input token count
   * @param outputTokens Output token count
   * @param isUrgent Whether request is time-sensitive (disables batch)
   * @returns Cost estimate with batch comparison
   */
  estimateCost(
    modelId: keyof typeof MODEL_CONFIG,
    inputTokens: number,
    outputTokens: number,
    isUrgent: boolean = false
  ): CostEstimate {
    const config = MODEL_CONFIG[modelId];

    const inputCost = inputTokens * config.inputCost;
    const outputCost = outputTokens * config.outputCost;
    const totalCost = inputCost + outputCost;

    // Batch API is 50% discount, but not for urgent requests
    const isBatchEligible = !isUrgent && totalCost > 0.01; // Minimum cost threshold
    const batchCost = isBatchEligible ? totalCost * 0.5 : undefined;
    const costSavingsWithBatch = isBatchEligible ? totalCost * 0.5 : undefined;

    return {
      modelId,
      inputTokens,
      outputTokens,
      inputCost,
      outputCost,
      totalCost,
      isBatchEligible,
      batchCost,
      costSavingsWithBatch,
    };
  }

  /**
   * Log an actual API usage
   *
   * @param modelId Model used
   * @param inputTokens Actual input tokens
   * @param outputTokens Actual output tokens
   * @param taskType Task description
   * @param isBatch Whether batch API was used
   */
  logUsage(
    modelId: keyof typeof MODEL_CONFIG,
    inputTokens: number,
    outputTokens: number,
    taskType: string,
    isBatch: boolean = false
  ): void {
    const config = MODEL_CONFIG[modelId];
    const baseCost = inputTokens * config.inputCost + outputTokens * config.outputCost;
    const actualCost = isBatch ? baseCost * 0.5 : baseCost;

    const log: UsageLog = {
      timestamp: new Date().toISOString(),
      modelId,
      inputTokens,
      outputTokens,
      actualCost,
      isBatch,
      taskType,
    };

    this.logs.push(log);

    // Check budget
    const monthlySpend = this.getMonthlySpend();
    if (monthlySpend > this.monthlyBudget) {
      console.warn(
        `⚠️  Monthly spend ($${monthlySpend.toFixed(2)}) exceeds budget ($${this.monthlyBudget.toFixed(2)})`
      );
    }
  }

  /**
   * Get total cost for a period
   *
   * @param days Number of days to look back (default: 30)
   * @returns Total cost in USD
   */
  getTotalCost(days: number = 30): number {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);

    return this.logs
      .filter((log) => new Date(log.timestamp) >= cutoff)
      .reduce((sum, log) => sum + log.actualCost, 0);
  }

  /**
   * Get monthly spend (current month)
   *
   * @returns Monthly spend in USD
   */
  getMonthlySpend(): number {
    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

    return this.logs
      .filter((log) => new Date(log.timestamp) >= monthStart)
      .reduce((sum, log) => sum + log.actualCost, 0);
  }

  /**
   * Get usage statistics
   *
   * @returns Detailed statistics
   */
  getStatistics(): {
    totalRequests: number;
    totalTokens: number;
    totalCost: number;
    averageCostPerRequest: number;
    batchSavings: number;
    modelUsage: Record<string, { requests: number; cost: number }>;
  } {
    const totalRequests = this.logs.length;
    const totalTokens = this.logs.reduce(
      (sum, log) => sum + log.inputTokens + log.outputTokens,
      0
    );
    const totalCost = this.logs.reduce((sum, log) => sum + log.actualCost, 0);
    const averageCostPerRequest = totalRequests > 0 ? totalCost / totalRequests : 0;

    // Calculate batch savings
    const nonBatchCost = this.logs
      .filter((log) => !log.isBatch)
      .reduce((sum, log) => sum + log.actualCost * 2, 0); // Undo the 50% discount
    const batchSavings = nonBatchCost - totalCost;

    // Model usage breakdown
    const modelUsage: Record<string, { requests: number; cost: number }> = {};
    for (const log of this.logs) {
      if (!modelUsage[log.modelId]) {
        modelUsage[log.modelId] = { requests: 0, cost: 0 };
      }
      modelUsage[log.modelId].requests += 1;
      modelUsage[log.modelId].cost += log.actualCost;
    }

    return {
      totalRequests,
      totalTokens,
      totalCost,
      averageCostPerRequest,
      batchSavings,
      modelUsage,
    };
  }

  /**
   * Format cost as USD string
   *
   * @param cost Cost in dollars
   * @returns Formatted string
   */
  static formatCost(cost: number): string {
    if (cost < 0.001) {
      return `$${(cost * 1000).toFixed(2)}m`; // millicents
    }
    return `$${cost.toFixed(4)}`;
  }

  /**
   * Get all logs
   *
   * @returns Array of usage logs
   */
  getLogs(): UsageLog[] {
    return [...this.logs];
  }

  /**
   * Clear logs (useful for testing)
   */
  clearLogs(): void {
    this.logs = [];
  }

  /**
   * Export logs as JSON
   *
   * @returns JSON string
   */
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2);
  }

  /**
   * Generate cost report
   *
   * @returns Formatted report string
   */
  generateReport(): string {
    const stats = this.getStatistics();
    const monthlySpend = this.getMonthlySpend();

    let report = "=== Cost Report ===\n";
    report += `Total Requests: ${stats.totalRequests}\n`;
    report += `Total Tokens: ${stats.totalTokens.toLocaleString()}\n`;
    report += `Total Cost: ${CostCalculator.formatCost(stats.totalCost)}\n`;
    report += `Monthly Spend: ${CostCalculator.formatCost(monthlySpend)}\n`;
    report += `Monthly Budget: ${CostCalculator.formatCost(this.monthlyBudget)}\n`;
    report += `Budget Remaining: ${CostCalculator.formatCost(Math.max(0, this.monthlyBudget - monthlySpend))}\n`;
    report += `Avg Cost/Request: ${CostCalculator.formatCost(stats.averageCostPerRequest)}\n`;
    report += `Batch Savings: ${CostCalculator.formatCost(stats.batchSavings)}\n`;

    report += "\n=== Model Usage ===\n";
    for (const [model, usage] of Object.entries(stats.modelUsage)) {
      report += `${model}: ${usage.requests} requests (${CostCalculator.formatCost(usage.cost)})\n`;
    }

    return report;
  }
}

export default CostCalculator;
