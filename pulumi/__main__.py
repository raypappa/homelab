"""An AWS Python Pulumi program."""

from stacks.weasel import Weasel
from stacks.cert_aws_creds import CertManagerAwsCreds
from stacks.home_assistant import HomeAssistant
import pulumi

primary_hosted_zone_name = "stoneydavis.com."
Weasel("weasel", primary_hosted_zone_name)
ha = HomeAssistant("home_assistant", primary_hosted_zone_name)
cert_creds = CertManagerAwsCreds("cert-manager-aws-creds")
pulumi.export("home_assistant_access_key_id", ha.access_key_id)
pulumi.export("home_assistant_secret_access_key", ha.secret_access_key)
pulumi.export("cert_manager_aws_creds_access_key_id", cert_creds.access_key_id)
pulumi.export("cert_manager_aws_creds_secret_access_key", cert_creds.secret_access_key)
