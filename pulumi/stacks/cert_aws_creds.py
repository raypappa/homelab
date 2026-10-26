"""Narrowly-scoped AWS credentials for cert-manager + ESO.

This is the FIRST component of the cert management work.  It creates a dedicated
IAM user whose policy is limited to exactly the permissions Route53 DNS-01 and ESO
PushSecret need on the hosted zone and the secret the component is pointed at:

- route53:ChangeResourceRecordSets / ListResourceRecordSets / GetChange on the
  hosted zone it is given and the Route53 ``change/*`` resource;
- secretsmanager:PutSecretValue / DescribeSecret on the ``<secret_name>-*``
  secret.

Nothing about the account, the region, the partition or the hosted zone is
hardcoded.  The hosted zone is looked up -- which also proves it exists -- and
the account, region and partition come from the provider's own credentials and
configuration.

The policy is deliberately narrow.  It does NOT include
``route53:TestDNSAnswer``, ``route53:ListHostedZonesByName``, ``iam:*``,
``AdministratorAccess``, or any access to any other hosted zone.  No OIDC
provider and no Pulumi-deploy role are created here.
"""

import pulumi
from pulumi_aws import get_caller_identity, get_partition, get_region, iam, route53


class CertManagerAwsCreds(pulumi.ComponentResource):
    """Create a narrow IAM user + access key for cert-manager Route53 and ESO Secrets Manager.

    :param name: Name of the component, also the prefix of the resources it creates.
    :param hosted_zone_name: Name of the public Route53 hosted zone cert-manager
        will update, e.g. ``stoneydavis.com.``.  The zone is looked up, so a name
        that does not resolve to an existing public zone fails the deployment
        instead of quietly producing a policy scoped to a zone that is not there.
    :param secret_name: Base name of the Secrets Manager secret ESO will push
        to.  Secrets Manager appends a random six-character suffix to secret
        IDs, so the policy is scoped to ``<secret_name>-*``.
    :param opts: Options handed to the component resource.
    """

    # Exposed by the component for other stacks to consume.
    access_key_id: pulumi.Output
    secret_access_key: pulumi.Output

    def __init__(
        self,
        name: str,
        hosted_zone_name: str,
        secret_name: str,
        opts: pulumi.ResourceOptions = None,
    ) -> None:
        super().__init__("cert:aws:creds", name, None, opts)

        # Look the hosted zone up instead of hardcoding its ARN.  This scopes
        # the policy to the zone that was asked for and validates it at the same
        # time: get_zone fails the deployment when no public zone with that name
        # exists.
        zone = route53.get_zone(name=hosted_zone_name, private_zone=False)

        # Account, region and partition come from the provider's own credentials
        # and configuration rather than being pinned into the policy.
        account_id = get_caller_identity().account_id
        region = get_region().region
        partition = get_partition().partition

        # IAM user + access key pair for the cert-manager path.
        # The user is inherently a user, so the resource name carries no
        # redundant "-user" suffix.
        aws_creds = iam.User("cert-manager-aws-creds", name="cert-manager-aws-creds")
        access_key = iam.AccessKey(f"{name}-access-key", user=aws_creds.name)

        # --- Narrow policy -------------------------------------------------
        # Only the three Route53 actions needed for DNS-01, scoped to the
        # hosted zone that was looked up and the Route53 change/* resource.
        # Only the Secrets Manager actions needed by ESO PushSecret, scoped to
        # the secret it was given.  Nothing else.
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
                        zone.arn,
                        pulumi.Output.format("arn:{}:route53:::change/*", partition),
                    ],
                },
                {
                    "effect": "Allow",
                    "actions": [
                        "secretsmanager:PutSecretValue",
                        "secretsmanager:DescribeSecret",
                    ],
                    "resources": [
                        pulumi.Output.format(
                            "arn:{}:secretsmanager:{}:{}:secret:{}-*",
                            partition,
                            region,
                            account_id,
                            secret_name,
                        ),
                    ],
                },
            ]
        )

        iam.UserPolicy(
            f"{name}-policy",
            name=f"{name}-policy",
            user=aws_creds.name,
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
