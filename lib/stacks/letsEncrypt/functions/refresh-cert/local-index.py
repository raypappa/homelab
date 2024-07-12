import json
from typing import TypedDict
import boto3
import certbot.main
import datetime
import os
import subprocess
from aws_lambda_powertools import Logger


# https://us-west-2.console.aws.amazon.com/acm/ajax/list_certs.json?maxItems=100
session = boto3.session.Session()
client = session.client("acm")
r = client._make_api_call("list_certs")
