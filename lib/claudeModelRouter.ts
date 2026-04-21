/**
 * Universal Claude API Model Router
 * Intelligent model selection based on task complexity and cost optimization
 */

import Anthropic from "@anthropic-ai/sdk";

/**
 * Supported Claude models with pricing and capabilities
 */
export const MODEL_CONFIG = {
  "claude-haiku-4-5": {
    displayName: "Claude Haiku 4.5",
    inputCost: 0.002 / 1000, // $0.002 per 1K input tokens
    outputCost: 0.005 / 1000, // $0.005 per 1K output tokens
    maxContextWindow: 200000,
    maxOutputTokens: 64000,
    capabilities: {
      vision: true,
      thinking: false,
      thinking_adaptive: false,
      toolUse: true,
      batches: true,
    },
  },
  "claude-sonnet-4-6": {
    displayName: "Claude Sonnet 4.6",
    inputCost: 0.003 / 1000, // $0.003 per 1K input tokens
    outputCost: 0.015 / 1000, // $0.015 per 1K output tokens
    maxContextWindow: 1000000,
    maxOutputTokens: 64000,
    capabilities: {
      vision: true,
      thinking: true,
      thinking_adaptive: true,
      toolUse: true,
      batches: true,
    },
  },
  "claude-opus-4-6": {
    displayName: "Claude Opus 4.6",
    inputCost: 0.005 / 1000, // $0.005 per 1K input tokens
    outputCost: 0.025 / 1000, // $0.025 per 1K output tokens
    maxContextWindow: 1000000,
    maxOutputTokens: 128000,
    capabilities: {
      vision: true,
      thinking: true,
      thinking_adaptive: true,
      toolUse: true,
      batches: true,
    },
  },
  "claude-opus-4-7": {
    displayName: "Claude Opus 4.7",
    inputCost: 0.005 / 1000, // $0.005 per 1K input tokens
    outputCost: 0.025 / 1000, // $0.025 per 1K output tokens
    maxContextWindow: 1000000,
    maxOutputTokens: 128000,
    capabilities: {
      vision: true,
      thinking: false, // only adaptive thinking
      thinking_adaptive: true,
      toolUse: true,
      batches: true,
    },
  },
} as const;

/**
 * Task complexity levels used for model selection
 */
export type TaskLevel = "simple" | "medium" | "complex" | "veryComplex";

/**
 * Model selection criteria
 */
export interface RoutingContext {
  /** Task description or prompt */
  taskType: string;
  /** Estimated input tokens */
  estimatedInputTokens: number;
  /** Estimated output tokens */
  estimatedOutputTokens: number;
  /** Whether this is a time-sensitive request */
  isUrgent: boolean;
  /** Optional budget limit in cents */
  budgetLimit?: number;
  /** Required model capabilities */
  requiredCapabilities?: Partial<
    typeof MODEL_CONFIG["claude-haiku-4-5"]["capabilities"]
  >;
}

/**
 * Selected model with routing decision details
 */
export interface RoutingDecision {
  /** Selected model ID */
  modelId: keyof typeof MODEL_CONFIG;
  /** Task complexity level that influenced the decision */
  taskLevel: TaskLevel;
  /** Estimated cost in USD */
  estimatedCost: number;
  /** Cost breakdown */
  costBreakdown: {
    inputTokensCost: number;
    outputTokensCost: number;
  };
  /** Reasoning for the selection */
  reasoning: string;
  /** Whether batch API is recommended */
  batchRecommended: boolean;
  /** Cost savings with batch API (%) */
  batchSavings?: number;
}

/**
 * Central model routing engine
 */
export class ClaudeModelRouter {
  private client: Anthropic;

  constructor(apiKey?: string) {
    this.client = new Anthropic({
      apiKey: apiKey || process.env.ANTHROPIC_API_KEY,
    });
  }

  /**
   * Route a task to the optimal Claude model
   * Considers complexity, cost, and urgency
   *
   * @param context Routing context with task details
   * @returns Routing decision with selected model
   */
  async route(context: RoutingContext): Promise<RoutingDecision> {
    // Analyze task complexity
    const taskLevel = this.analyzeTaskComplexity(
      context.taskType,
      context.estimatedInputTokens
    );

    // Select model based on complexity
    let selectedModel: keyof typeof MODEL_CONFIG;

    if (taskLevel === "simple") {
      selectedModel = "claude-haiku-4-5";
    } else if (taskLevel === "medium") {
      selectedModel = "claude-sonnet-4-6";
    } else if (taskLevel === "complex") {
      selectedModel = "claude-opus-4-6";
    } else {
      // veryComplex
      selectedModel = "claude-opus-4-7";
    }

    // Check required capabilities
    if (context.requiredCapabilities) {
      selectedModel = this.ensureCapabilities(
        selectedModel,
        context.requiredCapabilities
      );
    }

    // Calculate cost
    const costBreakdown = this.calculateCost(
      selectedModel,
      context.estimatedInputTokens,
      context.estimatedOutputTokens
    );

    const estimatedCost =
      costBreakdown.inputTokensCost + costBreakdown.outputTokensCost;

    // Check budget limit
    if (context.budgetLimit && estimatedCost > context.budgetLimit / 100) {
      throw new Error(
        `Estimated cost $${estimatedCost.toFixed(4)} exceeds budget $${(context.budgetLimit / 100).toFixed(4)}`
      );
    }

    // Determine batch recommendation
    const batchRecommended = !context.isUrgent && estimatedCost > 0.01; // >$0.01
    const batchSavings = batchRecommended ? 50 : undefined;

    const reasoning = this.generateReasoning(
      taskLevel,
      selectedModel,
      context.isUrgent
    );

    return {
      modelId: selectedModel,
      taskLevel,
      estimatedCost,
      costBreakdown,
      reasoning,
      batchRecommended,
      batchSavings,
    };
  }

  /**
   * Analyze task complexity from prompt and token estimates
   *
   * @param taskType Task description or type keyword
   * @param inputTokens Estimated input tokens
   * @returns Task complexity level
   */
  private analyzeTaskComplexity(taskType: string, inputTokens: number): TaskLevel {
    const lowerType = taskType.toLowerCase();

    // Keyword-based classification
    const simpleKeywords = [
      "classify",
      "summarize",
      "extract",
      "qa",
      "Q&A",
      "translate",
      "format",
    ];
    const mediumKeywords = [
      "generate",
      "analyze",
      "explain",
      "compare",
      "debug",
      "refactor",
    ];
    const complexKeywords = [
      "design",
      "architecture",
      "plan",
      "optimize",
      "research",
    ];
    const veryComplexKeywords = [
      "multi-step",
      "strategic",
      "novel",
      "breakthrough",
    ];

    // Check for exact keyword matches
    if (veryComplexKeywords.some((k) => lowerType.includes(k))) {
      return "veryComplex";
    }
    if (complexKeywords.some((k) => lowerType.includes(k))) {
      return "complex";
    }
    if (mediumKeywords.some((k) => lowerType.includes(k))) {
      return "medium";
    }
    if (simpleKeywords.some((k) => lowerType.includes(k))) {
      return "simple";
    }

    // Token-based heuristic
    if (inputTokens > 50000) return "complex";
    if (inputTokens > 10000) return "medium";
    if (inputTokens > 2000) return "simple";

    // Default: medium for unknown types with reasonable token count
    return "medium";
  }

  /**
   * Ensure selected model has required capabilities
   * Upgrade to a more capable model if needed
   *
   * @param selectedModel Current model selection
   * @param required Required capabilities
   * @returns Model with all required capabilities
   */
  private ensureCapabilities(
    selectedModel: keyof typeof MODEL_CONFIG,
    required: Partial<typeof MODEL_CONFIG["claude-haiku-4-5"]["capabilities"]>
  ): keyof typeof MODEL_CONFIG {
    const modelCaps = MODEL_CONFIG[selectedModel].capabilities;

    // Check if current model has all required capabilities
    const hasAllCapabilities = Object.entries(required).every(
      ([cap, needed]) => {
        if (!needed) return true; // Not required
        return modelCaps[cap as keyof typeof modelCaps];
      }
    );

    if (hasAllCapabilities) return selectedModel;

    // Upgrade to a more capable model
    // Priority: Opus 4.7 > Opus 4.6 > Sonnet 4.6 > Haiku 4.5
    const capabilityHierarchy: (keyof typeof MODEL_CONFIG)[] = [
      "claude-opus-4-7",
      "claude-opus-4-6",
      "claude-sonnet-4-6",
      "claude-haiku-4-5",
    ];

    for (const modelId of capabilityHierarchy) {
      const caps = MODEL_CONFIG[modelId].capabilities;
      const satisfies = Object.entries(required).every(
        ([cap, needed]) => {
          if (!needed) return true;
          return caps[cap as keyof typeof caps];
        }
      );
      if (satisfies) return modelId;
    }

    // Fallback to most capable
    return "claude-opus-4-7";
  }

  /**
   * Calculate estimated cost for a routing context
   *
   * @param modelId Model to calculate cost for
   * @param inputTokens Estimated input tokens
   * @param outputTokens Estimated output tokens
   * @returns Cost breakdown in USD
   */
  private calculateCost(
    modelId: keyof typeof MODEL_CONFIG,
    inputTokens: number,
    outputTokens: number
  ): RoutingDecision["costBreakdown"] {
    const config = MODEL_CONFIG[modelId];

    return {
      inputTokensCost: inputTokens * config.inputCost,
      outputTokensCost: outputTokens * config.outputCost,
    };
  }

  /**
   * Generate human-readable reasoning for model selection
   *
   * @param taskLevel Complexity level
   * @param modelId Selected model
   * @param isUrgent Whether request is time-sensitive
   * @returns Reasoning string
   */
  private generateReasoning(
    taskLevel: TaskLevel,
    modelId: keyof typeof MODEL_CONFIG,
    isUrgent: boolean
  ): string {
    const modelName = MODEL_CONFIG[modelId].displayName;
    const urgencyNote = isUrgent ? " (time-sensitive request)" : "";

    switch (taskLevel) {
      case "simple":
        return `Selected ${modelName} for simple classification/extraction task${urgencyNote}. Saves 86% vs Opus.`;
      case "medium":
        return `Selected ${modelName} for medium-complexity task${urgencyNote}. Balanced cost and capability.`;
      case "complex":
        return `Selected ${modelName} for complex reasoning task${urgencyNote}. Advanced reasoning required.`;
      case "veryComplex":
        return `Selected ${modelName} for very complex strategic task${urgencyNote}. Maximum capability needed.`;
    }
  }

  /**
   * Create a message request with the optimal routing
   *
   * @param context Routing context
   * @param messages Claude API messages
   * @param system System prompt
   * @returns Complete message creation parameters
   */
  async createOptimalRequest(
    context: RoutingContext,
    messages: Anthropic.MessageParam[],
    system?: string | Anthropic.TextBlockParam[]
  ): Promise<{
    routing: RoutingDecision;
    request: Anthropic.MessageCreateParamsNonStreaming;
  }> {
    const routing = await this.route(context);

    const request: Anthropic.MessageCreateParamsNonStreaming = {
      model: routing.modelId,
      max_tokens: Math.min(context.estimatedOutputTokens, 16000),
      messages,
      ...(system && { system }),
    };

    return { routing, request };
  }

  /**
   * Get available models
   *
   * @returns Array of model IDs
   */
  getAvailableModels(): Array<keyof typeof MODEL_CONFIG> {
    return Object.keys(MODEL_CONFIG) as Array<keyof typeof MODEL_CONFIG>;
  }

  /**
   * Get model details
   *
   * @param modelId Model ID
   * @returns Model configuration or null
   */
  getModelConfig(modelId: keyof typeof MODEL_CONFIG) {
    return MODEL_CONFIG[modelId] || null;
  }
}

export default ClaudeModelRouter;
