/**
 * Unit Tests for Task Analyzer
 * Tests task complexity analysis, capability detection, and token estimation
 */

import {
  analyzeTaskComplexity,
  detectRequiredCapabilities,
  estimateOutputTokens,
} from '../taskAnalyzer';

describe('TaskAnalyzer', () => {
  describe('analyzeTaskComplexity()', () => {
    test('should identify simple classification tasks', () => {
      const result = analyzeTaskComplexity('classify this email as spam or not', 500);

      expect(result.level).toBe('simple');
      expect(result.score).toBeLessThan(0.4);
      expect(result.reasoning).toContain('simple');
    });

    test('should identify simple extraction tasks', () => {
      const result = analyzeTaskComplexity('extract the email address from this text', 300);

      expect(result.level).toBe('simple');
    });

    test('should identify simple summarization tasks', () => {
      const result = analyzeTaskComplexity('summarize this document in 3 sentences', 400);

      expect(result.level).toBe('simple');
    });

    test('should identify medium-complexity tasks', () => {
      const result = analyzeTaskComplexity('generate a blog post about AI trends', 2000);

      expect(result.level).toBe('medium');
      expect(result.score).toBeGreaterThanOrEqual(0.4);
      expect(result.score).toBeLessThan(0.7);
    });

    test('should identify complex analysis tasks', () => {
      const result = analyzeTaskComplexity('analyze the market trends and provide recommendations', 5000);

      expect(result.level).toMatch(/complex|veryComplex/);
      expect(result.score).toBeGreaterThanOrEqual(0.6);
    });

    test('should identify very complex architecture tasks', () => {
      const result = analyzeTaskComplexity(
        'design a microservices architecture for an enterprise platform with millions of users',
        10000
      );

      expect(result.level).toMatch(/complex|veryComplex/);
      expect(result.score).toBeGreaterThanOrEqual(0.7);
    });

    test('should consider token count in complexity calculation', () => {
      const simpleLow = analyzeTaskComplexity('analyze data', 100);
      const simpleHigh = analyzeTaskComplexity('analyze data', 50000);

      expect(simpleHigh.score).toBeGreaterThan(simpleLow.score);
    });

    test('should identify length factor in complexity', () => {
      const result = analyzeTaskComplexity('x', 100000);

      expect(result.factors.lengthScore).toBeGreaterThan(0);
    });

    test('should calculate all complexity factors', () => {
      const result = analyzeTaskComplexity('generate code for a REST API with authentication', 3000);

      expect(result.factors).toHaveProperty('keywordScore');
      expect(result.factors).toHaveProperty('lengthScore');
      expect(result.factors).toHaveProperty('structureScore');
      expect(result.factors.keywordScore).toBeGreaterThanOrEqual(0);
      expect(result.factors.lengthScore).toBeGreaterThanOrEqual(0);
    });

    test('should include reasoning in result', () => {
      const result = analyzeTaskComplexity('do something', 1000);

      expect(result.reasoning).toBeDefined();
      expect(result.reasoning.length).toBeGreaterThan(0);
    });
  });

  describe('detectRequiredCapabilities()', () => {
    test('should detect vision capability need for image prompts', () => {
      const caps = detectRequiredCapabilities('analyze this image and describe what you see');

      expect(caps.vision).toBe(true);
    });

    test('should detect thinking capability for reasoning tasks', () => {
      const caps = detectRequiredCapabilities('think deeply about this problem and provide reasoning');

      expect(caps.thinking_adaptive).toBe(true);
    });

    test('should detect tool use for function calling needs', () => {
      const caps = detectRequiredCapabilities('call the weather API and analyze the data');

      expect(caps.toolUse).toBe(true);
    });

    test('should not require vision for text-only tasks', () => {
      const caps = detectRequiredCapabilities('summarize this text content');

      expect(caps.vision).toBeFalsy();
    });

    test('should not require thinking for simple tasks', () => {
      const caps = detectRequiredCapabilities('classify this as spam');

      expect(caps.thinking_adaptive).toBeFalsy();
    });

    test('should detect multiple capabilities at once', () => {
      const caps = detectRequiredCapabilities(
        'analyze this image using a vision model and call the API to get more data'
      );

      expect(caps.vision).toBe(true);
      expect(caps.toolUse).toBe(true);
    });

    test('should handle edge case of no capabilities needed', () => {
      const caps = detectRequiredCapabilities('simple text task');

      expect(Object.values(caps).some((v) => v === true)).toBeFalsy();
    });
  });

  describe('estimateOutputTokens()', () => {
    test('should estimate tokens for classification task', () => {
      const estimate = estimateOutputTokens('classify', 1000);

      expect(estimate).toBeGreaterThan(0);
      expect(estimate).toBeLessThan(500); // Should be small for classification
    });

    test('should estimate tokens for summarization task', () => {
      const estimate = estimateOutputTokens('summarize', 5000);

      expect(estimate).toBeGreaterThan(100);
      expect(estimate).toBeLessThan(1000);
    });

    test('should estimate tokens for generation task', () => {
      const estimate = estimateOutputTokens('generate', 2000);

      expect(estimate).toBeGreaterThan(500);
      expect(estimate).toBeLessThan(4096);
    });

    test('should estimate tokens for analysis task', () => {
      const estimate = estimateOutputTokens('analyze', 3000);

      expect(estimate).toBeGreaterThan(200);
    });

    test('should handle unknown task types', () => {
      const estimate = estimateOutputTokens('unknown_task', 1000);

      expect(estimate).toBeGreaterThan(0);
      expect(estimate).toBeLessThanOrEqual(4096);
    });

    test('should scale with input size for generation tasks', () => {
      const smallEstimate = estimateOutputTokens('generate', 1000);
      const largeEstimate = estimateOutputTokens('generate', 10000);

      expect(largeEstimate).toBeGreaterThan(smallEstimate);
    });

    test('should cap output at 4096 tokens', () => {
      const estimate = estimateOutputTokens('generate', 100000);

      expect(estimate).toBeLessThanOrEqual(4096);
    });
  });

  describe('integration scenarios', () => {
    test('should analyze complex research task completely', () => {
      const prompt =
        'Analyze the latest research papers on quantum computing and provide a comprehensive summary with key findings';
      const complexity = analyzeTaskComplexity(prompt, 5000);
      const caps = detectRequiredCapabilities(prompt);
      const outputTokens = estimateOutputTokens('analyze', 5000);

      expect(complexity.level).toBeDefined();
      expect(complexity.score).toBeGreaterThan(0);
      expect(outputTokens).toBeGreaterThan(500);
    });

    test('should analyze image analysis task with capabilities', () => {
      const prompt = 'Look at this image and identify all objects with their bounding boxes';
      const complexity = analyzeTaskComplexity(prompt, 2000);
      const caps = detectRequiredCapabilities(prompt);

      expect(caps.vision).toBe(true);
      expect(complexity.level).toMatch(/medium|complex/);
    });

    test('should estimate tokens for multi-step reasoning', () => {
      const prompt =
        'Think step-by-step about this problem: How would you design a distributed system for real-time data processing?';
      const complexity = analyzeTaskComplexity(prompt, 4000);
      const caps = detectRequiredCapabilities(prompt);
      const outputTokens = estimateOutputTokens('design', 4000);

      expect(caps.thinking_adaptive).toBe(true);
      expect(outputTokens).toBeGreaterThan(500);
      expect(complexity.score).toBeGreaterThan(0.5);
    });
  });
});
