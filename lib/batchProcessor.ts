/**
 * Batch API Processor Module
 * Handles non-urgent requests via Batch API for 50% cost savings
 */

import Anthropic from "@anthropic-ai/sdk";

/**
 * Batch request item
 */
export interface BatchItem {
  customId: string;
  params: Anthropic.MessageCreateParamsNonStreaming;
}

/**
 * Batch submission result
 */
export interface BatchSubmission {
  batchId: string;
  requestCount: number;
  submittedAt: string;
  estimatedCompletionTime: string;
}

/**
 * Batch result
 */
export interface BatchResult {
  customId: string;
  message?: Anthropic.Message;
  error?: {
    type: string;
    message: string;
  };
}

/**
 * Batch processor for non-urgent requests
 */
export class BatchProcessor {
  private client: Anthropic;
  private activeBatches: Map<string, BatchItem[]> = new Map();

  constructor(apiKey?: string) {
    this.client = new Anthropic({
      apiKey: apiKey || process.env.ANTHROPIC_API_KEY,
    });
  }

  /**
   * Convert routing decision to batch-ready format
   *
   * @param request Message creation parameters
   * @param customId Unique identifier for this request
   * @returns Batch item
   */
  static createBatchItem(
    request: Anthropic.MessageCreateParamsNonStreaming,
    customId: string
  ): BatchItem {
    return {
      customId,
      params: request,
    };
  }

  /**
   * Submit a batch of requests
   *
   * @param items Array of batch items
   * @returns Batch submission details
   */
  async submitBatch(items: BatchItem[]): Promise<BatchSubmission> {
    if (items.length === 0) {
      throw new Error("Cannot submit empty batch");
    }

    if (items.length > 100000) {
      throw new Error("Batch exceeds maximum size of 100,000 requests");
    }

    // Format requests for Batch API
    const requests = items.map((item) => ({
      custom_id: item.customId,
      params: item.params,
    }));

    // Submit batch
    const batch = await this.client.messages.batches.create({
      requests: requests as any, // Type assertion for SDK compatibility
    });

    // Store batch reference
    this.activeBatches.set(batch.id, items);

    // Estimate completion time (typically 1 hour for most batches)
    const estimatedCompletion = new Date();
    estimatedCompletion.setHours(estimatedCompletion.getHours() + 1);

    return {
      batchId: batch.id,
      requestCount: items.length,
      submittedAt: new Date().toISOString(),
      estimatedCompletionTime: estimatedCompletion.toISOString(),
    };
  }

  /**
   * Check batch status
   *
   * @param batchId Batch ID to check
   * @returns Batch status
   */
  async getBatchStatus(
    batchId: string
  ): Promise<{
    status: "queued" | "in_progress" | "ended";
    succeeded: number;
    errored: number;
    expired: number;
    canceled: number;
  }> {
    const batch = await this.client.messages.batches.retrieve(batchId);

    return {
      status: batch.processing_status,
      succeeded: batch.request_counts.succeeded,
      errored: batch.request_counts.errored,
      expired: batch.request_counts.expired,
      canceled: batch.request_counts.canceled,
    };
  }

  /**
   * Retrieve batch results
   * Waits for batch completion if not ready
   *
   * @param batchId Batch ID
   * @param pollIntervalMs Polling interval in milliseconds
   * @param maxWaitMs Maximum time to wait before returning partial results
   * @returns Array of batch results
   */
  async *getBatchResults(
    batchId: string,
    pollIntervalMs: number = 5000,
    maxWaitMs: number = 3600000 // 1 hour default
  ): AsyncGenerator<BatchResult> {
    const startTime = Date.now();
    let isComplete = false;

    while (!isComplete && Date.now() - startTime < maxWaitMs) {
      const batch = await this.client.messages.batches.retrieve(batchId);

      if (batch.processing_status === "ended") {
        isComplete = true;

        // Yield all results
        for await (const result of this.client.messages.batches.results(
          batchId
        )) {
          const batchResult: BatchResult = {
            customId: result.custom_id,
          };

          if (result.result.type === "succeeded") {
            batchResult.message = result.result.message;
          } else if (result.result.type === "errored") {
            batchResult.error = {
              type: result.result.error.type,
              message: result.result.error.message || "Unknown error",
            };
          } else if (result.result.type === "expired") {
            batchResult.error = {
              type: "expired",
              message: "Request expired before processing",
            };
          }

          yield batchResult;
        }
      } else {
        // Poll and wait
        await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
      }
    }

    if (!isComplete) {
      console.warn(`Batch ${batchId} did not complete within ${maxWaitMs}ms`);
    }
  }

  /**
   * Cancel a batch
   *
   * @param batchId Batch ID to cancel
   * @returns Cancellation status
   */
  async cancelBatch(
    batchId: string
  ): Promise<{ status: "canceling" | "canceled" }> {
    const batch = await this.client.messages.batches.cancel(batchId);

    return {
      status: batch.processing_status,
    };
  }

  /**
   * Format a request for batch submission
   * Handles model selection and parameter adjustment
   *
   * @param modelId Model to use
   * @param messages Messages array
   * @param system Optional system prompt
   * @returns Batch-ready request parameters
   */
  static formatBatchRequest(
    modelId: string,
    messages: Anthropic.MessageParam[],
    system?: string | Anthropic.TextBlockParam[]
  ): Anthropic.MessageCreateParamsNonStreaming {
    return {
      model: modelId,
      max_tokens: 4096, // Batch API default
      messages,
      ...(system && { system }),
    } as Anthropic.MessageCreateParamsNonStreaming;
  }

  /**
   * Get list of active batches
   *
   * @returns Array of batch IDs
   */
  getActiveBatches(): string[] {
    return Array.from(this.activeBatches.keys());
  }

  /**
   * Create a batch recommendation based on cost and urgency
   *
   * @param totalCost Total estimated cost
   * @param isUrgent Whether request is time-sensitive
   * @returns Recommendation object
   */
  static recommendBatchUsage(
    totalCost: number,
    isUrgent: boolean
  ): {
    shouldUseBatch: boolean;
    savingsUSD: number;
    savingsPercent: number;
    reasoning: string;
  } {
    const savingsUSD = totalCost * 0.5;
    const savingsPercent = 50;

    const shouldUseBatch = !isUrgent && totalCost > 0.01;

    let reasoning = "";
    if (!shouldUseBatch && isUrgent) {
      reasoning = "Request is time-sensitive; use standard API";
    } else if (!shouldUseBatch && totalCost <= 0.01) {
      reasoning = "Request cost too low to warrant batch processing";
    } else {
      reasoning = `Batch recommended: save ${CostCalculator.formatCost(savingsUSD)} (50%)`;
    }

    return {
      shouldUseBatch,
      savingsUSD,
      savingsPercent,
      reasoning,
    };
  }

  /**
   * Batch status monitor (for tracking)
   *
   * @param batchId Batch ID
   * @returns Formatted status string
   */
  async getFormattedStatus(batchId: string): Promise<string> {
    const status = await this.getBatchStatus(batchId);

    let output = `Batch ${batchId}\n`;
    output += `Status: ${status.status}\n`;
    output += `Succeeded: ${status.succeeded}\n`;
    output += `Errored: ${status.errored}\n`;

    if (status.expired > 0) output += `Expired: ${status.expired}\n`;
    if (status.canceled > 0) output += `Canceled: ${status.canceled}\n`;

    return output;
  }
}

/**
 * Helper: Cost formatter for batch processor output
 */
class CostCalculator {
  static formatCost(cost: number): string {
    if (cost < 0.001) {
      return `$${(cost * 1000).toFixed(2)}m`;
    }
    return `$${cost.toFixed(4)}`;
  }
}

export default BatchProcessor;
