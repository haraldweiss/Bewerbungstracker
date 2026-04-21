/**
 * Task Complexity Analysis Module
 * Analyzes prompts to determine optimal model selection
 */

/**
 * Keywords that influence task complexity scoring
 */
const COMPLEXITY_KEYWORDS = {
  simple: [
    "classify",
    "extract",
    "summarize",
    "format",
    "translate",
    "list",
    "count",
    "match",
    "validate",
    "qa",
    "question",
  ],
  medium: [
    "generate",
    "analyze",
    "explain",
    "compare",
    "contrast",
    "describe",
    "debug",
    "refactor",
    "improve",
    "suggest",
    "recommend",
  ],
  complex: [
    "design",
    "architect",
    "plan",
    "optimize",
    "research",
    "investigate",
    "strategy",
    "implement",
    "solve",
    "complex",
    "algorithm",
  ],
  veryComplex: [
    "multi-step",
    "strategic",
    "novel",
    "breakthrough",
    "comprehensive",
    "enterprise",
    "system design",
    "advanced",
  ],
};

/**
 * Task complexity score details
 */
export interface ComplexityScore {
  /** Overall complexity level */
  level: "simple" | "medium" | "complex" | "veryComplex";
  /** Score from 0-100 */
  score: number;
  /** Contributing factors */
  factors: {
    keywordScore: number;
    lengthScore: number;
    structureScore: number;
  };
  /** Breakdown of analysis */
  reasoning: string;
}

/**
 * Analyze task complexity from a prompt
 *
 * @param prompt Task description or prompt
 * @param contextLength Optional context length to influence scoring
 * @returns Complexity analysis with score and level
 */
export function analyzeTaskComplexity(
  prompt: string,
  contextLength: number = 0
): ComplexityScore {
  if (!prompt || prompt.trim().length === 0) {
    return {
      level: "simple",
      score: 10,
      factors: { keywordScore: 0, lengthScore: 0, structureScore: 0 },
      reasoning: "Empty or very short prompt - treating as simple task",
    };
  }

  const lowerPrompt = prompt.toLowerCase();

  // Keyword scoring
  let keywordScore = 0;
  let matchedLevel: keyof typeof COMPLEXITY_KEYWORDS | null = null;

  for (const [level, keywords] of Object.entries(COMPLEXITY_KEYWORDS)) {
    const matchCount = keywords.filter((kw) => lowerPrompt.includes(kw)).length;
    const levelScore = matchCount * (level === "veryComplex" ? 25 : level === "complex" ? 20 : level === "medium" ? 10 : 5);

    if (levelScore > keywordScore) {
      keywordScore = levelScore;
      matchedLevel = level as keyof typeof COMPLEXITY_KEYWORDS;
    }
  }

  // Length scoring (longer prompts = more context = higher complexity)
  const lengthScore = Math.min(30, Math.floor(prompt.length / 100));

  // Structure scoring (check for structured elements like lists, questions, steps)
  const hasLists = /^[\s]*[-•*]\s+/m.test(prompt);
  const hasNumberedSteps = /^[\s]*\d+[\.\)]\s+/m.test(prompt);
  const hasQuestions = (prompt.match(/\?/g) || []).length;
  const hasCodeBlocks = /```|`[^`]+`/g.test(prompt);

  let structureScore = 0;
  if (hasLists) structureScore += 5;
  if (hasNumberedSteps) structureScore += 5;
  if (hasQuestions > 3) structureScore += 10;
  if (hasCodeBlocks) structureScore += 10;
  if (contextLength > 10000) structureScore += 10;

  structureScore = Math.min(30, structureScore);

  // Context length influence
  let contextScore = 0;
  if (contextLength > 50000) contextScore = 20;
  else if (contextLength > 10000) contextScore = 15;
  else if (contextLength > 2000) contextScore = 10;

  // Total score
  const totalScore = Math.min(100, keywordScore + lengthScore + structureScore + contextScore);

  // Determine level based on score
  let level: "simple" | "medium" | "complex" | "veryComplex";
  if (totalScore >= 75) {
    level = "veryComplex";
  } else if (totalScore >= 50) {
    level = "complex";
  } else if (totalScore >= 25) {
    level = "medium";
  } else {
    level = "simple";
  }

  const reasoning = buildReasoningString(
    level,
    matchedLevel,
    { keywordScore, lengthScore, structureScore },
    { hasLists, hasNumberedSteps, hasQuestions, hasCodeBlocks }
  );

  return {
    level,
    score: totalScore,
    factors: { keywordScore, lengthScore, structureScore },
    reasoning,
  };
}

/**
 * Detect required capabilities from prompt
 *
 * @param prompt Task description
 * @returns Required capabilities
 */
export function detectRequiredCapabilities(prompt: string): {
  vision: boolean;
  thinking: boolean;
  toolUse: boolean;
} {
  const lowerPrompt = prompt.toLowerCase();

  const visionKeywords = ["image", "vision", "visual", "picture", "screenshot", "diagram", "photo"];
  const thinkingKeywords = ["step by step", "reasoning", "logic", "analyze", "deep"];
  const toolKeywords = ["api", "call", "execute", "run", "integration"];

  return {
    vision: visionKeywords.some((kw) => lowerPrompt.includes(kw)),
    thinking: thinkingKeywords.some((kw) => lowerPrompt.includes(kw)),
    toolUse: toolKeywords.some((kw) => lowerPrompt.includes(kw)),
  };
}

/**
 * Build human-readable reasoning string
 */
function buildReasoningString(
  level: string,
  matchedLevel: keyof typeof COMPLEXITY_KEYWORDS | null,
  factors: { keywordScore: number; lengthScore: number; structureScore: number },
  structure: {
    hasLists: boolean;
    hasNumberedSteps: boolean;
    hasQuestions: boolean;
    hasCodeBlocks: boolean;
  }
): string {
  const parts: string[] = [];

  if (matchedLevel) {
    parts.push(`Detected ${matchedLevel} keywords (score: ${factors.keywordScore})`);
  }

  if (factors.lengthScore > 10) {
    parts.push(`Extended prompt length (score: ${factors.lengthScore})`);
  }

  const structureElements = [];
  if (structure.hasLists) structureElements.push("lists");
  if (structure.hasNumberedSteps) structureElements.push("numbered steps");
  if (structure.hasQuestions > 0) structureElements.push("multiple questions");
  if (structure.hasCodeBlocks) structureElements.push("code blocks");

  if (structureElements.length > 0) {
    parts.push(`Structured elements: ${structureElements.join(", ")}`);
  }

  return `Complexity: ${level}. ${parts.join("; ") || "Standard prompt analysis"}`;
}

/**
 * Estimate output token count based on task type
 * (Rule of thumb estimates)
 *
 * @param taskType Task type or description
 * @param inputTokens Input token count
 * @returns Estimated output tokens
 */
export function estimateOutputTokens(taskType: string, inputTokens: number): number {
  const lowerType = taskType.toLowerCase();

  // Base ratio: output is typically 20-50% of input
  let ratio = 0.3;

  // Adjust based on task type
  if (lowerType.includes("summarize")) ratio = 0.15; // Summary is shorter
  if (lowerType.includes("extract")) ratio = 0.2;
  if (lowerType.includes("generate")) ratio = 0.8; // Generation creates new content
  if (lowerType.includes("analyze")) ratio = 0.6;
  if (lowerType.includes("design")) ratio = 0.7; // Design docs are longer
  if (lowerType.includes("code")) ratio = 0.9; // Code generation

  const estimated = Math.ceil(inputTokens * ratio);

  // Reasonable bounds
  return Math.max(256, Math.min(estimated, 64000));
}
