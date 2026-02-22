"""An AWS Python Pulumi program"""
from stacks.weasel import Weasel
from stacks.home_assistant import HomeAssistant

primary_hosted_zone_name = 'stoneydavis.com.'
Weasel(primary_hosted_zone_name)
HomeAssistant(primary_hosted_zone_name)
