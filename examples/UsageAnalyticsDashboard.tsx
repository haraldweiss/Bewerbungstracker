/**
 * Usage Analytics Dashboard Component
 * React component for displaying Claude API usage statistics and cost analytics
 * Uses the useClaudeUsageTracker hook to fetch and display data
 */

import React, { useState, useEffect } from 'react';
import useClaudeUsageTracker from './useClaudeUsageTracker';

/**
 * Main dashboard component
 */
export const UsageAnalyticsDashboard: React.FC<{ apiBaseUrl?: string }> = ({
  apiBaseUrl = 'http://localhost:3000',
}) => {
  const tracker = useClaudeUsageTracker(apiBaseUrl);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [showReport, setShowReport] = useState(false);
  const [reportText, setReportText] = useState('');

  /**
   * Handle project selection
   */
  const handleProjectSelect = async (projectId: string) => {
    setSelectedProject(projectId);
    await tracker.loadProjectStats(projectId);
  };

  /**
   * Generate and display report
   */
  const handleGenerateReport = async () => {
    const report = await tracker.generateReport(selectedProject || undefined);
    setReportText(report);
    setShowReport(true);
  };

  if (tracker.monthlyLoading && !tracker.monthlyStats) {
    return (
      <div className="analytics-dashboard loading">
        <p>Loading usage data...</p>
      </div>
    );
  }

  const stats = tracker.monthlyStats;

  return (
    <div className="analytics-dashboard">
      <style>{dashboardStyles}</style>

      {/* Error Display */}
      {tracker.error && (
        <div className="alert alert-error">
          <span>⚠️ {tracker.error}</span>
        </div>
      )}

      {/* Header */}
      <div className="dashboard-header">
        <h1>📊 Claude API Usage Analytics</h1>
        <p className="subtitle">Real-time cost tracking and usage statistics</p>
      </div>

      {/* Budget Overview */}
      {stats && (
        <div className="section budget-section">
          <h2>💰 Monthly Budget</h2>
          <div className="budget-container">
            <div className="budget-stat">
              <span className="label">Current Spend</span>
              <span className="value">${stats.monthlySpend.toFixed(2)}</span>
              <span className="subtext">of ${stats.monthlyBudget}</span>
            </div>

            <div className="budget-bar-container">
              <div className="budget-bar">
                <div
                  className={`progress ${tracker.budgetUsagePercent > 100 ? 'over-budget' : tracker.budgetUsagePercent > 80 ? 'warning' : ''}`}
                  style={{ width: `${Math.min(tracker.budgetUsagePercent, 100)}%` }}
                >
                  <span className="percentage">
                    {tracker.budgetUsagePercent.toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            <div className="budget-stat">
              <span className="label">Remaining</span>
              <span className={`value ${tracker.isOverBudget ? 'over' : ''}`}>
                ${tracker.budgetRemaining.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Key Metrics */}
      {stats && (
        <div className="section metrics-section">
          <h2>📈 Key Metrics</h2>
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Total Requests</span>
              <span className="metric-value">{stats.totalRequests}</span>
            </div>

            <div className="metric-card">
              <span className="metric-label">Total Tokens</span>
              <span className="metric-value">
                {(stats.totalTokens / 1000).toFixed(1)}K
              </span>
            </div>

            <div className="metric-card">
              <span className="metric-label">Avg Cost/Request</span>
              <span className="metric-value">
                ${(stats.totalCost / Math.max(1, stats.totalRequests)).toFixed(4)}
              </span>
            </div>

            <div className="metric-card success">
              <span className="metric-label">Batch Requests</span>
              <span className="metric-value">
                {stats.batchRequests}{' '}
                <span className="percentage">
                  {stats.totalRequests > 0
                    ? Math.round((stats.batchRequests / stats.totalRequests) * 100)
                    : 0}
                  %
                </span>
              </span>
            </div>

            <div className="metric-card highlight">
              <span className="metric-label">Total Cost</span>
              <span className="metric-value">${stats.totalCost.toFixed(4)}</span>
            </div>

            {tracker.batchSavings !== null && (
              <div className="metric-card success">
                <span className="metric-label">Batch Savings</span>
                <span className="metric-value">${tracker.batchSavings.toFixed(2)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Model Distribution */}
      {stats && stats.topModels.length > 0 && (
        <div className="section models-section">
          <h2>🤖 Top Models</h2>
          <div className="models-list">
            {stats.topModels.slice(0, 5).map((model) => (
              <div key={model.modelId} className="model-item">
                <div className="model-name">{model.modelId}</div>
                <div className="model-stats">
                  <span>{model.requests} requests</span>
                  <span className="cost">${model.cost.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Task Types */}
      {stats && stats.topTaskTypes.length > 0 && (
        <div className="section tasks-section">
          <h2>📝 Top Tasks</h2>
          <div className="tasks-list">
            {stats.topTaskTypes.slice(0, 5).map((task) => (
              <div key={task.taskType} className="task-item">
                <div className="task-name">{task.taskType}</div>
                <div className="task-stats">
                  <span>{task.requests} calls</span>
                  <span className="cost">${task.cost.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Project Selector and Stats */}
      {stats && stats.costBreakdown && Object.keys(stats.costBreakdown).length > 0 && (
        <div className="section project-section">
          <h2>🎯 Projects</h2>
          <div className="project-selector">
            <label>Select Project: </label>
            <select value={selectedProject} onChange={(e) => handleProjectSelect(e.target.value)}>
              <option value="">-- All Projects --</option>
              {Object.entries(stats.costBreakdown).map(([projectId, cost]) => (
                <option key={projectId} value={projectId}>
                  {projectId} (${cost.toFixed(2)})
                </option>
              ))}
            </select>
          </div>

          {tracker.projectStats && selectedProject && (
            <div className="project-stats">
              <p>
                <strong>{selectedProject}</strong> • {tracker.projectStats.totalRequests} requests
                • ${tracker.projectStats.totalCost.toFixed(4)}
              </p>
              <p className="monthly-info">
                Monthly: ${tracker.projectStats.monthlySpend.toFixed(2)} /{' '}
                ${tracker.projectStats.monthlyBudget}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="section actions-section">
        <button className="btn btn-primary" onClick={handleGenerateReport}>
          📄 Generate Report
        </button>
        <button className="btn btn-secondary" onClick={() => tracker.loadMonthlyStats()}>
          🔄 Refresh Data
        </button>
      </div>

      {/* Report Modal */}
      {showReport && (
        <div className="modal-overlay" onClick={() => setShowReport(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Usage Report</h3>
              <button className="modal-close" onClick={() => setShowReport(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <pre>{reportText}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Dashboard styles
 */
const dashboardStyles = `
  .analytics-dashboard {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background: #f5f5f5;
  }

  .analytics-dashboard.loading {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
  }

  .dashboard-header {
    margin-bottom: 30px;
    text-align: center;
  }

  .dashboard-header h1 {
    margin: 0;
    font-size: 28px;
    color: #333;
  }

  .dashboard-header .subtitle {
    margin: 10px 0 0;
    color: #666;
    font-size: 14px;
  }

  .section {
    background: white;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .section h2 {
    margin: 0 0 15px;
    font-size: 18px;
    color: #333;
  }

  .alert {
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 20px;
  }

  .alert-error {
    background: #fee;
    color: #c33;
    border: 1px solid #fcc;
  }

  .budget-container {
    display: flex;
    gap: 20px;
    align-items: center;
    margin-bottom: 15px;
  }

  .budget-stat {
    flex: 1;
  }

  .budget-stat .label {
    display: block;
    font-size: 12px;
    color: #666;
    margin-bottom: 5px;
  }

  .budget-stat .value {
    display: block;
    font-size: 24px;
    font-weight: bold;
    color: #333;
  }

  .budget-stat .subtext {
    display: block;
    font-size: 12px;
    color: #999;
    margin-top: 3px;
  }

  .budget-bar-container {
    flex: 2;
  }

  .budget-bar {
    height: 28px;
    background: #ddd;
    border-radius: 4px;
    overflow: hidden;
  }

  .budget-bar .progress {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #45a049);
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 10px;
    color: white;
    font-weight: bold;
    font-size: 12px;
    transition: background 0.3s ease;
  }

  .budget-bar .progress.warning {
    background: linear-gradient(90deg, #ff9800, #f59700);
  }

  .budget-bar .progress.over-budget {
    background: linear-gradient(90deg, #f44336, #da190b);
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
  }

  .metric-card {
    background: #f9f9f9;
    padding: 15px;
    border-radius: 6px;
    border-left: 4px solid #ddd;
  }

  .metric-card.success {
    border-left-color: #4CAF50;
    background: #f0f8f0;
  }

  .metric-card.highlight {
    border-left-color: #2196F3;
    background: #f0f4f8;
  }

  .metric-label {
    display: block;
    font-size: 12px;
    color: #666;
    margin-bottom: 8px;
  }

  .metric-value {
    display: block;
    font-size: 22px;
    font-weight: bold;
    color: #333;
  }

  .metric-value .percentage {
    font-size: 12px;
    color: #999;
    font-weight: normal;
  }

  .models-list,
  .tasks-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .model-item,
  .task-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    background: #f9f9f9;
    border-radius: 4px;
  }

  .model-name,
  .task-name {
    font-weight: 500;
    color: #333;
  }

  .model-stats,
  .task-stats {
    display: flex;
    gap: 15px;
    font-size: 12px;
    color: #666;
  }

  .model-stats .cost,
  .task-stats .cost {
    font-weight: bold;
    color: #333;
  }

  .project-selector {
    margin-bottom: 15px;
  }

  .project-selector label {
    margin-right: 10px;
    font-weight: 500;
  }

  .project-selector select {
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
  }

  .project-stats {
    background: #f9f9f9;
    padding: 12px;
    border-radius: 4px;
  }

  .project-stats p {
    margin: 5px 0;
    font-size: 14px;
  }

  .monthly-info {
    color: #666;
    font-size: 12px;
  }

  .actions-section {
    display: flex;
    gap: 10px;
  }

  .btn {
    padding: 10px 16px;
    border: none;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-primary {
    background: #2196F3;
    color: white;
  }

  .btn-primary:hover {
    background: #1976D2;
  }

  .btn-secondary {
    background: #f0f0f0;
    color: #333;
    border: 1px solid #ddd;
  }

  .btn-secondary:hover {
    background: #e0e0e0;
  }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    max-width: 600px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .modal-header {
    padding: 20px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .modal-header h3 {
    margin: 0;
    font-size: 18px;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
  }

  .modal-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
  }

  .modal-body pre {
    background: #f5f5f5;
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 1.5;
    margin: 0;
  }
`;

export default UsageAnalyticsDashboard;
