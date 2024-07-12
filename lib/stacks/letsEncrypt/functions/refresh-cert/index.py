import json
from typing import TypedDict
import boto3
import certbot.main
import datetime
import os
from aws_lambda_powertools import Logger

logger = Logger()

CONFIG_DIR = "/tmp/config-dir"
WORK_DIR = "/tmp/work-dir"
LOGS_DIR = "/tmp/logs-dir"


def read_and_delete_file(path: str):
    with open(path, "r") as file:
        contents = file.read()
    os.remove(path)
    return contents


class Cert(TypedDict):
    certificate: str
    private_key: str
    certificate_chain: str


def get_first_domain(domains: tuple[str]) -> str:
    """
    Returns the first domain from the given set of domains.

    tuple's are iterable, but not subscriptable, so
    ```
    for d in domains: return d
    ```
    works but
    ```
    domains[0]
    ```
    errors out.
    Basically `tuple` would need to implement `__getitem__` to be subscriptable.

    This also would apply to any `set` too.

    Args:
        domains (tuple[str]): A set of domains.

    Returns:
        str: The first domain from the set.

    """
    for d in domains:
        return d


def provision_cert(email: str, domains: tuple[str]) -> Cert:
    """
    Provisions a certificate using Certbot for the specified email and domains.

    Args:
        email (str): The email address to use for certificate registration.
        domains (str): Comma-separated list of domains to provision certificates
                       for.

    Returns:
        Cert: A dictionary containing the provisioned certificate, private key,
              and certificate chain.

    Raises:
        Any exceptions raised by Certbot during the certificate provisioning
        process.
    """
    certbot.main.main(
        [
            "certonly",  # Obtain a cert but don't install it
            "-n",  # Run in non-interactive mode
            "--agree-tos",  # Agree to the terms of service,
            "--email",
            email,  # Email
            "--dns-route53",  # Use dns challenge with route53
            "-d",
            ",".join(domains),  # Domains to provision certs for
            # Override directory paths so script doesn't have to be run as root
            "--config-dir",
            CONFIG_DIR,
            "--work-dir",
            WORK_DIR,
            "--logs-dir",
            LOGS_DIR,
        ]
    )

    first_domain = get_first_domain(domains)
    path = os.path.join(CONFIG_DIR, "live", first_domain)

    logger.info("Files in %s: %s", path, ", ".join(os.listdir(CONFIG_DIR)))
    logger.info("Files in %s: %s", path, ", ".join(os.listdir(path)))

    return {
        "certificate": read_and_delete_file(os.path.join(path, "cert.pem")),
        "private_key": read_and_delete_file(os.path.join(path, "privkey.pem")),
        "certificate_chain": read_and_delete_file(os.path.join(path, "chain.pem")),
    }


def should_provision(domains: tuple[str]) -> bool:
    """
    Determines whether a new certificate should be provisioned for the given domains.

    Args:
        domains (tuple[str]): A set of domain names for which the certificate is requested.

    Returns:
        bool: True if a new certificate should be provisioned, False otherwise.
    """
    existing_cert = find_existing_cert(domains)
    if existing_cert:
        now = datetime.datetime.now(datetime.timezone.utc)
        not_after = existing_cert["Certificate"]["NotAfter"]
        return (not_after - now).days <= 30
    else:
        return True


def find_existing_cert_in_acm(domains: tuple[str]):
    """
    Finds an existing certificate in AWS Certificate Manager (ACM) that matches
    the given domains.

    Args:
        domains (tuple[str]): A tuple of domain names to match against
        the Subject Alternative Names (SANs) of the certificates.

    Returns:
        dict or None: The certificate details if a matching certificate is
        found, otherwise None.
    """

    client = boto3.client("acm")
    paginator = client.get_paginator("list_certificates")
    iterator = paginator.paginate(
        PaginationConfig={"MaxItems": 1000},
        Includes={
            "keyTypes": ["EC_prime256v1"],
        },
    )

    for page in iterator:
        for cert in page["CertificateSummaryList"]:
            cert = client.describe_certificate(CertificateArn=cert["CertificateArn"])
            sans: tuple[str] = tuple(cert["Certificate"]["SubjectAlternativeNames"])
            if sans.issubset(domains):
                return cert
    return None


def find_existing_cert(domains: tuple[str]):
    """
    Finds an existing certificate for the given domains.

    Args:
        domains (tuple[str]): A set of domain names for which to find the certificate.

    Returns:
        str: The ARN of the existing certificate, if found. Otherwise, None.
    """
    return find_existing_cert_in_acm(domains)


def upload_cert_to_acm(cert: Cert, domains: tuple[str]):
    """
    Uploads a certificate to AWS Certificate Manager (ACM) and returns the ARN
    of the uploaded certificate.

    Args:
        cert (Cert): The certificate object containing the certificate, private
        key, and certificate chain. domains (tuple[str]): The set of domains
        associated with the certificate.

    Returns:
        str: The ARN of the uploaded certificate.

    """
    existing_cert = find_existing_cert(domains)
    certificate_arn = (
        existing_cert["Certificate"]["CertificateArn"] if existing_cert else None
    )

    client = boto3.client("acm")
    kwargs = dict(
        Certificate=cert["certificate"],
        PrivateKey=cert["private_key"],
        CertificateChain=cert["certificate_chain"],
    )
    if certificate_arn:
        kwargs["CertificateArn"] = certificate_arn

    acm_response = client.import_certificate(**kwargs)

    return None if certificate_arn else acm_response["CertificateArn"]


def find_existing_cert_in_secrets_manager(domains: tuple[str]):
    """
    Finds an existing certificate in Secrets Manager based on the given domains.

    Args:
        domains (tuple[str]): A set of domain names associated with the certificate.

    Returns:
        dict or None: The certificate information as a dictionary if found, None otherwise.
    """
    first_domain = get_first_domain(domains)
    secret_name = f"{first_domain}-cert"
    client = boto3.client("secretsmanager")
    try:
        secret = client.get_secret_value(SecretId=secret_name)
        return json.loads(secret["SecretString"])
    except client.exceptions.ResourceNotFoundException:
        return None


def upload_cert_to_secrets_manager(cert: Cert, domains: tuple[str]):
    """
    Uploads the certificate to AWS Secrets Manager.

    Args:
        cert (Cert): The certificate to upload.
        domains (tuple[str]): The domains associated with the certificate.

    Returns:
        None
    """
    first_domain = domains[0]
    secret_name = f"{first_domain}-cert"
    client = boto3.client("secretsmanager")
    kwargs = {"SecretString": json.dumps(cert)}
    try:
        client.create_secret(Name=secret_name, **kwargs)
    except client.exceptions.ResourceExistsException:
        client.put_secret_value(SecretId=secret_name, **kwargs)


def upload(cert: Cert, domains: tuple[str]):
    """
    Uploads the certificate to ACM (AWS Certificate Manager) and Secrets Manager.

    Args:
        cert (Cert): The certificate to upload.
        domains (tuple[str]): The set of domains associated with the certificate.

    Returns:
        None
    """
    upload_cert_to_secrets_manager(cert, domains)
    upload_cert_to_acm(cert, domains)


def handler(event, context):
    """
    Lambda function handler for refreshing Let's Encrypt certificates.

    Args:
        event: The event data passed to the Lambda function.
        context: The runtime information of the Lambda function.

    Returns:
        None
    """
    domains: str = os.environ["LETSENCRYPT_DOMAINS"]
    # frozenset was causing issues with ordering of the domains.
    domains_set = tuple(map(lambda x: x.strip(), domains.split(",")))
    email: str = os.environ["LETSENCRYPT_EMAIL"]
    if should_provision(domains_set):
        cert = provision_cert(email, domains_set)
        upload(cert, domains_set)
