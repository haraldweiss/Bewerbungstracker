/**
 * Unit Tests for CostCalculator
 * Tests cost estimation, logging, and budget tracking
 */

import { CostCalculator } from '../costCalculator';

describe('CostCalculator', () => {
  let calculator: CostCalculator;

  beforeEach(() => {
    calculator = new CostCalculator(100); // $100 monthly budget
  });

  describe('estimateCost()', () => {
    test('should calculate Haiku cost correctly', () => {
      const estimate = calculator.estimateCost(
        'claude-haiku-4-5',
        10000,
        1000,
        false
      );

      expect(estimate.modelId).toBe('claude-haiku-4-5');
      expect(estimate.inputCost).toBeCloseTo(0.02, 4); // 10k * $0.002/1k
      expect(estimate.outputCost).toBeCloseTo(0.005, 5); // 1k * $0.005/1k
      expect(estimate.totalCost).toBeCloseTo(0.025, 4);
    });

    test('should recommend batch for non-urgent requests', () => {
      const estimate = calculator.estimateCost(
        'claude-haiku-4-5',
        10000,
        1000,
        false
      );

      expect(estimate.isBatchEligible).toBe(true);
      expect(estimate.batchCost).toBeCloseTo(0.0125, 4); // 50% discount
      expect(estimate.costSavingsWithBatch).toBeCloseTo(0.0125, 4);
    });

    test('should not recommend batch for urgent requests', () => {
      const estimate = calculator.estimateCost(
        'claude-haiku-4-5',
        10000,
        1000,
        true // urgent
      );

      expect(estimate.isBatchEligible).toBe(false);
      expect(estimate.batchCost).toBeUndefined();
    });

    test('should not recommend batch for low-cost requests', () => {
      const estimate = calculator.estimateCost(
        'claude-haiku-4-5',
        100,
        10,
        false // Would be $0.00022, under $0.01 threshold
      );

      expect(estimate.isBatchEligible).toBe(false);
    });
  });

  describe('logUsage()', () => {
    test('should log usage correctly', () => {
      calculator.logUsage('claude-haiku-4-5', 5000, 500, 'test', false);

      const logs = calculator.getLogs();
      expect(logs).toHaveLength(1);
      expect(logs[0].modelId).toBe('claude-haiku-4-5');
      expect(logs[0].inputTokens).toBe(5000);
      expect(logs[0].outputTokens).toBe(500);
      expect(logs[0].isBatch).toBe(false);
    });

    test('should calculate correct cost in log', () => {
      calculator.logUsage('claude-haiku-4-5', 10000, 1000, 'test', false);

      const logs = calculator.getLogs();
      expect(logs[0].actualCost).toBeCloseTo(0.025, 4);
    });

    test('should apply 50% discount for batch', () => {
      calculator.logUsage('claude-haiku-4-5', 10000, 1000, 'test', true);

      const logs = calculator.getLogs();
      expect(logs[0].actualCost).toBeCloseTo(0.0125, 4); // 50% off
    });

    test('should warn when exceeding budget', () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
      const smallBudgetCalc = new CostCalculator(0.01); // $0.01 budget

      smallBudgetCalc.logUsage('claude-opus-4-7', 10000, 5000, 'expensive', false);

      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('exceeds budget')
      );

      warnSpy.mockRestore();
    });
  });

  describe('getTotalCost()', () => {
    test('should sum costs over period', () => {
      calculator.logUsage('claude-haiku-4-5', 1000, 100, 'test1', false);
      calculator.logUsage('claude-haiku-4-5', 2000, 200, 'test2', false);

      const total = calculator.getTotalCost(30);
      expect(total).toBeCloseTo(0.005, 4); // $0.002 + $0.003
    });

    test('should filter by days', () => {
      calculator.logUsage('claude-haiku-4-5', 1000, 100, 'test', false);

      const total = calculator.getTotalCost(1); // Only last day
      expect(total).toBeGreaterThan(0);

      const totalLong = calculator.getTotalCost(365);
      expect(totalLong).toEqual(total); // Same since only one log
    });
  });

  describe('getMonthlySpend()', () => {
    test('should calculate current month spend', () => {
      calculator.logUsage('claude-haiku-4-5', 10000, 1000, 'test', false);

      const monthly = calculator.getMonthlySpend();
      expect(monthly).toBeCloseTo(0.025, 4);
    });
  });

  describe('getStatistics()', () => {
    test('should return correct statistics', () => {
      calculator.logUsage('claude-haiku-4-5', 5000, 500, 'test1', false);
      calculator.logUsage('claude-sonnet-4-6', 10000, 1000, 'test2', false);

      const stats = calculator.getStatistics();

      expect(stats.totalRequests).toBe(2);
      expect(stats.totalTokens).toBe(16500); // 5k+500+10k+1k
      expect(stats.modelUsage['claude-haiku-4-5'].requests).toBe(1);
      expect(stats.modelUsage['claude-sonnet-4-6'].requests).toBe(1);
    });

    test('should calculate batch savings', () => {
      calculator.logUsage('claude-haiku-4-5', 10000, 1000, 'test1', false);
      calculator.logUsage('claude-haiku-4-5', 10000, 1000, 'test2', true); // batch

      const stats = calculator.getStatistics();

      // First request: full price $0.025, if it were batched would cost $0.0125
      // So savings = $0.025 - $0.0125 = $0.0125
      expect(stats.batchSavings).toBeGreaterThan(0);
    });

    test('should include model breakdown', () => {
      calculator.logUsage('claude-haiku-4-5', 1000, 100, 'test1', false);
      calculator.logUsage('claude-sonnet-4-6', 2000, 200, 'test2', false);

      const stats = calculator.getStatistics();

      expect(Object.keys(stats.modelUsage)).toContain('claude-haiku-4-5');
      expect(Object.keys(stats.modelUsage)).toContain('claude-sonnet-4-6');
    });
  });

  describe('formatCost()', () => {
    test('should format USD properly', () => {
      expect(CostCalculator.formatCost(0.5)).toBe('$0.5000');
      expect(CostCalculator.formatCost(0.0001)).toBe('$0.1000m');
      expect(CostCalculator.formatCost(1.5)).toBe('$1.5000');
    });
  });

  describe('exportLogs()', () => {
    test('should export logs as JSON', () => {
      calculator.logUsage('claude-haiku-4-5', 1000, 100, 'test', false);

      const json = calculator.exportLogs();
      const parsed = JSON.parse(json);

      expect(Array.isArray(parsed)).toBe(true);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].modelId).toBe('claude-haiku-4-5');
    });
  });

  describe('generateReport()', () => {
    test('should generate formatted report', () => {
      calculator.logUsage('claude-haiku-4-5', 1000, 100, 'test', false);

      const report = calculator.generateReport();

      expect(report).toContain('Total Requests: 1');
      expect(report).toContain('claude-haiku-4-5');
      expect(report).toContain('Monthly Budget');
    });
  });

  describe('clearLogs()', () => {
    test('should clear all logs', () => {
      calculator.logUsage('claude-haiku-4-5', 1000, 100, 'test', false);
      expect(calculator.getLogs()).toHaveLength(1);

      calculator.clearLogs();
      expect(calculator.getLogs()).toHaveLength(0);
    });
  });
});
