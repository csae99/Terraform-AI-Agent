You point Terraform’s AWS provider to the local Floci endpoint instead of real AWS.

Example:

## 1. Run Floci

```bash id="rtivxe"
docker run -d --name floci -p 4566:4566 floci/floci
```

## 2. Set dummy credentials

```bash id="m0qz7o"
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

## 3. Terraform provider config

```hcl id="8t4g1j"
provider "aws" {
  access_key = "test"
  secret_key = "test"
  region     = "us-east-1"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    eks = "http://localhost:4566"
    ec2 = "http://localhost:4566"
    iam = "http://localhost:4566"
    s3  = "http://localhost:4566"
  }
}
```

## 4. Example EKS resource

```hcl id="6xrr5l"
resource "aws_eks_cluster" "demo" {
  name     = "demo-cluster"
  role_arn = "arn:aws:iam::000000000000:role/test-role"

  vpc_config {
    subnet_ids = ["subnet-123"]
  }
}
```

## 5. Run Terraform

```bash id="f0e1nt"
terraform init
terraform plan
terraform apply
```

Then verify:

```bash id="bjlwm5"
aws --endpoint-url=http://localhost:4566 eks list-clusters
```

This is useful for:

* Terraform learning
* CI/CD testing
* Validating IaC before real AWS deployment
* Offline/local development
* Fast integration tests

Important:

* Not every AWS feature is fully implemented.
* Some advanced networking/IAM behaviors are simplified.
* Terraform state behaves normally.
