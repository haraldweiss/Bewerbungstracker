/**
 * Cost Dashboard Component
 * Real-time visualization of Claude API usage and costs
 * Framework-agnostic (works with React, Vue, Svelte)
 */

import React, { useState, useEffect } from 'react';
import { CostCalculator } from '../lib/costCalculator';

interface DashboardData {
  totalRequests: number;
  totalTokens: number;
  totalCost: number;
  monthlySpend: number;
  monthlyBudget: number;
  budgetRemaining: number;
  budgetPercentage: number;
  averageCostPerRequest: number;
  batchSavings: number;
  modelBreakdown: Record<
    string,
    { requests: number; cost: number; percentage: number }
  >;
}

interface CostDashboardProps {
  calculator: CostCalculator;
  refreshInterval?: number; // milliseconds
  compact?: boolean; // Show compact version
}

/**
 * Cost Dashboard Component
 * Displays real-time API usage and cost metrics
 */
export const CostDashboard: React.FC<CostDashboardProps> = ({
  calculator,
  refreshInterval = 10000,
  compact = false,
}) => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const updateData = () => {
      const stats = calculator.getStatistics();
      const monthlyBudget = 100; // Default, would come from calculator
      const monthlySpend = calculator.getMonthlySpend();
      const budgetRemaining = Math.max(0, monthlyBudget - monthlySpend);

      const totalCost = stats.totalCost || 0;
      const modelBreakdown: Record<
        string,
        { requests: number; cost: number; percentage: number }
      > = {};

      for (const [model, usage] of Object.entries(stats.modelUsage)) {
        modelBreakdown[model] = {
          requests: usage.requests,
          cost: usage.cost,
          percentage: totalCost > 0 ? (usage.cost / totalCost) * 100 : 0,
        };
      }

      setData({
        totalRequests: stats.totalRequests,
        totalTokens: stats.totalTokens,
        totalCost: stats.totalCost,
        monthlySpend,
        monthlyBudget,
        budgetRemaining,
        budgetPercentage: monthlyBudget > 0 ? (monthlySpend / monthlyBudget) * 100 : 0,
        averageCostPerRequest: stats.averageCostPerRequest,
        batchSavings: stats.batchSavings,
        modelBreakdown,
      });

      setLoading(false);
    };

    updateData();
    const interval = setInterval(updateData, refreshInterval);

    return () => clearInterval(interval);
  }, [calculator, refreshInterval]);

  if (loading || !data) {
    return (
      <div className="cost-dashboard loading">
        <p>Loading cost data...</p>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="cost-dashboard compact">
        <div className="metric">
          <span className="label">Spend:</span>
          <span className="value">${data.monthlySpend.toFixed(2)}</span>
          <span className="unit">/ ${data.monthlyBudget.toFixed(0)}</span>
        </div>
        <div className="metric">
          <span className="label">Requests:</span>
          <span className="value">{data.totalRequests}</span>
        </div>
        <div className="metric">
          <span className="label">Savings:</span>
          <span className="value">${data.batchSavings.toFixed(2)}</span>
          <span className="unit">w/ batch</span>
        </div>
      </div>
    );
  }

  return (
    <div className="cost-dashboard full">
      <div className="dashboard-header">
        <h2>📊 Claude API Cost Dashboard</h2>
        <p className="timestamp">Updated: {new Date().toLocaleTimeString()}</p>
      </div>

      {/* Budget Overview */}
      <div className="section budget-section">
        <h3>💰 Monthly Budget</h3>
        <div className="budget-overview">
          <div className="budget-stat">
            <span className="stat-label">Monthly Spend</span>
            <span className="stat-value">${data.monthlySpend.toFixed(2)}</span>
            <span className="stat-max">/ ${data.monthlyBudget.toFixed(0)}</span>
          </div>

          <div className="budget-bar">
            <div
              className={`progress-bar ${data.budgetPercentage > 80 ? 'warning' : data.budgetPercentage > 100 ? 'danger' : ''}`}
              style={{ width: `${Math.min(data.budgetPercentage, 100)}%` }}
            >
              <span className="percentage">{data.budgetPercentage.toFixed(0)}%</span>
            </div>
          </div>

          <div className="budget-stat">
            <span className="stat-label">Remaining</span>
            <span className={`stat-value ${data.budgetRemaining < 0 ? 'over-budget' : ''}`}>
              ${Math.max(0, data.budgetRemaining).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Usage Summary */}
      <div className="section usage-section">
        <h3>📈 Usage Summary</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-label">Total Requests</span>
            <span className="metric-value">{data.totalRequests}</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Total Tokens</span>
            <span className="metric-value">
              {(data.totalTokens / 1000).toFixed(1)}K
            </span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Avg Cost/Request</span>
            <span className="metric-value">
              ${data.averageCostPerRequest.toFixed(4)}
            </span>
          </div>

          <div className="metric-card success">
            <span className="metric-label">Batch Savings</span>
            <span className="metric-value">
              ${data.batchSavings.toFixed(2)}
            </span>
            <span className="metric-label">saved</span>
          </div>
        </div>
      </div>

      {/* Model Breakdown */}
      <div className="section model-section">
        <h3>🤖 Model Usage Breakdown</h3>
        <div className="model-list">
          {Object.entries(data.modelBreakdown).map(
            ([model, breakdown]) => (
              <div key={model} className="model-item">
                <div className="model-header">
                  <span className="model-name">{model}</span>
                  <span className="model-stats">
                    {breakdown.requests} requests • ${breakdown.cost.toFixed(2)}
                  </span>
                </div>

                <div className="model-bar">
                  <div
                    className="model-progress"
                    style={{ width: `${breakdown.percentage}%` }}
                  >
                    <span className="model-percentage">
                      {breakdown.percentage.toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* Total Cost Summary */}
      <div className="section total-section">
        <div className="total-card">
          <span className="total-label">Total All-Time Cost</span>
          <span className="total-value">${data.totalCost.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
};

/**
 * Standalone HTML dashboard (for non-React projects)
 */
export function createCostDashboardHTML(calculator: CostCalculator): string {
  const stats = calculator.getStatistics();
  const monthlySpend = calculator.getMonthlySpend();
  const monthlyBudget = 100;

  const modelRows = Object.entries(stats.modelUsage)
    .map(
      ([model, usage]) => `
    <tr>
      <td>${model}</td>
      <td>${usage.requests}</td>
      <td>$${usage.cost.toFixed(4)}</td>
    </tr>
  `
    )
    .join('');

  return `
    <div class="cost-dashboard">
      <style>
        .cost-dashboard {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          max-width: 1000px;
          padding: 20px;
          background: #f5f5f5;
          border-radius: 8px;
        }
        .dashboard-header { margin-bottom: 20px; }
        .dashboard-header h2 { margin: 0 0 10px; font-size: 24px; }
        .section { margin-bottom: 20px; }
        .section h3 { margin: 0 0 15px; font-size: 18px; }
        .budget-bar {
          height: 30px;
          background: #ddd;
          border-radius: 4px;
          overflow: hidden;
          margin: 10px 0;
        }
        .progress-bar {
          height: 100%;
          background: #4CAF50;
          display: flex;
          align-items: center;
          justify-content: flex-end;
          padding-right: 10px;
          color: white;
          font-weight: bold;
          transition: background 0.3s;
        }
        .progress-bar.warning { background: #ff9800; }
        .progress-bar.danger { background: #f44336; }
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 15px;
        }
        .metric-card {
          background: white;
          padding: 15px;
          border-radius: 6px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-card.success { border-left: 4px solid #4CAF50; }
        .metric-label { display: block; font-size: 12px; color: #666; margin-bottom: 5px; }
        .metric-value { display: block; font-size: 24px; font-weight: bold; color: #333; }
        .model-item {
          background: white;
          padding: 12px;
          border-radius: 4px;
          margin-bottom: 10px;
        }
        .model-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-size: 14px;
        }
        .model-name { font-weight: bold; }
        .model-stats { color: #666; font-size: 12px; }
        .model-bar {
          height: 20px;
          background: #f0f0f0;
          border-radius: 3px;
          overflow: hidden;
        }
        .model-progress {
          height: 100%;
          background: linear-gradient(90deg, #2196F3, #21CBF3);
          display: flex;
          align-items: center;
          justify-content: flex-end;
          padding-right: 5px;
          color: white;
          font-size: 11px;
          font-weight: bold;
        }
        .total-card {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 30px;
          border-radius: 8px;
          text-align: center;
        }
        .total-label { display: block; font-size: 14px; margin-bottom: 10px; opacity: 0.9; }
        .total-value { display: block; font-size: 36px; font-weight: bold; }
      </style>

      <div class="dashboard-header">
        <h2>📊 Claude API Cost Dashboard</h2>
      </div>

      <div class="section">
        <h3>💰 Monthly Budget</h3>
        <div style="margin-bottom: 10px;">
          <strong>$${monthlySpend.toFixed(2)} / $${monthlyBudget.toFixed(0)}</strong>
        </div>
        <div class="budget-bar">
          <div class="progress-bar" style="width: ${Math.min((monthlySpend / monthlyBudget) * 100, 100)}%">
            ${((monthlySpend / monthlyBudget) * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <div class="section">
        <h3>📈 Summary</h3>
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Requests</span>
            <span class="metric-value">${stats.totalRequests}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Total Cost</span>
            <span class="metric-value">$${stats.totalCost.toFixed(2)}</span>
          </div>
          <div class="metric-card success">
            <span class="metric-label">Batch Savings</span>
            <span class="metric-value">$${stats.batchSavings.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div class="section">
        <h3>🤖 Model Breakdown</h3>
        <table style="width: 100%; border-collapse: collapse;">
          <tr style="background: #f9f9f9; font-weight: bold;">
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">Model</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">Requests</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">Cost</td>
          </tr>
          ${modelRows}
        </table>
      </div>

      <div class="section">
        <div class="total-card">
          <span class="total-label">Total Cost</span>
          <span class="total-value">$${stats.totalCost.toFixed(2)}</span>
        </div>
      </div>
    </div>
  `;
}

export default CostDashboard;
