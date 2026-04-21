/**
 * Claude-KI-Usage-Tracker Backend Service
 * Express.js integration for tracking Claude API usage across projects
 * Provides REST API endpoints for usage recording, analytics, and reporting
 */

import express, { Express, Request, Response } from 'express';
import { UsageTracker, UsageEvent } from '../lib/usageTracker';
import { ClaudeModelRouter } from '../lib/claudeModelRouter';
import Anthropic from '@anthropic-ai/sdk';

/**
 * Express middleware and routes for usage tracking
 */
export class UsageTrackerService {
  private app: Express;
  private tracker: UsageTracker;
  private router: ClaudeModelRouter;
  private anthropic: Anthropic;

  constructor(port: number = 3000, apiKey: string = process.env.ANTHROPIC_API_KEY || '') {
    this.app = express();
    this.tracker = new UsageTracker(100); // $100 default budget
    this.router = new ClaudeModelRouter(apiKey);
    this.anthropic = new Anthropic({ apiKey });

    this.setupMiddleware();
    this.setupRoutes();
  }

  /**
   * Setup Express middleware
   */
  private setupMiddleware(): void {
    this.app.use(express.json());

    // CORS
    this.app.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
      res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
      next();
    });

    // Request logging
    this.app.use((req, res, next) => {
      console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
      next();
    });
  }

  /**
   * Setup API routes
   */
  private setupRoutes(): void {
    /**
     * POST /api/track-usage
     * Record a usage event for an API call
     */
    this.app.post('/api/track-usage', (req: Request, res: Response) => {
      try {
        const {
          projectId,
          taskType,
          modelId,
          inputTokens,
          outputTokens,
          isBatch,
          durationMs,
          userId,
          metadata,
        } = req.body;

        if (!projectId || !taskType || !modelId) {
          return res.status(400).json({ error: 'Missing required fields' });
        }

        const event = this.tracker.recordUsage(
          projectId,
          taskType,
          modelId,
          inputTokens,
          outputTokens,
          isBatch,
          durationMs,
          userId,
          metadata
        );

        res.json({ success: true, event });
      } catch (error) {
        console.error('Error recording usage:', error);
        res.status(500).json({ error: 'Failed to record usage' });
      }
    });

    /**
     * GET /api/usage/monthly
     * Get monthly usage statistics
     */
    this.app.get('/api/usage/monthly', (req: Request, res: Response) => {
      try {
        const stats = this.tracker.getMonthlyStats();
        res.json(stats);
      } catch (error) {
        console.error('Error fetching monthly stats:', error);
        res.status(500).json({ error: 'Failed to fetch monthly stats' });
      }
    });

    /**
     * GET /api/usage/project/:projectId
     * Get project-specific statistics
     */
    this.app.get('/api/usage/project/:projectId', (req: Request, res: Response) => {
      try {
        const { projectId } = req.params;
        const stats = this.tracker.getProjectStats(projectId);
        res.json(stats);
      } catch (error) {
        console.error('Error fetching project stats:', error);
        res.status(500).json({ error: 'Failed to fetch project stats' });
      }
    });

    /**
     * GET /api/usage/events
     * Get usage events with optional filters
     */
    this.app.get('/api/usage/events', (req: Request, res: Response) => {
      try {
        const { projectId, modelId, startDate, endDate } = req.query;

        const filters: any = {};
        if (projectId) filters.projectId = projectId;
        if (modelId) filters.modelId = modelId;
        if (startDate) filters.startDate = new Date(startDate as string);
        if (endDate) filters.endDate = new Date(endDate as string);

        const events = this.tracker.getEvents(filters);
        res.json(events);
      } catch (error) {
        console.error('Error fetching events:', error);
        res.status(500).json({ error: 'Failed to fetch events' });
      }
    });

    /**
     * GET /api/usage/report
     * Get comprehensive usage report
     */
    this.app.get('/api/usage/report', (req: Request, res: Response) => {
      try {
        const { projectId } = req.query;
        const report = this.tracker.generateReport(projectId as string);

        res.set('Content-Type', 'text/plain');
        res.send(report);
      } catch (error) {
        console.error('Error generating report:', error);
        res.status(500).json({ error: 'Failed to generate report' });
      }
    });

    /**
     * GET /api/usage/cost-by-model
     * Get cost breakdown by model
     */
    this.app.get('/api/usage/cost-by-model', (req: Request, res: Response) => {
      try {
        const breakdown = this.tracker.getCostByModel();
        res.json(breakdown);
      } catch (error) {
        console.error('Error fetching cost breakdown:', error);
        res.status(500).json({ error: 'Failed to fetch cost breakdown' });
      }
    });

    /**
     * GET /api/usage/batch-savings
     * Get total savings from batch processing
     */
    this.app.get('/api/usage/batch-savings', (req: Request, res: Response) => {
      try {
        const savings = this.tracker.calculateBatchSavings();
        res.json({ savingsUSD: savings });
      } catch (error) {
        console.error('Error calculating batch savings:', error);
        res.status(500).json({ error: 'Failed to calculate batch savings' });
      }
    });

    /**
     * POST /api/route-and-track
     * Integrated endpoint: route a request + track usage
     * Example for Claude API call with automatic routing
     */
    this.app.post('/api/route-and-track', async (req: Request, res: Response) => {
      try {
        const {
          projectId,
          prompt,
          isUrgent = false,
          userId,
          estimatedInputTokens,
          estimatedOutputTokens,
        } = req.body;

        if (!projectId || !prompt) {
          return res.status(400).json({ error: 'Missing required fields' });
        }

        // Route the request
        const decision = await this.router.route({
          taskType: prompt.substring(0, 100), // Use first 100 chars as task type
          estimatedInputTokens: estimatedInputTokens || 500,
          estimatedOutputTokens: estimatedOutputTokens || 100,
          isUrgent,
        });

        // Track the routing decision
        const event = this.tracker.recordUsage(
          projectId,
          decision.taskLevel,
          decision.modelId,
          estimatedInputTokens || 500,
          estimatedOutputTokens || 100,
          decision.batchRecommended,
          0,
          userId,
          {
            reasoning: decision.reasoning,
            estimatedCost: decision.estimatedCost,
            batchSavings: decision.batchSavings,
          }
        );

        res.json({
          decision,
          tracked: event,
          recommendation: decision.batchRecommended
            ? 'Use Batch API for 50% savings'
            : 'Use standard API for immediate response',
        });
      } catch (error) {
        console.error('Error routing and tracking:', error);
        res.status(500).json({ error: 'Failed to route and track request' });
      }
    });

    /**
     * POST /api/budget/set-project
     * Set monthly budget for a project
     */
    this.app.post('/api/budget/set-project', (req: Request, res: Response) => {
      try {
        const { projectId, monthlyBudgetUSD } = req.body;

        if (!projectId || monthlyBudgetUSD === undefined) {
          return res.status(400).json({ error: 'Missing required fields' });
        }

        this.tracker.setProjectBudget(projectId, monthlyBudgetUSD);

        res.json({
          success: true,
          message: `Budget set for ${projectId}: $${monthlyBudgetUSD}`,
        });
      } catch (error) {
        console.error('Error setting budget:', error);
        res.status(500).json({ error: 'Failed to set budget' });
      }
    });

    /**
     * GET /api/health
     * Health check endpoint
     */
    this.app.get('/api/health', (req: Request, res: Response) => {
      res.json({ status: 'ok', timestamp: new Date().toISOString() });
    });

    /**
     * POST /api/test-claude-call
     * Test Claude API call with automatic routing
     * For development/testing purposes
     */
    this.app.post('/api/test-claude-call', async (req: Request, res: Response) => {
      try {
        const { projectId, prompt, modelId } = req.body;

        if (!projectId || !prompt) {
          return res.status(400).json({ error: 'Missing required fields' });
        }

        const selectedModel = modelId || 'claude-opus-4-7';
        const startTime = Date.now();

        const message = await this.anthropic.messages.create({
          model: selectedModel,
          max_tokens: 1024,
          messages: [{ role: 'user', content: prompt }],
        });

        const durationMs = Date.now() - startTime;
        const inputTokens = message.usage.input_tokens;
        const outputTokens = message.usage.output_tokens;

        // Record the usage
        const event = this.tracker.recordUsage(
          projectId,
          'test-call',
          selectedModel,
          inputTokens,
          outputTokens,
          false,
          durationMs
        );

        res.json({
          success: true,
          message: message.content[0].type === 'text' ? message.content[0].text : null,
          usage: {
            inputTokens,
            outputTokens,
            totalTokens: inputTokens + outputTokens,
          },
          tracked: event,
        });
      } catch (error) {
        console.error('Error testing Claude call:', error);
        res.status(500).json({ error: 'Failed to test Claude call' });
      }
    });
  }

  /**
   * Start the server
   */
  public start(port: number = 3000): void {
    this.app.listen(port, () => {
      console.log(`✓ Usage Tracker Service running on http://localhost:${port}`);
      console.log(`  API Documentation:`);
      console.log(`  - POST   /api/track-usage         - Record usage event`);
      console.log(`  - GET    /api/usage/monthly       - Monthly statistics`);
      console.log(`  - GET    /api/usage/project/:id   - Project statistics`);
      console.log(`  - GET    /api/usage/events        - List events (filtered)`);
      console.log(`  - GET    /api/usage/report        - Generate report`);
      console.log(`  - GET    /api/usage/cost-by-model - Cost breakdown`);
      console.log(`  - GET    /api/usage/batch-savings - Batch savings`);
      console.log(`  - POST   /api/route-and-track     - Route + track request`);
      console.log(`  - POST   /api/budget/set-project  - Set project budget`);
      console.log(`  - POST   /api/test-claude-call    - Test API call`);
      console.log(`  - GET    /api/health              - Health check`);
    });
  }

  /**
   * Get the Express app (for testing)
   */
  public getApp(): Express {
    return this.app;
  }

  /**
   * Get the tracker instance
   */
  public getTracker(): UsageTracker {
    return this.tracker;
  }
}

/**
 * Start the service if this file is run directly
 */
if (require.main === module) {
  const service = new UsageTrackerService(
    parseInt(process.env.PORT || '3000'),
    process.env.ANTHROPIC_API_KEY
  );
  service.start();
}

export default UsageTrackerService;
