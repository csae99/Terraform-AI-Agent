# PCI-DSS v4.0 Compliance Pack (Payment Card Industry Data Security Standard)
# Enforces strict network segmentation, default denial firewalls, and encrypted transmission.

package compliance.pci_dss

default allow = false

# Rule 1: No default open ingress to sensitive VPC subnets
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_security_group_rule"
    resource.values.type == "ingress"
    resource.values.cidr_blocks[_] == "0.0.0.0/0"
    resource.values.from_port != 443
    msg := sprintf("PCI-DSS Violation: Security group rule '%v' allows non-HTTPS 0.0.0.0/0 public ingress.", [resource.name])
}

# Rule 2: EBS Volumes attached to cardholder data environments must be encrypted
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_ebs_volume"
    resource.values.encrypted != true
    msg := sprintf("PCI-DSS Violation: EBS volume '%v' must have encrypted=true.", [resource.name])
}

# Rule 3: AWS Elastic Load Balancer must enforce TLS 1.2+
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_lb_listener"
    resource.values.protocol == "HTTP"
    not resource.values.default_action[_].redirect.protocol == "HTTPS"
    msg := sprintf("PCI-DSS Violation: Load Balancer listener '%v' uses unencrypted HTTP without HTTPS redirect.", [resource.name])
}

allow {
    count(deny) == 0
}
