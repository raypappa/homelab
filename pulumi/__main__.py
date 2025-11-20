"""An AWS Python Pulumi program"""

import pulumi
from pulumi_aws import iam, route53

ha_user = iam.User("home_assistant_user", name="home-assistant")
ha_user_access_key = iam.AccessKey("home_assistant_key", user=ha_user.name)
selected = route53.get_zone(
    name="stoneydavis.com.",
    private_zone=False,
)
ha_iam_policy_doc = iam.get_policy_document(
    statements=[
        {
            "effect": "Allow",
            "actions": [
                "route53:GetHostedZone",
                "route53:ChangeResourceRecordSets",
                "route53:ListResourceRecordSets",
            ],
            "resources": [selected.arn],
        },
        {
            "effect": "Allow",
            "resources": ["*"],
            "actions": ["route53:TestDNSAnswer"],
        },
    ]
)
iam.UserPolicy(
    "r53",
    name="r53",
    user=ha_user.name,
    policy=ha_iam_policy_doc.json,
)


pulumi.export("home_assistant_access_key_id", ha_user_access_key.id)
pulumi.export("home_assistant_secret_access_key", ha_user_access_key.secret)


org = pulumi.get_organization()
proj = pulumi.get_project()
oidc_aud = org

default = iam.OpenIdConnectProvider(
    "default", url="https://api.pulumi.com/oidc", client_id_lists=[oidc_aud]
)

pulumi_role = iam.Role(
    "pulumi_oidc",
    name_prefix="pulumi-oidc",
    assume_role_policy=iam.get_policy_document(
        statements=[
            {
                "effect": "Allow",
                "actions": ["sts:AssumeRoleWithWebIdentity"],
                "principals": [{"type": "Federated", "identifiers": [default.arn]}],
                "conditions": [
                    {
                        "test": "StringEquals",
                        "variable": "api.pulumi.com/oidc:aud",
                        "values": [oidc_aud],
                    },
                    {
                        "test": "StringLike",
                        "variable": "api.pulumi.com/oidc:sub",
                        "values": [f"pulumi:deploy:org:{org}:project:{proj}:*"],
                    },
                ],
            }
        ]
    ).json,
)
iam.RolePolicyAttachment(
    "pulumi_oidc_role_admin",
    role=pulumi_role.name,
    policy_arn=iam.get_policy(name="AdministratorAccess").arn,
)

