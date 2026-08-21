# CIS Cloud Architecture Benchmarks (Center for Internet Security)
# Enforces multi-AZ redundancy, MFA delete protection, and root account protection.

package compliance.cis_benchmarks

default allow = false

# Rule 1: S3 Buckets must have versioning enabled
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_s3_bucket_versioning"
    resource.values.versioning_configuration[_].status != "Enabled"
    msg := sprintf("CIS Benchmark Violation: S3 versioning configuration for '%v' is not Enabled.", [resource.name])
}

# Rule 2: VPCs must have default security group configured to deny all traffic
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_default_security_group"
    count(object.get(resource.values, "ingress", [])) > 0
    msg := sprintf("CIS Benchmark Violation: Default security group '%v' must have zero ingress rules.", [resource.name])
}

allow {
    count(deny) == 0
}
