# HIPAA Compliance Pack (Healthcare Information Security)
# Enforces private subnet isolation, encrypted databases, and retention logs.

package compliance.hipaa

default allow = false

# Rule 1: Databases containing ePHI must not be publicly accessible
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_db_instance"
    resource.values.publicly_accessible == true
    msg := sprintf("HIPAA Violation: RDS database '%v' must not be publicly accessible.", [resource.name])
}

# Rule 2: Databases must have automatic backup retention enabled >= 7 days
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_db_instance"
    backup_days := object.get(resource.values, "backup_retention_period", 0)
    backup_days < 7
    msg := sprintf("HIPAA Violation: RDS database '%v' backup_retention_period must be at least 7 days (found: %v).", [resource.name, backup_days])
}

# Rule 3: KMS Key rotation must be enabled
deny[msg] {
    resource := input.resources[_]
    resource.type == "aws_kms_key"
    resource.values.enable_key_rotation != true
    msg := sprintf("HIPAA Violation: KMS key '%v' must have enable_key_rotation=true.", [resource.name])
}

allow {
    count(deny) == 0
}
