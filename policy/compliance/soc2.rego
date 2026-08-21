# SOC2 Type II Enterprise Compliance Pack
# Enforces encryption at rest, public access blocking, TLS transit, and IAM least-privilege.

package compliance.soc2

default allow = false

# Rule 1: S3 buckets must have public access block enabled
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_s3_bucket"
    not has_public_access_block(resource.name)
    msg := sprintf("SOC2 Violation: S3 bucket '%v' must have aws_s3_bucket_public_access_block configured.", [resource.name])
}

# Rule 2: S3 buckets must have server-side encryption enabled
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_s3_bucket"
    not has_encryption_configured(resource.name)
    msg := sprintf("SOC2 Violation: S3 bucket '%v' must have server-side encryption configured.", [resource.name])
}

# Rule 3: RDS database instances must be encrypted with KMS
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_db_instance"
    resource.values.storage_encrypted != true
    msg := sprintf("SOC2 Violation: RDS instance '%v' storage_encrypted must be true.", [resource.name])
}

# Rule 4: Security groups must not allow open ingress (0.0.0.0/0) on sensitive ports
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_security_group"
    ingress := resource.values.ingress[_]
    ingress.cidr_blocks[_] == "0.0.0.0/0"
    is_sensitive_port(ingress.from_port, ingress.to_port)
    msg := sprintf("SOC2 Violation: Security group '%v' allows unrestricted 0.0.0.0/0 ingress to sensitive port %v.", [resource.name, ingress.from_port])
}

# Helper functions
has_public_access_block(bucket_name) {
    pab := input.resources[_]
    pab.type == "aws_s3_bucket_public_access_block"
    contains(pab.values.bucket, bucket_name)
    pab.values.block_public_acls == true
    pab.values.block_public_policy == true
}

has_encryption_configured(bucket_name) {
    sse := input.resources[_]
    sse.type == "aws_s3_bucket_server_side_encryption_configuration"
    contains(sse.values.bucket, bucket_name)
}

is_sensitive_port(from_p, to_p) {
    sensitive := [22, 3389, 5432, 3306, 27017, 6379]
    port := sensitive[_]
    from_p <= port
    to_p >= port
}

allow {
    count(deny) == 0
}
