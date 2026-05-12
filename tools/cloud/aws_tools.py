import os

class CloudSync:
    """
    Handles cloud credential detection and terraform backend configuration templates.
    """
    
    def __init__(self):
        self.providers = {
            "AWS": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
            "GCP": ["GOOGLE_APPLICATION_CREDENTIALS"],
            "AZURE": ["ARM_SUBSCRIPTION_ID", "ARM_CLIENT_ID", "ARM_CLIENT_SECRET"]
        }

    def check_cloud_readiness(self):
        """
        Scans environment variables for active cloud credentials.
        Returns a dictionary with readiness status and detected provider.
        """
        results = {
            "ready": False,
            "provider": "Local",
            "detected_vars": []
        }
        
        for provider, vars in self.providers.items():
            missing = [v for v in vars if not os.getenv(v)]
            if not missing:
                results["ready"] = True
                results["provider"] = provider
                results["detected_vars"] = vars
                return results
                
        return results

    def get_backend_template(self, project_slug, provider="AWS"):
        """
        Returns a security-hardened backend configuration block.
        Enforces use of -tf-state suffix for bucket names.
        """
        bucket_name = f"{project_slug}-tf-state".lower().replace("_", "-")
        
        if provider == "AWS":
            return f"""
terraform {{
  backend "s3" {{
    bucket         = "{bucket_name}"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "{bucket_name}-lock"
  }}
}}
"""
        return ""

    def generate_bootstrap_code(self, project_slug, provider="AWS"):
        """
        Generates Terraform code to create the initial S3 bucket and DynamoDB table.
        """
        bucket_name = f"{project_slug}-tf-state".lower().replace("_", "-")
        
        if provider == "AWS":
            return f"""
provider "aws" {{
  region = "us-east-1"
}}

resource "aws_s3_bucket" "state_bucket" {{
  bucket = "{bucket_name}"
  force_destroy = false
}}

resource "aws_s3_bucket_versioning" "state_versioning" {{
  bucket = aws_s3_bucket.state_bucket.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

resource "aws_dynamodb_table" "state_lock" {{
  name         = "{bucket_name}-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {{
    name = "LockID"
    type = "S"
  }}
}}
"""
        return ""
