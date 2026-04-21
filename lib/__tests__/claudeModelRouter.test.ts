/**
 * Unit Tests for ClaudeModelRouter
 * Tests model selection, cost calculation, and routing decisions
 */

import { ClaudeModelRouter, MODEL_CONFIG } from '../claudeModelRouter';

describe('ClaudeModelRouter', () => {
  let router: ClaudeModelRouter;

  beforeEach(() => {
    router = new ClaudeModelRouter('test-api-key');
  });

  describe('route()', () => {
    test('should select Haiku for simple classification task', async () => {
      const decision = await router.route({
        taskType: 'classify email as spam',
        estimatedInputTokens: 500,
        estimatedOutputTokens: 10,
        isUrgent: false,
      });

      expect(decision.modelId).toBe('claude-haiku-4-5');
      expect(decision.taskLevel).toBe('simple');
      expect(decision.reasoning).toContain('simple');
    });

    test('should select Sonnet for medium-complexity task', async () => {
      const decision = await router.route({
        taskType: 'generate code from specification',
        estimatedInputTokens: 10000,
        estimatedOutputTokens: 2000,
        isUrgent: false,
      });

      expect(decision.modelId).toBe('claude-sonnet-4-6');
      expect(decision.taskLevel).toBe('medium');
    });

    test('should select Opus for complex architecture task', async () => {
      const decision = await router.route({
        taskType: 'design system architecture for enterprise platform',
        estimatedInputTokens: 50000,
        estimatedOutputTokens: 5000,
        isUrgent: false,
      });

      expect(decision.modelId).toBe('claude-opus-4-6');
      expect(decision.taskLevel).toMatch(/complex|veryComplex/);
    });

    test('should recommend batch for non-urgent requests over $0.01', async () => {
      const decision = await router.route({
        taskType: 'analyze large dataset',
        estimatedInputTokens: 20000,
        estimatedOutputTokens: 1000,
        isUrgent: false,
      });

      expect(decision.batchRecommended).toBe(true);
      expect(decision.batchSavings).toBe(50);
    });

    test('should not recommend batch for urgent requests', async () => {
      const decision = await router.route({
        taskType: 'urgent customer support',
        estimatedInputTokens: 20000,
        estimatedOutputTokens: 1000,
        isUrgent: true,
      });

      expect(decision.batchRecommended).toBe(false);
    });

    test('should enforce budget limits', async () => {
      expect(async () => {
        await router.route({
          taskType: 'expensive task',
          estimatedInputTokens: 1000000,
          estimatedOutputTokens: 100000,
          isUrgent: false,
          budgetLimit: 100, // $1.00
        });
      }).rejects.toThrow();
    });

    test('should upgrade model for required capabilities', async () => {
      const decision = await router.route({
        taskType: 'classify simple image',
        estimatedInputTokens: 500,
        estimatedOutputTokens: 100,
        isUrgent: false,
        requiredCapabilities: {
          vision: true,
        },
      });

      const config = MODEL_CONFIG[decision.modelId];
      expect(config.capabilities.vision).toBe(true);
    });

    test('should calculate accurate costs', async () => {
      const decision = await router.route({
        taskType: 'analyze text',
        estimatedInputTokens: 10000,
        estimatedOutputTokens: 1000,
        isUrgent: false,
      });

      // Sonnet: 10k * $0.003/1k + 1k * $0.015/1k = $0.03 + $0.015 = $0.045
      expect(decision.estimatedCost).toBeCloseTo(0.045, 4);
    });
  });

  describe('analyzeTaskComplexity()', () => {
    test('should identify simple keywords', () => {
      const simple = [
        'classify this text',
        'extract email address',
        'summarize the document',
        'translate to French',
      ];

      simple.forEach((task) => {
        const decision = router['analyzeTaskComplexity'](task, 1000);
        expect(decision).toBe('simple');
      });
    });

    test('should identify medium keywords', () => {
      const medium = [
        'generate a blog post',
        'analyze market trends',
        'explain quantum computing',
        'debug this code',
      ];

      medium.forEach((task) => {
        const decision = router['analyzeTaskComplexity'](task, 5000);
        expect(decision).toBe('medium');
      });
    });

    test('should identify complex keywords', () => {
      const complex = [
        'design a microservices architecture',
        'plan a research strategy',
        'optimize database performance',
      ];

      complex.forEach((task) => {
        const decision = router['analyzeTaskComplexity'](task, 10000);
        expect(decision).toMatch(/complex|veryComplex/);
      });
    });

    test('should consider token count in complexity', () => {
      const generic = 'analyze';

      // Low tokens = simple
      expect(router['analyzeTaskComplexity'](generic, 100)).toBe('simple');

      // High tokens = complex
      expect(router['analyzeTaskComplexity'](generic, 100000)).toBe('complex');
    });
  });

  describe('ensureCapabilities()', () => {
    test('should not upgrade if model has all capabilities', () => {
      const result = router['ensureCapabilities']('claude-opus-4-7', {
        vision: true,
        thinking_adaptive: true,
      });

      expect(result).toBe('claude-opus-4-7');
    });

    test('should upgrade if capabilities are missing', () => {
      const result = router['ensureCapabilities']('claude-haiku-4-5', {
        thinking_adaptive: true,
      });

      expect(result).not.toBe('claude-haiku-4-5');
      expect(MODEL_CONFIG[result].capabilities.thinking_adaptive).toBe(true);
    });
  });

  describe('calculateCost()', () => {
    test('should calculate input token cost', () => {
      const cost = router['calculateCost']('claude-haiku-4-5', 1000, 0);
      expect(cost.inputTokensCost).toBeCloseTo(0.002, 5);
    });

    test('should calculate output token cost', () => {
      const cost = router['calculateCost']('claude-haiku-4-5', 0, 1000);
      expect(cost.outputTokensCost).toBeCloseTo(0.005, 5);
    });

    test('should calculate combined cost', () => {
      const cost = router['calculateCost']('claude-sonnet-4-6', 10000, 1000);
      // 10k * $0.003/1k + 1k * $0.015/1k = $0.03 + $0.015 = $0.045
      expect(cost.inputTokensCost + cost.outputTokensCost).toBeCloseTo(0.045, 4);
    });
  });

  describe('getAvailableModels()', () => {
    test('should return all available models', () => {
      const models = router.getAvailableModels();
      expect(models).toContain('claude-haiku-4-5');
      expect(models).toContain('claude-sonnet-4-6');
      expect(models).toContain('claude-opus-4-6');
      expect(models).toContain('claude-opus-4-7');
    });
  });

  describe('getModelConfig()', () => {
    test('should return config for valid model', () => {
      const config = router.getModelConfig('claude-haiku-4-5');
      expect(config).toBeDefined();
      expect(config?.displayName).toBe('Claude Haiku 4.5');
      expect(config?.inputCost).toBe(0.002 / 1000);
    });

    test('should return null for invalid model', () => {
      const config = router.getModelConfig('invalid-model' as any);
      expect(config).toBeNull();
    });
  });
});
