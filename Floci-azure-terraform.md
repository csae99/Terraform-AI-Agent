
## 1. Run floci-az

```bash id="5s9m3o"
docker run -d --name floci-az \
  -p 4577:4577 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  floci/floci-az:latest
```

## 2. Terraform provider

```hcl id="1d9pca"
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id = "00000000-0000-0000-0000-000000000000"
  tenant_id       = "00000000-0000-0000-0000-000000000000"
  client_id       = "test"
  client_secret   = "test"

  resource_provider_registrations = "none"

  storage_use_azuread = false
}
```

## 3. Set endpoint overrides

For services like Blob Storage / Cosmos / Key Vault:

```bash id="vgnf91"
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=test;BlobEndpoint=http://127.0.0.1:4577/devstoreaccount1;"
```

## 4. Example Terraform resource

```hcl id="e9d30y"
resource "azurerm_resource_group" "demo" {
  name     = "demo-rg"
  location = "East US"
}
```

## 5. Run Terraform

```bash id="k4m4fr"
terraform init
terraform apply
```

Recent versions also added:

* AKS emulation (k3s-backed)
* Cosmos DB
* Key Vault
* Event Hubs
* Azure Functions ([Reddit][2])

For AKS testing specifically:

```hcl id="9tcr3u"
resource "azurerm_kubernetes_cluster" "demo" {
  name                = "demo-aks"
  location            = "East US"
  resource_group_name = azurerm_resource_group.demo.name
  dns_prefix          = "demo"

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_DS2_v2"
  }

  identity {
    type = "SystemAssigned"
  }
}
```

Then:

```bash id="7bx5ja"
terraform apply
kubectl get nodes
```

Docs:

* [floci-az Docs](https://floci.io/floci-az/?utm_source=chatgpt.com)
* [floci-az GitHub](https://github.com/floci-io/floci-az?utm_source=chatgpt.com)

[1]: https://floci.io/floci-az/?utm_source=chatgpt.com "Floci-AZ"
[2]: https://www.reddit.com/r/AZURE/comments/1tlk3im/flociaz_030_opensource_local_azure_emulator_now/?utm_source=chatgpt.com "floci-az 0.3.0 > open-source local Azure emulator, now with Cosmos DB SQL API and AKS"
