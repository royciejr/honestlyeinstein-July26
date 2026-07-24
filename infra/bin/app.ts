#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { UploadPipelineStack } from '../lib/upload-pipeline-stack';
import { GenerationPipelineStack } from '../lib/generation-pipeline-stack';
import { BudgetStack } from '../lib/budget-stack';

const app = new cdk.App();

// Everything lives in ap-southeast-1 (decided: Bedrock Claude in-region).
// Account is resolved from the CLI credentials at deploy time; synth works
// without credentials (CI runs `cdk synth` with no AWS account).
const region = 'ap-southeast-1';

new UploadPipelineStack(app, 'MathsUploadPipeline', {
  stackName: 'maths-upload-pipeline',
  env: { region },
  description: 'Photo upload bucket + EventBridge + stub marker Lambda',
});

new GenerationPipelineStack(app, 'MathsGenerationPipeline', {
  stackName: 'maths-generation-pipeline',
  env: { region },
  description: 'Step Functions generate/verify/symcheck/write skeleton (stub Lambdas)',
});

// AWS::Budgets::Budget CloudFormation resources only deploy in us-east-1,
// hence the separate stack/region. The budget itself is account-global.
new BudgetStack(app, 'MathsBudget', {
  stackName: 'maths-budget',
  env: { region: 'us-east-1' },
  description: 'USD 30/month cost guardrail with email alerts',
});
