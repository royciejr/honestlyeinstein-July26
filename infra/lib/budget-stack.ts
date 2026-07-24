import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as budgets from 'aws-cdk-lib/aws-budgets';

/** USD 30/month guardrail: alert at 80% actual and 100% forecast. */
export class BudgetStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const email: string =
      this.node.tryGetContext('budgetEmail') || process.env.BUDGET_ALERT_EMAIL || '';
    if (!email) {
      cdk.Annotations.of(this).addWarningV2(
        'maths:missing-budget-email',
        'No budgetEmail context / BUDGET_ALERT_EMAIL env set — synth OK, but set it ' +
          'before deploying this stack or the alerts have nowhere to go.',
      );
    }

    const subscriber: budgets.CfnBudget.SubscriberProperty = {
      subscriptionType: 'EMAIL',
      address: email || 'change-me@example.com',
    };

    new budgets.CfnBudget(this, 'MonthlyBudget', {
      budget: {
        budgetName: 'maths-platform-monthly',
        budgetType: 'COST',
        timeUnit: 'MONTHLY',
        budgetLimit: { amount: 30, unit: 'USD' },
      },
      notificationsWithSubscribers: [
        {
          notification: {
            notificationType: 'ACTUAL',
            comparisonOperator: 'GREATER_THAN',
            threshold: 80,
            thresholdType: 'PERCENTAGE',
          },
          subscribers: [subscriber],
        },
        {
          notification: {
            notificationType: 'FORECASTED',
            comparisonOperator: 'GREATER_THAN',
            threshold: 100,
            thresholdType: 'PERCENTAGE',
          },
          subscribers: [subscriber],
        },
      ],
    });
  }
}
