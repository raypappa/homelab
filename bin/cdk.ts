#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import "source-map-support/register";
import { GithubOIDCStack } from "../lib/stacks/githubOIDC";
import { LetsEncryptStack } from "../lib/stacks/letsEncrypt";

const app = new cdk.App();

new GithubOIDCStack(app, "GithubOIDC", {});
new LetsEncryptStack(app, "LetsEncrypt", {});
