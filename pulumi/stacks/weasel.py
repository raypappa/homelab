import pulumi
from pulumi_aws import route53


class Weasel(pulumi.ComponentResource):
    def __init__(self, name, primary_hosted_zone_name: str, opts=None):
        super().__init__("pkg:index:Weasel", name, None, opts)
        selected = route53.get_zone(
            name=primary_hosted_zone_name,
            private_zone=False,
        )
        route53.Record(
            "weasel_A_record",
            zone_id=selected.zone_id,
            name=f"weasel.{selected.name}",
            type=route53.RecordType.A,
            ttl=86400,
            records=[pulumi.Config().require_object("weasel")["primary_ipv4"]],
        )
        route53.Record(
            "weasel_AAAA_record",
            zone_id=selected.zone_id,
            name=f"weasel.{selected.name}",
            type=route53.RecordType.AAAA,
            ttl=86400,
            records=[pulumi.Config().require_object("weasel")["primary_ipv6"]],
        )
