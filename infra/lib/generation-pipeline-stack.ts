import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as path from 'path';

/**
 * Batch question-generation pipeline skeleton:
 *   generate (Lambda→Bedrock) → verify (different persona) → symcheck (SymPy)
 *   → write-approved, with a human-review branch on disagreement.
 * Phase 1 deploys stub Lambdas so the state machine is invocable end-to-end;
 * the writer posts real HMAC-signed rows through the API either way.
 * Pass {"force_disagreement": true} as execution input to exercise the
 * review branch.
 */
export class GenerationPipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const apiBaseUrl: string =
      this.node.tryGetContext('apiBaseUrl') ?? 'http://localhost:8000';
    const hmacSecret = process.env.INTERNAL_HMAC_SECRET ?? '';

    const assetDir = path.join(__dirname, '..', 'lambdas', 'sfn');
    const makeFn = (name: string, handler: string, env: Record<string, string> = {}) =>
      new lambda.Function(this, name, {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler,
        code: lambda.Code.fromAsset(assetDir),
        timeout: cdk.Duration.seconds(60),
        memorySize: 256,
        environment: env,
        logGroup: new logs.LogGroup(this, `${name}Logs`, {
          retention: logs.RetentionDays.ONE_WEEK,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      });

    // Phase 2: generate/verify get Bedrock env + IAM; symcheck gets a SymPy
    // container image (SymPy exceeds the zip limit comfortably).
    const generateFn = makeFn('GenerateFn', 'generate.handler');
    const verifyFn = makeFn('VerifyFn', 'verify.handler');
    const symcheckFn = makeFn('SymcheckFn', 'symcheck.handler');
    const writerFn = makeFn('WriterFn', 'writer.handler', {
      API_BASE_URL: apiBaseUrl,
      INTERNAL_HMAC_SECRET: hmacSecret,
    });

    const generate = new tasks.LambdaInvoke(this, 'Generate', {
      lambdaFunction: generateFn,
      payloadResponseOnly: true,
      resultPath: '$.generated',
    });
    const verify = new tasks.LambdaInvoke(this, 'Verify', {
      lambdaFunction: verifyFn,
      payloadResponseOnly: true,
      resultPath: '$.verified',
    });
    const symcheck = new tasks.LambdaInvoke(this, 'Symcheck', {
      lambdaFunction: symcheckFn,
      payloadResponseOnly: true,
      resultPath: '$.symchecked',
    });
    const writeApproved = new tasks.LambdaInvoke(this, 'WriteApproved', {
      lambdaFunction: writerFn,
      payloadResponseOnly: true,
      payload: sfn.TaskInput.fromObject({
        kind: 'approved',
        'state.$': '$',
      }),
    });
    const humanReview = new tasks.LambdaInvoke(this, 'HumanReview', {
      lambdaFunction: writerFn,
      payloadResponseOnly: true,
      payload: sfn.TaskInput.fromObject({
        kind: 'review',
        'state.$': '$',
      }),
    });

    const allAgree = sfn.Condition.and(
      sfn.Condition.booleanEquals('$.verified.agrees', true),
      sfn.Condition.booleanEquals('$.symchecked.ok', true),
    );

    const definition = generate
      .next(verify)
      .next(symcheck)
      .next(
        new sfn.Choice(this, 'AllChecksAgree')
          .when(allAgree, writeApproved)
          .otherwise(humanReview),
      );

    const stateMachine = new sfn.StateMachine(this, 'GenerationStateMachine', {
      stateMachineName: 'maths-template-generation',
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.minutes(10),
    });

    new cdk.CfnOutput(this, 'StateMachineArn', { value: stateMachine.stateMachineArn });
  }
}
