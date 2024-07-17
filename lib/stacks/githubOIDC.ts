import { Duration, Stack, type StackProps, aws_iam } from "aws-cdk-lib";
import type { Construct } from "constructs";
// import * as sqs from 'aws-cdk-lib/aws-sqs';

type GithubOrg = string;
type GithubRepo = string;
type GitHubMap = Record<GithubOrg, GithubRepo[]>;
const githubDomain = "token.actions.githubusercontent.com";
export class GithubOIDCStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const provider = new aws_iam.OpenIdConnectProvider(this, "GithubProvider", {
      url: `https://${githubDomain}`,
      clientIds: ["sts.amazonaws.com"],
    });
    const githubMappings: GitHubMap = this.node.tryGetContext("githubMap");
    const repos = Object.keys(githubMappings).flatMap((org) => {
      return githubMappings[org].map((repo) => {
        return `repo:${org}/${repo}:*`;
      });
    });
    const conditions: aws_iam.Conditions = {
      StringLike: {
        [`${githubDomain}:sub`]: repos,
      },
    };
    const principal = new aws_iam.OpenIdConnectPrincipal(provider, conditions);

    const role = new aws_iam.Role(this, "Role", {
      assumedBy: principal,
      managedPolicies: [
        aws_iam.ManagedPolicy.fromAwsManagedPolicyName("AdministratorAccess"),
      ],
      description:
        "This role is used via GitHub Actions to deploy with AWS CDK or Terraform on the target AWS account",
      maxSessionDuration: Duration.hours(1),
    });
  }
}
