import * as python from "@aws-cdk/aws-lambda-python-alpha";
import {
  Duration,
  Stack,
  StackProps,
  aws_events,
  aws_events_targets,
  aws_iam,
  aws_lambda,
} from "aws-cdk-lib";
import { Construct } from "constructs";

export class LetsEncryptStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const powerToolsLayer = aws_lambda.LayerVersion.fromLayerVersionArn(
      this,
      "PowerToolsLayer",
      `arn:aws:lambda:${this.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:59`,
    );

    const publicDomainName = this.node.getContext(
      "infrastructure:internalPublicDomain",
    );
    const email = this.node.getContext("infrastructure:letsEncryptEmail");

    const fn = new python.PythonFunction(this, "letsEncrypt", {
      entry: "lib/stacks/letsEncrypt/functions/refresh-cert",
      runtime: aws_lambda.Runtime.PYTHON_3_12,
      layers: [powerToolsLayer],
      timeout: Duration.minutes(5),
      environment: {
        LETSENCRYPT_DOMAINS: `${publicDomainName},*.${publicDomainName}`,
        LETSENCRYPT_EMAIL: email,
      },
      bundling: {
        assetExcludes: [".venv"],
      },
    });

    const rule = new aws_events.Rule(this, "rule", {
      schedule: aws_events.Schedule.rate(Duration.days(1)),
    });
    rule.addTarget(new aws_events_targets.LambdaFunction(fn));

    fn.grantInvoke(new aws_iam.ServicePrincipal("events.amazonaws.com"));
    fn.addToRolePolicy(
      new aws_iam.PolicyStatement({
        actions: [
          "acm:DescribeCertificate",
          "acm:ImportCertificate",
          "acm:ListCertificates",
          "route53:ChangeResourceRecordSets",
          "route53:GetChange",
          "route53:ListCertificates",
          "route53:ListHostedZones",
          "secretsmanager:GetSecretValue",
          "secretsmanager:ListSecrets",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage",
          "secretsmanager:CreateSecret",
        ],
        resources: ["*"],
      }),
    );
  }
}
