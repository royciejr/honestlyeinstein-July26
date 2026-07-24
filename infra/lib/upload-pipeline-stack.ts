import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';

/**
 * Photo pipeline: browser PUTs to S3 via a presigned URL from the API,
 * S3 emits an EventBridge "Object Created" event, the marker Lambda reads the
 * image (stubbed in Phase 1) and posts HMAC-signed marking JSON back to the
 * API's /internal/marking-result endpoint.
 */
export class UploadPipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const webOrigins: string[] =
      this.node.tryGetContext('webOrigins') ?? ['http://localhost:3000'];
    const apiBaseUrl: string =
      this.node.tryGetContext('apiBaseUrl') ?? 'http://localhost:8000';
    const hmacSecret = process.env.INTERNAL_HMAC_SECRET ?? '';
    if (!hmacSecret) {
      cdk.Annotations.of(this).addWarningV2(
        'maths:missing-hmac-secret',
        'INTERNAL_HMAC_SECRET is not set — fine for synth, required for a working deploy. ' +
          'Export it before `cdk deploy` (see docs/RUNBOOK.md).',
      );
    }

    const bucket = new s3.Bucket(this, 'UploadBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      eventBridgeEnabled: true,
      lifecycleRules: [
        {
          id: 'child-data-retention-90d',
          expiration: cdk.Duration.days(90),
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
      ],
      cors: [
        {
          // Browser PUTs directly to the bucket, so S3 CORS must allow the
          // web origins. Update the webOrigins context after the first
          // Vercel deploy (cdk.json or -c webOrigins='[...]').
          allowedMethods: [s3.HttpMethods.PUT],
          allowedOrigins: webOrigins,
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
      // Teardown deletes the bucket only if empty — never silently destroys
      // children's photos.
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const markerFn = new lambda.Function(this, 'MarkerFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'marker')),
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
      description: 'Marks uploaded photos (Phase 1: stub JSON behind MARKER_STUB_ENABLED)',
      environment: {
        API_BASE_URL: apiBaseUrl,
        INTERNAL_HMAC_SECRET: hmacSecret,
        MARKER_STUB_ENABLED: 'true',
        // Phase 2: in-region Claude via the APAC cross-region inference profile.
        BEDROCK_MODEL_ID: 'apac.anthropic.claude-sonnet-4-5-20250929-v1:0',
      },
      logGroup: new logs.LogGroup(this, 'MarkerLogs', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    bucket.grantRead(markerFn);
    // Phase 2 readiness: the real marker calls Bedrock. Harmless while stubbed.
    markerFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [
          `arn:aws:bedrock:*::foundation-model/anthropic.*`,
          `arn:aws:bedrock:*:${this.account}:inference-profile/apac.anthropic.*`,
        ],
      }),
    );

    const rule = new events.Rule(this, 'ObjectCreatedRule', {
      description: 'uploads/ object created -> marker Lambda',
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['Object Created'],
        detail: {
          bucket: { name: [bucket.bucketName] },
          object: { key: [{ prefix: 'uploads/' }] },
        },
      },
    });
    rule.addTarget(
      new targets.LambdaFunction(markerFn, {
        retryAttempts: 2,
        maxEventAge: cdk.Duration.hours(1),
      }),
    );

    new cdk.CfnOutput(this, 'UploadBucketName', {
      value: bucket.bucketName,
      description: 'Set this as S3_UPLOAD_BUCKET in the API env',
    });
    new cdk.CfnOutput(this, 'MarkerFunctionName', { value: markerFn.functionName });
  }
}
