/**
 * Unit Tests for Usage Tracker
 * Tests usage recording, analytics, budget tracking, and reporting
 */

import { UsageTracker } from '../usageTracker';

describe('UsageTracker', () => {
  let tracker: UsageTracker;

  beforeEach(() => {
    tracker = new UsageTracker(100); // $100 monthly budget
  });

  describe('recordUsage()', () => {
    test('should record basic usage event', () => {
      const event = tracker.recordUsage(
        'bewerbungstracker',
        'classify',
        'claude-haiku-4-5',
        1000,
        100,
        false,
        250
      );

      expect(event.projectId).toBe('bewerbungstracker');
      expect(event.taskType).toBe('classify');
      expect(event.modelId).toBe('claude-haiku-4-5');
      expect(event.inputTokens).toBe(1000);
      expect(event.outputTokens).toBe(100);
      expect(event.totalTokens).toBe(1100);
      expect(event.durationMs).toBe(250);
    });

    test('should calculate cost correctly', () => {
      const event = tracker.recordUsage(
        'project1',
        'analyze',
        'claude-haiku-4-5',
        10000,
        1000,
        false,
        500
      );

      // Haiku: 10k * $0.002/1k + 1k * $0.005/1k = $0.02 + $0.005 = $0.025
      expect(event.cost).toBeCloseTo(0.025, 4);
    });

    test('should apply 50% batch discount', () => {
      const regularEvent = tracker.recordUsage(
        'project1',
        'task',
        'claude-haiku-4-5',
        10000,
        1000,
        false,
        500
      );

      tracker.clearEvents();

      const batchEvent = tracker.recordUsage(
        'project1',
        'task',
        'claude-haiku-4-5',
        10000,
        1000,
        true, // batch
        500
      );

      // Batch should be 50% of regular
      expect(batchEvent.cost).toBeCloseTo(regularEvent.cost * 0.5, 4);
    });

    test('should include optional user ID', () => {
      const event = tracker.recordUsage(
        'project1',
        'classify',
        'claude-haiku-4-5',
        500,
        50,
        false,
        100,
        'user-123'
      );

      expect(event.userId).toBe('user-123');
    });

    test('should include optional metadata', () => {
      const metadata = { source: 'email-classifier', version: '1.0' };
      const event = tracker.recordUsage(
        'project1',
        'classify',
        'claude-haiku-4-5',
        500,
        50,
        false,
        100,
        undefined,
        metadata
      );

      expect(event.metadata).toEqual(metadata);
    });
  });

  describe('getUsageForPeriod()', () => {
    beforeEach(() => {
      const now = new Date();
      // Record multiple events
      tracker.recordUsage('project1', 'classify', 'claude-haiku-4-5', 1000, 100, false, 100);
      tracker.recordUsage('project1', 'analyze', 'claude-sonnet-4-6', 5000, 500, false, 200);
      tracker.recordUsage('project2', 'generate', 'claude-opus-4-7', 10000, 2000, true, 300);
    });

    test('should calculate period statistics', () => {
      const now = new Date();
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const endDate = now;

      const stats = tracker.getUsageForPeriod(startDate, endDate);

      expect(stats.totalRequests).toBe(3);
      expect(stats.totalTokens).toBeGreaterThan(0);
      expect(stats.totalCost).toBeGreaterThan(0);
    });

    test('should identify top models', () => {
      const now = new Date();
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const endDate = now;

      const stats = tracker.getUsageForPeriod(startDate, endDate);

      expect(stats.topModels.length).toBeGreaterThan(0);
      expect(stats.topModels[0]).toHaveProperty('modelId');
      expect(stats.topModels[0]).toHaveProperty('requests');
      expect(stats.topModels[0]).toHaveProperty('cost');
    });

    test('should identify top task types', () => {
      const now = new Date();
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const endDate = now;

      const stats = tracker.getUsageForPeriod(startDate, endDate);

      expect(stats.topTaskTypes.length).toBeGreaterThan(0);
      expect(stats.topTaskTypes[0]).toHaveProperty('taskType');
    });

    test('should count batch vs regular requests', () => {
      const now = new Date();
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const endDate = now;

      const stats = tracker.getUsageForPeriod(startDate, endDate);

      expect(stats.batchRequests).toBe(1);
      expect(stats.regularRequests).toBe(2);
    });

    test('should provide cost breakdown by project', () => {
      const now = new Date();
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const endDate = now;

      const stats = tracker.getUsageForPeriod(startDate, endDate);

      expect(stats.costBreakdown['project1']).toBeGreaterThan(0);
      expect(stats.costBreakdown['project2']).toBeGreaterThan(0);
    });

    test('should calculate average cost per request', () => {
      const now = new Date();
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const endDate = now;

      const stats = tracker.getUsageForPeriod(startDate, endDate);

      expect(stats.averageCostPerRequest).toBeGreaterThan(0);
      expect(stats.averageCostPerRequest).toBeLessThan(stats.totalCost);
    });
  });

  describe('getMonthlyStats()', () => {
    test('should return current month statistics', () => {
      tracker.recordUsage('project1', 'classify', 'claude-haiku-4-5', 1000, 100, false, 100);

      const stats = tracker.getMonthlyStats();

      expect(stats.startDate.getMonth()).toBe(new Date().getMonth());
      expect(stats.endDate.getMonth()).toBe(new Date().getMonth());
      expect(stats.totalRequests).toBeGreaterThan(0);
    });
  });

  describe('getProjectStats()', () => {
    beforeEach(() => {
      tracker.recordUsage('project1', 'task1', 'claude-haiku-4-5', 1000, 100, false, 100);
      tracker.recordUsage('project1', 'task2', 'claude-sonnet-4-6', 2000, 200, false, 200);
      tracker.recordUsage('project2', 'task3', 'claude-opus-4-7', 3000, 300, false, 300);
    });

    test('should return project-specific statistics', () => {
      const stats = tracker.getProjectStats('project1');

      expect(stats.projectId).toBe('project1');
      expect(stats.totalRequests).toBe(2);
      expect(stats.totalCost).toBeGreaterThan(0);
    });

    test('should include model distribution', () => {
      const stats = tracker.getProjectStats('project1');

      expect(stats.modelDistribution['claude-haiku-4-5']).toBe(1);
      expect(stats.modelDistribution['claude-sonnet-4-6']).toBe(1);
    });

    test('should calculate monthly spend', () => {
      tracker.setProjectBudget('project1', 100);

      const stats = tracker.getProjectStats('project1');

      expect(stats.monthlySpend).toBeGreaterThan(0);
      expect(stats.monthlyBudget).toBe(100);
    });

    test('should provide 30-day cost trend', () => {
      const stats = tracker.getProjectStats('project1');

      expect(stats.costTrend.length).toBeGreaterThan(0);
      expect(stats.costTrend[0]).toHaveProperty('date');
      expect(stats.costTrend[0]).toHaveProperty('cost');
    });
  });

  describe('setProjectBudget()', () => {
    test('should set budget for project', () => {
      tracker.setProjectBudget('project1', 150);

      const stats = tracker.getProjectStats('project1');
      expect(stats.monthlyBudget).toBe(150);
    });
  });

  describe('getEvents()', () => {
    beforeEach(() => {
      tracker.recordUsage('project1', 'task1', 'claude-haiku-4-5', 1000, 100, false, 100);
      tracker.recordUsage('project1', 'task2', 'claude-sonnet-4-6', 2000, 200, false, 200);
      tracker.recordUsage('project2', 'task3', 'claude-opus-4-7', 3000, 300, false, 300);
    });

    test('should return all events without filters', () => {
      const events = tracker.getEvents();

      expect(events).toHaveLength(3);
    });

    test('should filter events by project', () => {
      const events = tracker.getEvents({ projectId: 'project1' });

      expect(events).toHaveLength(2);
      expect(events.every((e) => e.projectId === 'project1')).toBe(true);
    });

    test('should filter events by model', () => {
      const events = tracker.getEvents({ modelId: 'claude-haiku-4-5' });

      expect(events).toHaveLength(1);
      expect(events[0].modelId).toBe('claude-haiku-4-5');
    });

    test('should filter events by date range', () => {
      const startDate = new Date();
      const endDate = new Date(startDate.getTime() + 60 * 1000);

      const events = tracker.getEvents({ startDate, endDate });

      expect(events.length).toBeGreaterThan(0);
    });

    test('should combine multiple filters', () => {
      const events = tracker.getEvents({
        projectId: 'project1',
        modelId: 'claude-haiku-4-5',
      });

      expect(events).toHaveLength(1);
      expect(events[0].projectId).toBe('project1');
      expect(events[0].modelId).toBe('claude-haiku-4-5');
    });
  });

  describe('generateReport()', () => {
    beforeEach(() => {
      tracker.recordUsage('project1', 'classify', 'claude-haiku-4-5', 1000, 100, false, 100);
      tracker.recordUsage('project2', 'analyze', 'claude-sonnet-4-6', 5000, 500, false, 200);
    });

    test('should generate overall report', () => {
      const report = tracker.generateReport();

      expect(report).toContain('Claude API Usage Report');
      expect(report).toContain('Total Requests');
      expect(report).toContain('Total Cost');
    });

    test('should generate project-specific report', () => {
      const report = tracker.generateReport('project1');

      expect(report).toContain('project1');
      expect(report).toContain('Total Requests: 1');
    });

    test('should include model information in report', () => {
      const report = tracker.generateReport('project1');

      expect(report).toContain('claude-haiku-4-5');
    });
  });

  describe('exportEvents()', () => {
    test('should export events as JSON', () => {
      tracker.recordUsage('project1', 'classify', 'claude-haiku-4-5', 1000, 100, false, 100);

      const json = tracker.exportEvents();
      const parsed = JSON.parse(json);

      expect(Array.isArray(parsed)).toBe(true);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].projectId).toBe('project1');
    });

    test('should convert timestamps to ISO strings', () => {
      tracker.recordUsage('project1', 'task', 'claude-haiku-4-5', 1000, 100, false, 100);

      const json = tracker.exportEvents();
      const parsed = JSON.parse(json);

      expect(typeof parsed[0].timestamp).toBe('string');
      expect(parsed[0].timestamp).toMatch(/\d{4}-\d{2}-\d{2}/);
    });
  });

  describe('getUserUsage()', () => {
    beforeEach(() => {
      tracker.recordUsage('project1', 'task1', 'claude-haiku-4-5', 1000, 100, false, 100, 'user1');
      tracker.recordUsage('project1', 'task2', 'claude-haiku-4-5', 1000, 100, false, 100, 'user2');
      tracker.recordUsage('project2', 'task3', 'claude-haiku-4-5', 1000, 100, false, 100, 'user1');
    });

    test('should filter events by user ID', () => {
      const userEvents = tracker.getUserUsage('user1');

      expect(userEvents).toHaveLength(2);
      expect(userEvents.every((e) => e.userId === 'user1')).toBe(true);
    });

    test('should return empty array for non-existent user', () => {
      const userEvents = tracker.getUserUsage('user-nonexistent');

      expect(userEvents).toHaveLength(0);
    });
  });

  describe('calculateBatchSavings()', () => {
    test('should calculate savings from batch requests', () => {
      tracker.recordUsage('project1', 'task1', 'claude-haiku-4-5', 10000, 1000, false, 100);
      tracker.recordUsage('project1', 'task2', 'claude-haiku-4-5', 10000, 1000, true, 200); // batch
      tracker.recordUsage('project1', 'task3', 'claude-haiku-4-5', 10000, 1000, true, 300); // batch

      const savings = tracker.calculateBatchSavings();

      expect(savings).toBeGreaterThan(0);
      // 2 batch requests * 50% savings = roughly cost of 1 non-batch request
      expect(savings).toBeGreaterThan(0.01);
    });

    test('should return zero if no batch requests', () => {
      tracker.recordUsage('project1', 'task1', 'claude-haiku-4-5', 1000, 100, false, 100);
      tracker.recordUsage('project1', 'task2', 'claude-haiku-4-5', 1000, 100, false, 100);

      const savings = tracker.calculateBatchSavings();

      expect(savings).toBe(0);
    });
  });

  describe('getCostByModel()', () => {
    beforeEach(() => {
      tracker.recordUsage('project1', 'task1', 'claude-haiku-4-5', 1000, 100, false, 100);
      tracker.recordUsage('project1', 'task2', 'claude-haiku-4-5', 2000, 200, false, 200);
      tracker.recordUsage('project1', 'task3', 'claude-sonnet-4-6', 5000, 500, false, 300);
    });

    test('should provide cost breakdown by model', () => {
      const breakdown = tracker.getCostByModel();

      expect(breakdown['claude-haiku-4-5']).toBeDefined();
      expect(breakdown['claude-sonnet-4-6']).toBeDefined();
    });

    test('should count requests per model', () => {
      const breakdown = tracker.getCostByModel();

      expect(breakdown['claude-haiku-4-5'].requests).toBe(2);
      expect(breakdown['claude-sonnet-4-6'].requests).toBe(1);
    });

    test('should sum tokens per model', () => {
      const breakdown = tracker.getCostByModel();

      // Haiku: (1k+100) + (2k+200) = 3.3k tokens
      expect(breakdown['claude-haiku-4-5'].tokens).toBe(3300);
      // Sonnet: 5k+500 = 5.5k tokens
      expect(breakdown['claude-sonnet-4-6'].tokens).toBe(5500);
    });

    test('should sum costs per model', () => {
      const breakdown = tracker.getCostByModel();

      expect(breakdown['claude-haiku-4-5'].cost).toBeGreaterThan(0);
      expect(breakdown['claude-sonnet-4-6'].cost).toBeGreaterThan(0);
    });
  });

  describe('clearEvents()', () => {
    test('should clear all recorded events', () => {
      tracker.recordUsage('project1', 'task', 'claude-haiku-4-5', 1000, 100, false, 100);
      expect(tracker.getEvents()).toHaveLength(1);

      tracker.clearEvents();
      expect(tracker.getEvents()).toHaveLength(0);
    });
  });
});
