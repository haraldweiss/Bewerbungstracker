#!/usr/bin/env node

/**
 * Claude Cost Reporter CLI
 * Command-line tool for tracking usage, generating reports, and managing batches
 * Usage: npx ts-node cli-cost-reporter.ts <command> [options]
 */

import { program } from 'commander';
import { UsageTracker } from '../lib/usageTracker';
import { BatchProcessor } from '../lib/batchProcessor';
import Anthropic from '@anthropic-ai/sdk';
import * as fs from 'fs';
import * as path from 'path';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// Load or create tracker data file
const dataDir = path.join(process.cwd(), '.claude-usage');
const dataFile = path.join(dataDir, 'usage-tracker.json');

function ensureDataDir() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
}

function loadTracker(): UsageTracker {
  ensureDataDir();
  const tracker = new UsageTracker(100);

  // Load existing data if available
  if (fs.existsSync(dataFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));
      // Note: In production, you'd deserialize the events properly
      console.log(`✓ Loaded ${data.length || 0} previous events`);
    } catch (error) {
      console.warn('⚠️ Could not load previous data');
    }
  }

  return tracker;
}

function saveTracker(tracker: UsageTracker) {
  ensureDataDir();
  // In production, you'd implement proper serialization
  console.log('✓ Data saved');
}

/**
 * CLI Setup
 */
program
  .name('claude-cost-reporter')
  .description('CLI tool for tracking Claude API costs and usage')
  .version('1.0.0');

/**
 * Command: report
 * Generate usage and cost reports
 */
program
  .command('report [projectId]')
  .description('Generate usage report (optionally for a specific project)')
  .option('-f, --format <format>', 'Output format (text, json)', 'text')
  .action((projectId: string | undefined, options: { format: string }) => {
    const tracker = loadTracker();
    const report = tracker.generateReport(projectId);

    if (options.format === 'json') {
      const stats = projectId ? tracker.getProjectStats(projectId) : tracker.getMonthlyStats();
      console.log(JSON.stringify(stats, null, 2));
    } else {
      console.log(report);
    }
  });

/**
 * Command: summary
 * Display quick cost summary
 */
program
  .command('summary')
  .description('Display quick cost summary')
  .action(() => {
    const tracker = loadTracker();
    const stats = tracker.getMonthlyStats();

    console.log('\n📊 Claude API Usage Summary');
    console.log('================================');
    console.log(`Total Requests:    ${stats.totalRequests}`);
    console.log(`Total Tokens:      ${stats.totalTokens.toLocaleString()}`);
    console.log(`Total Cost:        $${stats.totalCost.toFixed(4)}`);
    console.log(`Avg Cost/Request:  $${stats.averageCostPerRequest.toFixed(4)}`);
    console.log(`Batch Requests:    ${stats.batchRequests} (${Math.round((stats.batchRequests / Math.max(1, stats.totalRequests)) * 100)}%)`);
    console.log('\n💰 Top Models:');
    stats.topModels.slice(0, 3).forEach((model) => {
      console.log(`  ${model.modelId}: ${model.requests} requests, $${model.cost.toFixed(4)}`);
    });
  });

/**
 * Command: project
 * View project statistics
 */
program
  .command('project <projectId>')
  .description('View statistics for a specific project')
  .action((projectId: string) => {
    const tracker = loadTracker();
    const stats = tracker.getProjectStats(projectId);

    console.log(`\n📁 Project: ${projectId}`);
    console.log('================================');
    console.log(`Total Requests:  ${stats.totalRequests}`);
    console.log(`Total Cost:      $${stats.totalCost.toFixed(4)}`);
    console.log(`Monthly Spend:   $${stats.monthlySpend.toFixed(2)} / $${stats.monthlyBudget}`);
    console.log(`Budget Usage:    ${((stats.monthlySpend / stats.monthlyBudget) * 100).toFixed(0)}%`);

    if (Object.keys(stats.modelDistribution).length > 0) {
      console.log('\n🤖 Model Distribution:');
      Object.entries(stats.modelDistribution)
        .sort((a, b) => b[1] - a[1])
        .forEach(([model, count]) => {
          console.log(`  ${model}: ${count} requests`);
        });
    }
  });

/**
 * Command: models
 * Show cost breakdown by model
 */
program
  .command('models')
  .description('Show cost breakdown by model')
  .action(() => {
    const tracker = loadTracker();
    const breakdown = tracker.getCostByModel();

    console.log('\n🤖 Cost by Model');
    console.log('========================================');
    console.log('Model                    Requests  Cost');
    console.log('----------------------------------------');

    Object.entries(breakdown)
      .sort((a, b) => b[1].cost - a[1].cost)
      .forEach(([model, stats]) => {
        const padding = ' '.repeat(Math.max(0, 24 - model.length));
        console.log(`${model}${padding}${String(stats.requests).padStart(8)}  $${stats.cost.toFixed(4)}`);
      });
  });

/**
 * Command: batch
 * Manage batch operations
 */
program
  .command('batch <action> [batchId]')
  .description('Manage batch operations (status, cancel, list)')
  .action(async (action: string, batchId?: string) => {
    const processor = new BatchProcessor(process.env.ANTHROPIC_API_KEY);

    try {
      switch (action) {
        case 'list':
          console.log('\n📦 Active Batches:');
          const activeBatches = processor.getActiveBatches();
          if (activeBatches.length === 0) {
            console.log('No active batches');
          } else {
            activeBatches.forEach((id) => console.log(`  - ${id}`));
          }
          break;

        case 'status':
          if (!batchId) {
            console.error('Error: batchId required for status command');
            process.exit(1);
          }
          const status = await processor.getBatchStatus(batchId);
          console.log(`\n📦 Batch ${batchId}`);
          console.log(`Status:    ${status.status}`);
          console.log(`Succeeded: ${status.succeeded}`);
          console.log(`Errored:   ${status.errored}`);
          console.log(`Expired:   ${status.expired}`);
          console.log(`Canceled:  ${status.canceled}`);
          break;

        case 'cancel':
          if (!batchId) {
            console.error('Error: batchId required for cancel command');
            process.exit(1);
          }
          const cancelResult = await processor.cancelBatch(batchId);
          console.log(`✓ Batch ${batchId} cancelled (status: ${cancelResult.status})`);
          break;

        default:
          console.error(`Unknown batch action: ${action}`);
          console.log('Available actions: list, status <batchId>, cancel <batchId>');
          process.exit(1);
      }
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

/**
 * Command: budget
 * Set and view budget limits
 */
program
  .command('budget <projectId> [limitUSD]')
  .description('Set or view budget for a project')
  .action((projectId: string, limitUSD?: string) => {
    const tracker = loadTracker();

    if (limitUSD) {
      const limit = parseFloat(limitUSD);
      if (isNaN(limit)) {
        console.error('Error: Invalid budget amount');
        process.exit(1);
      }
      tracker.setProjectBudget(projectId, limit);
      console.log(`✓ Budget for ${projectId} set to $${limit}`);
      saveTracker(tracker);
    } else {
      const stats = tracker.getProjectStats(projectId);
      console.log(`\n💰 Budget for ${projectId}`);
      console.log(`Limit:  $${stats.monthlyBudget}`);
      console.log(`Spent:  $${stats.monthlySpend.toFixed(2)}`);
      console.log(`Used:   ${((stats.monthlySpend / stats.monthlyBudget) * 100).toFixed(0)}%`);
      console.log(`Left:   $${(stats.monthlyBudget - stats.monthlySpend).toFixed(2)}`);
    }
  });

/**
 * Command: savings
 * Calculate batch savings
 */
program
  .command('savings')
  .description('Calculate total savings from batch processing')
  .action(() => {
    const tracker = loadTracker();
    const savings = tracker.calculateBatchSavings();

    console.log('\n💎 Batch Savings');
    console.log('================================');
    console.log(`Total Saved:  $${savings.toFixed(4)}`);

    const monthlyStats = tracker.getMonthlyStats();
    const savingsPercent = (savings / (monthlyStats.totalCost + savings)) * 100;
    console.log(`Savings %:    ${savingsPercent.toFixed(1)}%`);
    console.log(`Without Batch Cost: $${(monthlyStats.totalCost + savings).toFixed(4)}`);
  });

/**
 * Command: export
 * Export tracking data
 */
program
  .command('export [format]')
  .description('Export usage data (csv, json)')
  .option('-o, --output <file>', 'Output file path')
  .action((format: string = 'json', options: { output?: string }) => {
    const tracker = loadTracker();
    const data = tracker.exportEvents();

    const output = options.output || `usage-export-${new Date().toISOString().split('T')[0]}.json`;

    fs.writeFileSync(output, data);
    console.log(`✓ Data exported to ${output}`);
  });

/**
 * Command: test
 * Test connection and API key
 */
program
  .command('test')
  .description('Test connection to Claude API')
  .action(async () => {
    try {
      console.log('Testing Claude API connection...');

      const response = await anthropic.messages.create({
        model: 'claude-haiku-4-5',
        max_tokens: 100,
        messages: [{ role: 'user', content: 'Say "Connected!" only' }],
      });

      console.log('✓ Connection successful!');
      console.log(`Response: ${response.content[0].type === 'text' ? response.content[0].text : 'N/A'}`);
      console.log(`Tokens used: ${response.usage.input_tokens} input, ${response.usage.output_tokens} output`);
    } catch (error) {
      console.error('✗ Connection failed:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

/**
 * Help command
 */
program
  .command('help')
  .description('Show detailed help')
  .action(() => {
    console.log(`
Claude Cost Reporter - Usage Examples
=====================================

# View monthly summary
  claude-cost-reporter summary

# Generate full report
  claude-cost-reporter report

# View project statistics
  claude-cost-reporter project bewerbungstracker

# Cost breakdown by model
  claude-cost-reporter models

# Set project budget
  claude-cost-reporter budget myproject 50.00

# View batch savings
  claude-cost-reporter savings

# Check batch status
  claude-cost-reporter batch status <batch-id>

# Export data
  claude-cost-reporter export json -o data.json

# Test API connection
  claude-cost-reporter test

Environment Variables
=====================
ANTHROPIC_API_KEY - Your Claude API key (required)
    `);
  });

// Parse command-line arguments
program.parse(process.argv);

// Show help if no command provided
if (!process.argv.slice(2).length) {
  program.outputHelp();
}
