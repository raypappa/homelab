"""Narrowly-scoped AWS credentials for cert-manager + ESO.

This is the FIRST component of the cert management work.  It creates a dedicated
IAM user whose policy is limited to exactly the permissions Route53 DNS-01 and ESO
PushSecret need on `stoneydavis.com`:

- route53:ChangeResourceRecordSets / ListResourceRecordSets / GetChange on the
  stoneydavis.com hosted zone and the Route53 ``change/*`` resource;
- secretsmanager:PutSecretValue / DescribeSecret on the
  ``puma.stoneydavis.com-cert*`` secret.

The policy is deliberately narrow.  It does NOT include
``route53:TestDNSAnswer``, ``route53:ListHostedZonesByName``, ``iam:*``,
``AdministratorAccess``, or any access to any other hosted zone.  No OIDC
provider and no Pulumi-deploy role are created here.
"""

import pulumi
from pulumi_aws import iam


class CertManagerAwsCreds(pulumi.ComponentResource):
    """Create a narrow IAM user + access key for cert-manager Route53 and ESO Secrets Manager."""

    # Exposed by the component for other stacks to consume.
    access_key_id: pulumi.Output
    secret_access_key: pulumi.Output

    def __init__(self, name: str, opts: pulumi.ResourceOptions = None) -> None:
        super().__init__("cert:aws:creds", name, None, opts)

        # IAM user + access key pair for the cert-manager path.
        user = iam.User(f"{name}-user", name="cert-manager-aws-creds")
        access_key = iam.AccessKey(f"{name}-access-key", user=user.name)

        # --- Narrow policy -------------------------------------------------
        # Only the three Route53 actions needed for DNS-01, scoped to the
        # stoneydavis.com zone and the Route53 change/* resource.  Only the
        # Secrets Manager actions needed by ESO PushSecret, scoped to the
        # puma.stoneydavis.com-cert* secret.  Nothing else.
        policy_doc = iam.get_policy_document(
            statements=[
                {
                    "effect": "Allow",
                    "actions": [
                        "route53:ChangeResourceRecordSets",
                        "route53:ListResourceRecordSets",
                        "route53:GetChange",
                    ],
                    "resources": [
                        "arn:aws:route53:::hostedzone/Z07993151Z48PIABM0XKH",
                        "arn:aws:route53:::change/*",
                    ],
                },
                {
                    "effect": "Allow",
                    "actions": [
                        "secretsmanager:PutSecretValue",
                        "secretsmanager:DescribeSecret",
                    ],
                    "resources": [
                        "arn:aws:secretsmanager:us-west-2:181794460:secret:puma.stoneydavis.com-cert-*",
                    ],
                },
            ]
        )

        iam.UserPolicy(
            f"{name}-policy",
            name=f"{name}-policy",
            user=user.name,
            policy=policy_doc.json,
        )

        self.access_key_id = access_key.id
        self.secret_access_key = access_key.secret

        self.register_outputs(
            {
                "access_key_id": self.access_key_id,
                "secret_access_key": self.secret_access_key,
            }
        )
