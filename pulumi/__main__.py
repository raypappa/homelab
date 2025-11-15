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

# ha_user_access_key_dict = config.get_object("home_assistant_access_key")
# if ha_user_access_key_dict is None:
#     ha_user_access_key_dict = {
#         "access_key_id": ha_user_access_key.id,
#         "secret_access_key": ha_user_access_key.secret
#     }
#
# secretsmanager.SecretVersion(
#     "home_assistant_key_secret_version",
#     secret_id=secretsmanager.Secret(
#         "home_assistant_key_secret", name="/home-assistant/access-key"
#     ).id,
#     secret_string=std.jsonencode(ha_user_access_key_dict
#     ),
# )
