/**
 * Unit Tests for Batch Processor
 * Tests batch submission, status polling, result retrieval, and recommendations
 */

import BatchProcessor, { BatchItem, BatchSubmission, BatchResult } from '../batchProcessor';
import Anthropic from '@anthropic-ai/sdk';

jest.mock('@anthropic-ai/sdk');

describe('BatchProcessor', () => {
  let processor: BatchProcessor;
  let mockClient: jest.Mocked<Anthropic>;

  beforeEach(() => {
    mockClient = new Anthropic() as jest.Mocked<Anthropic>;
    processor = new BatchProcessor('test-api-key');
  });

  describe('createBatchItem()', () => {
    test('should create batch item with custom ID', () => {
      const params: Anthropic.MessageCreateParamsNonStreaming = {
        model: 'claude-opus-4-7',
        max_tokens: 1024,
        messages: [{ role: 'user', content: 'Hello' }],
      };

      const item = BatchProcessor.createBatchItem(params, 'request-001');

      expect(item.customId).toBe('request-001');
      expect(item.params).toEqual(params);
    });

    test('should preserve request parameters', () => {
      const params: Anthropic.MessageCreateParamsNonStreaming = {
        model: 'claude-haiku-4-5',
        max_tokens: 256,
        messages: [
          { role: 'user', content: 'Test' },
          { role: 'assistant', content: 'Response' },
        ],
      };

      const item = BatchProcessor.createBatchItem(params, 'multi-turn-001');

      expect(item.params.messages).toHaveLength(2);
      expect(item.params.model).toBe('claude-haiku-4-5');
    });
  });

  describe('submitBatch()', () => {
    test('should submit batch with correct format', async () => {
      const items: BatchItem[] = [
        BatchProcessor.createBatchItem(
          {
            model: 'claude-haiku-4-5',
            max_tokens: 256,
            messages: [{ role: 'user', content: 'Test 1' }],
          },
          'req-1'
        ),
        BatchProcessor.createBatchItem(
          {
            model: 'claude-haiku-4-5',
            max_tokens: 256,
            messages: [{ role: 'user', content: 'Test 2' }],
          },
          'req-2'
        ),
      ];

      const mockBatch = {
        id: 'batch-123',
        processing_status: 'queued' as const,
        request_counts: { succeeded: 0, errored: 0, expired: 0, canceled: 0 },
      };

      (mockClient.messages.batches.create as jest.Mock).mockResolvedValue(mockBatch);

      const result = await processor.submitBatch(items);

      expect(result.batchId).toBe('batch-123');
      expect(result.requestCount).toBe(2);
      expect(result.submittedAt).toBeDefined();
      expect(result.estimatedCompletionTime).toBeDefined();
    });

    test('should reject empty batch', async () => {
      await expect(processor.submitBatch([])).rejects.toThrow('Cannot submit empty batch');
    });

    test('should reject batch exceeding max size', async () => {
      const items: BatchItem[] = Array.from({ length: 100001 }, (_, i) =>
        BatchProcessor.createBatchItem(
          {
            model: 'claude-haiku-4-5',
            max_tokens: 256,
            messages: [{ role: 'user', content: `Test ${i}` }],
          },
          `req-${i}`
        )
      );

      await expect(processor.submitBatch(items)).rejects.toThrow(
        'Batch exceeds maximum size of 100,000 requests'
      );
    });

    test('should format requests correctly for API', async () => {
      const items: BatchItem[] = [
        BatchProcessor.createBatchItem(
          {
            model: 'claude-sonnet-4-6',
            max_tokens: 1024,
            messages: [{ role: 'user', content: 'Complex query' }],
            system: 'You are helpful',
          },
          'special-req'
        ),
      ];

      const mockBatch = {
        id: 'batch-456',
        processing_status: 'queued' as const,
        request_counts: { succeeded: 0, errored: 0, expired: 0, canceled: 0 },
      };

      (mockClient.messages.batches.create as jest.Mock).mockResolvedValue(mockBatch);

      await processor.submitBatch(items);

      expect(mockClient.messages.batches.create).toHaveBeenCalled();
    });

    test('should store batch reference internally', async () => {
      const items: BatchItem[] = [
        BatchProcessor.createBatchItem(
          {
            model: 'claude-haiku-4-5',
            max_tokens: 256,
            messages: [{ role: 'user', content: 'Test' }],
          },
          'req-1'
        ),
      ];

      const mockBatch = {
        id: 'batch-789',
        processing_status: 'queued' as const,
        request_counts: { succeeded: 0, errored: 0, expired: 0, canceled: 0 },
      };

      (mockClient.messages.batches.create as jest.Mock).mockResolvedValue(mockBatch);

      await processor.submitBatch(items);

      const activeBatches = processor.getActiveBatches();
      expect(activeBatches).toContain('batch-789');
    });
  });

  describe('getBatchStatus()', () => {
    test('should return batch status correctly', async () => {
      const mockBatch = {
        id: 'batch-123',
        processing_status: 'in_progress' as const,
        request_counts: {
          succeeded: 50,
          errored: 2,
          expired: 0,
          canceled: 0,
        },
      };

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);

      const status = await processor.getBatchStatus('batch-123');

      expect(status.status).toBe('in_progress');
      expect(status.succeeded).toBe(50);
      expect(status.errored).toBe(2);
    });

    test('should handle batch completion status', async () => {
      const mockBatch = {
        id: 'batch-456',
        processing_status: 'ended' as const,
        request_counts: {
          succeeded: 100,
          errored: 0,
          expired: 0,
          canceled: 0,
        },
      };

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);

      const status = await processor.getBatchStatus('batch-456');

      expect(status.status).toBe('ended');
      expect(status.succeeded).toBe(100);
    });
  });

  describe('getBatchResults()', () => {
    test('should yield results as they complete', async () => {
      const mockBatch = {
        id: 'batch-123',
        processing_status: 'ended' as const,
        request_counts: {
          succeeded: 2,
          errored: 0,
          expired: 0,
          canceled: 0,
        },
      };

      const mockResults = [
        {
          custom_id: 'req-1',
          result: {
            type: 'succeeded' as const,
            message: { id: 'msg-1', content: [{ type: 'text' as const, text: 'Response 1' }] },
          },
        },
        {
          custom_id: 'req-2',
          result: {
            type: 'succeeded' as const,
            message: { id: 'msg-2', content: [{ type: 'text' as const, text: 'Response 2' }] },
          },
        },
      ];

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);
      (mockClient.messages.batches.results as jest.Mock).mockReturnValue(
        (async function* () {
          for (const result of mockResults) {
            yield result;
          }
        })()
      );

      const results: BatchResult[] = [];
      for await (const result of processor.getBatchResults('batch-123')) {
        results.push(result);
      }

      expect(results).toHaveLength(2);
      expect(results[0].customId).toBe('req-1');
      expect(results[1].customId).toBe('req-2');
    });

    test('should handle errored results', async () => {
      const mockBatch = {
        id: 'batch-123',
        processing_status: 'ended' as const,
        request_counts: { succeeded: 1, errored: 1, expired: 0, canceled: 0 },
      };

      const mockResults = [
        {
          custom_id: 'req-1',
          result: {
            type: 'errored' as const,
            error: { type: 'invalid_request_error', message: 'Invalid model' },
          },
        },
      ];

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);
      (mockClient.messages.batches.results as jest.Mock).mockReturnValue(
        (async function* () {
          for (const result of mockResults) {
            yield result;
          }
        })()
      );

      const results: BatchResult[] = [];
      for await (const result of processor.getBatchResults('batch-123')) {
        results.push(result);
      }

      expect(results[0].error).toBeDefined();
      expect(results[0].error?.type).toBe('invalid_request_error');
    });

    test('should handle expired results', async () => {
      const mockBatch = {
        id: 'batch-123',
        processing_status: 'ended' as const,
        request_counts: { succeeded: 0, errored: 0, expired: 1, canceled: 0 },
      };

      const mockResults = [
        {
          custom_id: 'req-1',
          result: { type: 'expired' as const },
        },
      ];

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);
      (mockClient.messages.batches.results as jest.Mock).mockReturnValue(
        (async function* () {
          for (const result of mockResults) {
            yield result;
          }
        })()
      );

      const results: BatchResult[] = [];
      for await (const result of processor.getBatchResults('batch-123')) {
        results.push(result);
      }

      expect(results[0].error).toBeDefined();
      expect(results[0].error?.type).toBe('expired');
    });
  });

  describe('cancelBatch()', () => {
    test('should cancel batch successfully', async () => {
      const mockBatch = {
        id: 'batch-123',
        processing_status: 'canceling' as const,
        request_counts: { succeeded: 0, errored: 0, expired: 0, canceled: 0 },
      };

      (mockClient.messages.batches.cancel as jest.Mock).mockResolvedValue(mockBatch);

      const result = await processor.cancelBatch('batch-123');

      expect(result.status).toBe('canceling');
      expect(mockClient.messages.batches.cancel).toHaveBeenCalledWith('batch-123');
    });
  });

  describe('formatBatchRequest()', () => {
    test('should format request with model and messages', () => {
      const messages: Anthropic.MessageParam[] = [{ role: 'user', content: 'Test' }];
      const request = BatchProcessor.formatBatchRequest('claude-opus-4-7', messages);

      expect(request.model).toBe('claude-opus-4-7');
      expect(request.messages).toEqual(messages);
      expect(request.max_tokens).toBe(4096);
    });

    test('should include optional system prompt', () => {
      const messages: Anthropic.MessageParam[] = [{ role: 'user', content: 'Test' }];
      const systemPrompt = 'You are a helpful assistant';

      const request = BatchProcessor.formatBatchRequest(
        'claude-sonnet-4-6',
        messages,
        systemPrompt
      );

      expect(request.system).toBe(systemPrompt);
    });

    test('should handle text block system prompt', () => {
      const messages: Anthropic.MessageParam[] = [{ role: 'user', content: 'Test' }];
      const systemBlocks: Anthropic.TextBlockParam[] = [
        { type: 'text', text: 'System instruction 1' },
        { type: 'text', text: 'System instruction 2' },
      ];

      const request = BatchProcessor.formatBatchRequest(
        'claude-haiku-4-5',
        messages,
        systemBlocks
      );

      expect(request.system).toEqual(systemBlocks);
    });
  });

  describe('getActiveBatches()', () => {
    test('should return array of active batch IDs', async () => {
      const items: BatchItem[] = [
        BatchProcessor.createBatchItem(
          {
            model: 'claude-haiku-4-5',
            max_tokens: 256,
            messages: [{ role: 'user', content: 'Test' }],
          },
          'req-1'
        ),
      ];

      const mockBatch = {
        id: 'batch-new',
        processing_status: 'queued' as const,
        request_counts: { succeeded: 0, errored: 0, expired: 0, canceled: 0 },
      };

      (mockClient.messages.batches.create as jest.Mock).mockResolvedValue(mockBatch);

      await processor.submitBatch(items);

      const active = processor.getActiveBatches();
      expect(Array.isArray(active)).toBe(true);
      expect(active).toContain('batch-new');
    });

    test('should return empty array initially', () => {
      const active = processor.getActiveBatches();
      expect(active).toEqual([]);
    });
  });

  describe('recommendBatchUsage()', () => {
    test('should recommend batch for non-urgent requests over threshold', () => {
      const rec = BatchProcessor.recommendBatchUsage(0.05, false);

      expect(rec.shouldUseBatch).toBe(true);
      expect(rec.savingsPercent).toBe(50);
      expect(rec.savingsUSD).toBeCloseTo(0.025, 3);
    });

    test('should not recommend batch for urgent requests', () => {
      const rec = BatchProcessor.recommendBatchUsage(0.05, true);

      expect(rec.shouldUseBatch).toBe(false);
      expect(rec.reasoning).toContain('time-sensitive');
    });

    test('should not recommend batch for low-cost requests', () => {
      const rec = BatchProcessor.recommendBatchUsage(0.005, false);

      expect(rec.shouldUseBatch).toBe(false);
      expect(rec.reasoning).toContain('too low');
    });

    test('should calculate 50% savings correctly', () => {
      const rec = BatchProcessor.recommendBatchUsage(1.0, false);

      expect(rec.savingsUSD).toBeCloseTo(0.5, 2);
      expect(rec.savingsPercent).toBe(50);
    });
  });

  describe('getFormattedStatus()', () => {
    test('should return formatted status string', async () => {
      const mockBatch = {
        id: 'batch-123',
        processing_status: 'in_progress' as const,
        request_counts: { succeeded: 75, errored: 2, expired: 0, canceled: 0 },
      };

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);

      const status = await processor.getFormattedStatus('batch-123');

      expect(status).toContain('batch-123');
      expect(status).toContain('in_progress');
      expect(status).toContain('75');
      expect(status).toContain('2');
    });

    test('should include expired and canceled counts when present', async () => {
      const mockBatch = {
        id: 'batch-456',
        processing_status: 'ended' as const,
        request_counts: { succeeded: 98, errored: 1, expired: 1, canceled: 0 },
      };

      (mockClient.messages.batches.retrieve as jest.Mock).mockResolvedValue(mockBatch);

      const status = await processor.getFormattedStatus('batch-456');

      expect(status).toContain('Expired: 1');
    });
  });
});
