#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import "source-map-support/register";
import { GithubOIDCStack } from "../lib/stacks/githubOIDC";

const app = new cdk.App();

new GithubOIDCStack(app, "GithubOIDC", {});
