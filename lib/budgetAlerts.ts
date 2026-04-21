/**
 * Budget Alerts System
 * Monitors spending and sends webhook notifications for budget thresholds
 * Supports multiple notification channels and custom triggers
 */

/**
 * Alert trigger types
 */
export type AlertTrigger = 'threshold' | 'percentage' | 'daily_limit' | 'exceeded';

/**
 * Notification channel types
 */
export type NotificationChannel = 'webhook' | 'email' | 'slack' | 'console';

/**
 * Alert rule configuration
 */
export interface AlertRule {
  id: string;
  projectId: string;
  triggerType: AlertTrigger;
  threshold?: number; // USD amount
  percentageThreshold?: number; // 0-100
  dailyLimit?: number; // USD
  channels: NotificationChannel[];
  webhookUrl?: string;
  slackWebhook?: string;
  emailTo?: string;
  enabled: boolean;
  createdAt: Date;
  lastTriggeredAt?: Date;
}

/**
 * Alert event
 */
export interface AlertEvent {
  id: string;
  ruleId: string;
  projectId: string;
  triggerType: AlertTrigger;
  currentSpend: number;
  threshold: number;
  percentageUsed: number;
  timestamp: Date;
  message: string;
  sent: boolean;
  sentChannels: NotificationChannel[];
}

/**
 * Budget Alert Manager
 */
export class BudgetAlertManager {
  private rules: Map<string, AlertRule> = new Map();
  private events: AlertEvent[] = [];
  private checkInterval: NodeJS.Timer | null = null;

  /**
   * Create a new alert rule
   */
  createRule(
    projectId: string,
    triggerType: AlertTrigger,
    channels: NotificationChannel[],
    options?: {
      threshold?: number;
      percentageThreshold?: number;
      dailyLimit?: number;
      webhookUrl?: string;
      slackWebhook?: string;
      emailTo?: string;
    }
  ): AlertRule {
    const rule: AlertRule = {
      id: `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      projectId,
      triggerType,
      threshold: options?.threshold,
      percentageThreshold: options?.percentageThreshold,
      dailyLimit: options?.dailyLimit,
      channels,
      webhookUrl: options?.webhookUrl,
      slackWebhook: options?.slackWebhook,
      emailTo: options?.emailTo,
      enabled: true,
      createdAt: new Date(),
    };

    this.rules.set(rule.id, rule);
    return rule;
  }

  /**
   * Get all rules for a project
   */
  getRulesForProject(projectId: string): AlertRule[] {
    return Array.from(this.rules.values()).filter((r) => r.projectId === projectId);
  }

  /**
   * Enable/disable a rule
   */
  setRuleEnabled(ruleId: string, enabled: boolean): boolean {
    const rule = this.rules.get(ruleId);
    if (!rule) return false;

    rule.enabled = enabled;
    return true;
  }

  /**
   * Delete a rule
   */
  deleteRule(ruleId: string): boolean {
    return this.rules.delete(ruleId);
  }

  /**
   * Check if alert should trigger
   */
  async checkAlert(
    projectId: string,
    currentSpend: number,
    monthlyBudget: number,
    dailySpend: number = 0
  ): Promise<AlertEvent[]> {
    const triggeredEvents: AlertEvent[] = [];
    const rules = this.getRulesForProject(projectId);

    for (const rule of rules) {
      if (!rule.enabled) continue;

      let shouldTrigger = false;
      let threshold = 0;
      let percentageUsed = (currentSpend / monthlyBudget) * 100;

      switch (rule.triggerType) {
        case 'threshold':
          if (rule.threshold && currentSpend >= rule.threshold) {
            shouldTrigger = true;
            threshold = rule.threshold;
          }
          break;

        case 'percentage':
          if (rule.percentageThreshold && percentageUsed >= rule.percentageThreshold) {
            shouldTrigger = true;
            threshold = (rule.percentageThreshold / 100) * monthlyBudget;
          }
          break;

        case 'daily_limit':
          if (rule.dailyLimit && dailySpend >= rule.dailyLimit) {
            shouldTrigger = true;
            threshold = rule.dailyLimit;
          }
          break;

        case 'exceeded':
          if (currentSpend > monthlyBudget) {
            shouldTrigger = true;
            threshold = monthlyBudget;
          }
          break;
      }

      if (shouldTrigger) {
        const event = await this.createAlertEvent(
          rule,
          currentSpend,
          threshold,
          percentageUsed,
          monthlyBudget
        );

        triggeredEvents.push(event);

        // Send notifications
        await this.sendNotifications(event, rule);

        // Update last triggered time
        rule.lastTriggeredAt = event.timestamp;
      }
    }

    return triggeredEvents;
  }

  /**
   * Create an alert event
   */
  private async createAlertEvent(
    rule: AlertRule,
    currentSpend: number,
    threshold: number,
    percentageUsed: number,
    monthlyBudget: number
  ): Promise<AlertEvent> {
    const messages: Record<AlertTrigger, string> = {
      threshold: `Budget threshold of $${threshold.toFixed(2)} reached. Current spend: $${currentSpend.toFixed(2)}`,
      percentage: `Budget ${Math.round(percentageUsed)}% used ($${currentSpend.toFixed(2)} of $${monthlyBudget.toFixed(2)})`,
      daily_limit: `Daily spending limit of $${threshold.toFixed(2)} exceeded. Today: $${currentSpend.toFixed(2)}`,
      exceeded: `⚠️ BUDGET EXCEEDED - Spent $${currentSpend.toFixed(2)} of $${monthlyBudget.toFixed(2)} budget`,
    };

    const event: AlertEvent = {
      id: `event-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      ruleId: rule.id,
      projectId: rule.projectId,
      triggerType: rule.triggerType,
      currentSpend,
      threshold,
      percentageUsed,
      timestamp: new Date(),
      message: messages[rule.triggerType],
      sent: false,
      sentChannels: [],
    };

    this.events.push(event);
    return event;
  }

  /**
   * Send notifications through configured channels
   */
  private async sendNotifications(event: AlertEvent, rule: AlertRule): Promise<void> {
    const promises: Promise<void>[] = [];

    for (const channel of rule.channels) {
      switch (channel) {
        case 'webhook':
          if (rule.webhookUrl) {
            promises.push(this.sendWebhookNotification(event, rule.webhookUrl));
          }
          break;

        case 'slack':
          if (rule.slackWebhook) {
            promises.push(this.sendSlackNotification(event, rule.slackWebhook));
          }
          break;

        case 'email':
          if (rule.emailTo) {
            promises.push(this.sendEmailNotification(event, rule.emailTo));
          }
          break;

        case 'console':
          promises.push(this.sendConsoleNotification(event));
          break;
      }
    }

    const results = await Promise.allSettled(promises);

    // Track which channels succeeded
    for (let i = 0; i < results.length; i++) {
      if (results[i].status === 'fulfilled') {
        event.sentChannels.push(rule.channels[i]);
      }
    }

    event.sent = event.sentChannels.length > 0;
  }

  /**
   * Send webhook notification
   */
  private async sendWebhookNotification(event: AlertEvent, webhookUrl: string): Promise<void> {
    const payload = {
      alert: event,
      timestamp: new Date().toISOString(),
    };

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Webhook failed: ${response.statusText}`);
    }
  }

  /**
   * Send Slack notification
   */
  private async sendSlackNotification(event: AlertEvent, slackWebhook: string): Promise<void> {
    const color =
      event.triggerType === 'exceeded'
        ? '#ff0000'
        : event.percentageUsed > 80
          ? '#ff9800'
          : '#4CAF50';

    const payload = {
      attachments: [
        {
          color,
          title: `💰 Claude API Budget Alert - ${event.projectId}`,
          text: event.message,
          fields: [
            {
              title: 'Current Spend',
              value: `$${event.currentSpend.toFixed(4)}`,
              short: true,
            },
            {
              title: 'Threshold',
              value: `$${event.threshold.toFixed(4)}`,
              short: true,
            },
            {
              title: 'Alert Type',
              value: event.triggerType,
              short: true,
            },
            {
              title: 'Time',
              value: event.timestamp.toISOString(),
              short: true,
            },
          ],
        },
      ],
    };

    const response = await fetch(slackWebhook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Slack notification failed: ${response.statusText}`);
    }
  }

  /**
   * Send email notification
   */
  private async sendEmailNotification(event: AlertEvent, emailTo: string): Promise<void> {
    // In production, use a service like SendGrid, AWS SES, or Nodemailer
    console.log(`📧 Email notification would be sent to ${emailTo}`);
    console.log(`Subject: Claude API Budget Alert - ${event.projectId}`);
    console.log(`Message: ${event.message}`);

    // Simulated implementation - replace with actual email service
    // Example with SendGrid:
    // const sgMail = require('@sendgrid/mail');
    // sgMail.setApiKey(process.env.SENDGRID_API_KEY);
    // await sgMail.send({
    //   to: emailTo,
    //   from: 'alerts@yourcompany.com',
    //   subject: `Claude API Budget Alert - ${event.projectId}`,
    //   html: this.formatEmailHtml(event),
    // });
  }

  /**
   * Send console notification
   */
  private async sendConsoleNotification(event: AlertEvent): Promise<void> {
    const emoji =
      event.triggerType === 'exceeded'
        ? '🚨'
        : event.percentageUsed > 80
          ? '⚠️'
          : '💡';

    console.log(`\n${emoji} [Budget Alert] ${event.message}`);
    console.log(`   Project: ${event.projectId}`);
    console.log(`   Timestamp: ${event.timestamp.toISOString()}\n`);
  }

  /**
   * Format email HTML (example)
   */
  private formatEmailHtml(event: AlertEvent): string {
    return `
      <h2>Claude API Budget Alert</h2>
      <p><strong>${event.message}</strong></p>
      <table style="border-collapse: collapse; width: 100%;">
        <tr>
          <td style="padding: 8px; border: 1px solid #ddd;">Project</td>
          <td style="padding: 8px; border: 1px solid #ddd;">${event.projectId}</td>
        </tr>
        <tr>
          <td style="padding: 8px; border: 1px solid #ddd;">Alert Type</td>
          <td style="padding: 8px; border: 1px solid #ddd;">${event.triggerType}</td>
        </tr>
        <tr>
          <td style="padding: 8px; border: 1px solid #ddd;">Current Spend</td>
          <td style="padding: 8px; border: 1px solid #ddd;">$${event.currentSpend.toFixed(4)}</td>
        </tr>
        <tr>
          <td style="padding: 8px; border: 1px solid #ddd;">Percentage Used</td>
          <td style="padding: 8px; border: 1px solid #ddd;">${event.percentageUsed.toFixed(1)}%</td>
        </tr>
      </table>
      <p>Timestamp: ${event.timestamp.toISOString()}</p>
    `;
  }

  /**
   * Get alert events
   */
  getAlertEvents(
    filters?: {
      projectId?: string;
      ruleId?: string;
      since?: Date;
    }
  ): AlertEvent[] {
    let events = this.events;

    if (filters?.projectId) {
      events = events.filter((e) => e.projectId === filters.projectId);
    }
    if (filters?.ruleId) {
      events = events.filter((e) => e.ruleId === filters.ruleId);
    }
    if (filters?.since) {
      events = events.filter((e) => e.timestamp >= filters.since!);
    }

    return events;
  }

  /**
   * Get all rules
   */
  getAllRules(): AlertRule[] {
    return Array.from(this.rules.values());
  }

  /**
   * Start periodic checking (for background monitoring)
   */
  startMonitoring(
    checkFn: () => Promise<{ projectId: string; spend: number; budget: number; dailySpend?: number }[]>,
    intervalMs: number = 60000
  ): void {
    this.checkInterval = setInterval(async () => {
      try {
        const projects = await checkFn();
        for (const project of projects) {
          await this.checkAlert(
            project.projectId,
            project.spend,
            project.budget,
            project.dailySpend
          );
        }
      } catch (error) {
        console.error('Error during budget check:', error);
      }
    }, intervalMs);
  }

  /**
   * Stop periodic monitoring
   */
  stopMonitoring(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }
}

export default BudgetAlertManager;
