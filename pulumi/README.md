# Pulumi

Deploying resource using pulumi

## Overview

### AWS

- Create IAM user for home-assistant integration for managing r53 records.

## Getting Started

### Preview the planned changes

```bash
task pulumi:preview
```

### Deploy the stack

```bash
task pulumi:up
```

### Tear down when finished

```bash
task pulumi:destroy
```

## Project Layout

After running `pulumi new`, your directory will look like:

```
├── __main__.py         # Entry point of the Pulumi program
├── Pulumi.yaml         # Project metadata and template configuration
└── Pulumi.<stack>.yaml # Stack-specific configuration (e.g., Pulumi.dev.yaml)
```

## Configuration

This template defines the following config value:

- `aws:region` (string)
  The AWS region to deploy resources into.
  Default: `us-east-1`

View or update configuration with:

```bash
pulumi config get aws:region
pulumi config set aws:region us-west-2
```

## Outputs

Once deployed, the stack exports:

### Retrieve outputs

```bash
pulumi stack output bucket_name
```

if the output is a secret then use

```bash
pulumi stack output bucket_name --show-secrets
```
