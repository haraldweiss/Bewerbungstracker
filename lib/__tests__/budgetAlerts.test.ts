/**
 * Unit Tests for Budget Alerts System
 * Tests alert rules, triggers, and notifications
 */

import { BudgetAlertManager, AlertRule, AlertEvent } from '../budgetAlerts';

// Mock fetch for webhook tests
global.fetch = jest.fn();

describe('BudgetAlertManager', () => {
  let manager: BudgetAlertManager;

  beforeEach(() => {
    manager = new BudgetAlertManager();
    jest.clearAllMocks();
  });

  describe('createRule()', () => {
    test('should create a threshold-based alert rule', () => {
      const rule = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50.0,
      });

      expect(rule.projectId).toBe('project1');
      expect(rule.triggerType).toBe('threshold');
      expect(rule.threshold).toBe(50.0);
      expect(rule.enabled).toBe(true);
    });

    test('should create a percentage-based alert rule', () => {
      const rule = manager.createRule('project1', 'percentage', ['webhook'], {
        percentageThreshold: 80,
        webhookUrl: 'https://example.com/alert',
      });

      expect(rule.triggerType).toBe('percentage');
      expect(rule.percentageThreshold).toBe(80);
      expect(rule.webhookUrl).toBe('https://example.com/alert');
    });

    test('should create a daily limit rule', () => {
      const rule = manager.createRule('project1', 'daily_limit', ['slack'], {
        dailyLimit: 10.0,
        slackWebhook: 'https://hooks.slack.com/services/...',
      });

      expect(rule.triggerType).toBe('daily_limit');
      expect(rule.dailyLimit).toBe(10.0);
    });

    test('should create an exceeded budget rule', () => {
      const rule = manager.createRule('project1', 'exceeded', ['console', 'email'], {
        emailTo: 'admin@example.com',
      });

      expect(rule.triggerType).toBe('exceeded');
      expect(rule.channels).toContain('email');
    });

    test('should assign unique IDs to rules', () => {
      const rule1 = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });
      const rule2 = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });

      expect(rule1.id).not.toBe(rule2.id);
    });
  });

  describe('getRulesForProject()', () => {
    beforeEach(() => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50 });
      manager.createRule('project1', 'percentage', ['console'], {
        percentageThreshold: 80,
      });
      manager.createRule('project2', 'threshold', ['console'], { threshold: 30 });
    });

    test('should return rules for specific project', () => {
      const rules = manager.getRulesForProject('project1');

      expect(rules).toHaveLength(2);
      expect(rules.every((r) => r.projectId === 'project1')).toBe(true);
    });

    test('should return empty array for non-existent project', () => {
      const rules = manager.getRulesForProject('project-nonexistent');

      expect(rules).toHaveLength(0);
    });
  });

  describe('setRuleEnabled()', () => {
    test('should enable/disable a rule', () => {
      const rule = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });

      manager.setRuleEnabled(rule.id, false);
      const rules = manager.getRulesForProject('project1');

      expect(rules[0].enabled).toBe(false);

      manager.setRuleEnabled(rule.id, true);
      expect(rules[0].enabled).toBe(true);
    });

    test('should return false for non-existent rule', () => {
      const result = manager.setRuleEnabled('nonexistent', false);

      expect(result).toBe(false);
    });
  });

  describe('deleteRule()', () => {
    test('should delete a rule', () => {
      const rule = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });

      const deleted = manager.deleteRule(rule.id);
      expect(deleted).toBe(true);

      const rules = manager.getRulesForProject('project1');
      expect(rules).toHaveLength(0);
    });

    test('should return false for non-existent rule', () => {
      const deleted = manager.deleteRule('nonexistent');

      expect(deleted).toBe(false);
    });
  });

  describe('checkAlert() - Threshold Trigger', () => {
    test('should trigger when spending reaches threshold', async () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50.0 });

      const events = await manager.checkAlert('project1', 50.0, 100.0);

      expect(events).toHaveLength(1);
      expect(events[0].triggerType).toBe('threshold');
    });

    test('should not trigger when below threshold', async () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50.0 });

      const events = await manager.checkAlert('project1', 25.0, 100.0);

      expect(events).toHaveLength(0);
    });

    test('should trigger when spending exceeds threshold', async () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50.0 });

      const events = await manager.checkAlert('project1', 75.0, 100.0);

      expect(events).toHaveLength(1);
    });
  });

  describe('checkAlert() - Percentage Trigger', () => {
    test('should trigger at percentage threshold', async () => {
      manager.createRule('project1', 'percentage', ['console'], {
        percentageThreshold: 80,
      });

      const events = await manager.checkAlert('project1', 80.0, 100.0);

      expect(events).toHaveLength(1);
      expect(events[0].percentageUsed).toBe(80);
    });

    test('should not trigger below percentage', async () => {
      manager.createRule('project1', 'percentage', ['console'], {
        percentageThreshold: 80,
      });

      const events = await manager.checkAlert('project1', 50.0, 100.0);

      expect(events).toHaveLength(0);
    });

    test('should trigger when exceeding percentage', async () => {
      manager.createRule('project1', 'percentage', ['console'], {
        percentageThreshold: 50,
      });

      const events = await manager.checkAlert('project1', 75.0, 100.0);

      expect(events).toHaveLength(1);
      expect(events[0].percentageUsed).toBe(75);
    });
  });

  describe('checkAlert() - Daily Limit Trigger', () => {
    test('should trigger when daily spend reaches limit', async () => {
      manager.createRule('project1', 'daily_limit', ['console'], { dailyLimit: 10.0 });

      const events = await manager.checkAlert('project1', 50.0, 100.0, 10.0);

      expect(events).toHaveLength(1);
      expect(events[0].triggerType).toBe('daily_limit');
    });

    test('should not trigger below daily limit', async () => {
      manager.createRule('project1', 'daily_limit', ['console'], { dailyLimit: 10.0 });

      const events = await manager.checkAlert('project1', 50.0, 100.0, 5.0);

      expect(events).toHaveLength(0);
    });
  });

  describe('checkAlert() - Exceeded Trigger', () => {
    test('should trigger when budget is exceeded', async () => {
      manager.createRule('project1', 'exceeded', ['console'], {});

      const events = await manager.checkAlert('project1', 110.0, 100.0);

      expect(events).toHaveLength(1);
      expect(events[0].triggerType).toBe('exceeded');
    });

    test('should not trigger when within budget', async () => {
      manager.createRule('project1', 'exceeded', ['console'], {});

      const events = await manager.checkAlert('project1', 99.0, 100.0);

      expect(events).toHaveLength(0);
    });
  });

  describe('Alert Events', () => {
    test('should record alert events', async () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50 });

      await manager.checkAlert('project1', 50.0, 100.0);

      const events = manager.getAlertEvents({ projectId: 'project1' });
      expect(events).toHaveLength(1);
    });

    test('should include alert message in event', async () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50 });

      await manager.checkAlert('project1', 50.0, 100.0);

      const events = manager.getAlertEvents({ projectId: 'project1' });
      expect(events[0].message).toContain('$50.00');
    });

    test('should filter events by project', async () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50 });
      manager.createRule('project2', 'threshold', ['console'], { threshold: 50 });

      await manager.checkAlert('project1', 50.0, 100.0);
      await manager.checkAlert('project2', 50.0, 100.0);

      const p1Events = manager.getAlertEvents({ projectId: 'project1' });
      expect(p1Events).toHaveLength(1);
      expect(p1Events[0].projectId).toBe('project1');
    });
  });

  describe('Disabled Rules', () => {
    test('should not trigger disabled rules', async () => {
      const rule = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });
      manager.setRuleEnabled(rule.id, false);

      const events = await manager.checkAlert('project1', 50.0, 100.0);

      expect(events).toHaveLength(0);
    });
  });

  describe('getAllRules()', () => {
    test('should return all rules', () => {
      manager.createRule('project1', 'threshold', ['console'], { threshold: 50 });
      manager.createRule('project2', 'percentage', ['console'], {
        percentageThreshold: 80,
      });

      const allRules = manager.getAllRules();

      expect(allRules).toHaveLength(2);
    });
  });

  describe('Multiple Channels', () => {
    test('should send through multiple channels', async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
      mockFetch.mockResolvedValue({
        ok: true,
        statusText: 'OK',
      } as Response);

      manager.createRule('project1', 'threshold', ['console', 'webhook'], {
        threshold: 50,
        webhookUrl: 'https://example.com/alert',
      });

      const events = await manager.checkAlert('project1', 50.0, 100.0);

      expect(events).toHaveLength(1);
      expect(events[0].sentChannels).toContain('console');
    });
  });

  describe('Last Triggered Time', () => {
    test('should record last triggered time', async () => {
      const rule = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });

      expect(rule.lastTriggeredAt).toBeUndefined();

      await manager.checkAlert('project1', 50.0, 100.0);

      const updatedRule = manager.getRulesForProject('project1')[0];
      expect(updatedRule.lastTriggeredAt).toBeDefined();
      expect(updatedRule.lastTriggeredAt).toBeInstanceOf(Date);
    });
  });

  describe('Alert Event Filtering', () => {
    beforeEach(async () => {
      const rule1 = manager.createRule('project1', 'threshold', ['console'], {
        threshold: 50,
      });
      const rule2 = manager.createRule('project1', 'percentage', ['console'], {
        percentageThreshold: 80,
      });

      await manager.checkAlert('project1', 50.0, 100.0);
      await manager.checkAlert('project1', 80.0, 100.0);
    });

    test('should filter events by rule ID', () => {
      const allEvents = manager.getAlertEvents({ projectId: 'project1' });
      expect(allEvents).toHaveLength(2);

      const rule = manager.getRulesForProject('project1')[0];
      const filteredEvents = manager.getAlertEvents({ ruleId: rule.id });
      expect(filteredEvents).toHaveLength(1);
    });

    test('should filter events by since date', async () => {
      const beforeTime = new Date();
      await new Promise((resolve) => setTimeout(resolve, 100));
      const afterTime = new Date();

      await manager.checkAlert('project1', 50.0, 100.0);

      const events = manager.getAlertEvents({ since: afterTime });
      expect(events.length).toBeGreaterThan(0);
    });
  });
});
