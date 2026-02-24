"""An AWS Python Pulumi program"""

from stacks.weasel import Weasel
from stacks.home_assistant import HomeAssistant

primary_hosted_zone_name = "stoneydavis.com."
Weasel("weasel", primary_hosted_zone_name)
HomeAssistant("home_assistant", primary_hosted_zone_name)
