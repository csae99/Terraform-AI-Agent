import os
import requests
import boto3
from crewai.tools import tool

class TestingTools:

    @staticmethod
    def _get_aws_client(service_name: str):
        """Helper to create a boto3 client pointing to Floci or live AWS."""
        is_test_local = os.environ.get("TEST_LOCAL") == "true"
        if is_test_local:
            is_in_docker = os.path.exists('/.dockerenv') or os.environ.get("RUNNING_IN_DOCKER") == "true"
            floci_host = "floci" if is_in_docker else "localhost"
            endpoint_url = f"http://{floci_host}:4566"
            return boto3.client(
                service_name,
                region_name="us-east-1",
                aws_access_key_id="mock_access_key",
                aws_secret_access_key="mock_secret_key",
                endpoint_url=endpoint_url
            )
        else:
            return boto3.client(service_name)

    @tool("HTTP Endpoint Verification")
    def verify_http_endpoint(url: str, expected_status: int = 200, timeout: int = 5) -> str:
        """
        Sends an HTTP GET request to verify if an endpoint is reachable and returning the expected status code.
        Args:
            url (str): The full URL to test.
            expected_status (int): The expected HTTP status code (default: 200).
            timeout (int): Timeout in seconds.
        """
        try:
            is_in_docker = os.path.exists('/.dockerenv') or os.environ.get("RUNNING_IN_DOCKER") == "true"
            target_url = url
            if is_in_docker:
                if "localhost" in url:
                    target_url = url.replace("localhost", "floci")
                elif "127.0.0.1" in url:
                    target_url = url.replace("127.0.0.1", "floci")

            response = requests.get(target_url, timeout=timeout)
            if response.status_code == expected_status:
                return f"✅ HTTP Endpoint Verification Succeeded: {url} returned status {response.status_code}."
            else:
                return f"❌ HTTP Endpoint Verification Failed: {url} returned status {response.status_code} (Expected {expected_status})."
        except Exception as e:
            return f"❌ HTTP Endpoint Verification Error for {url}: {str(e)}"

    @tool("AWS S3 Bucket Verification")
    def verify_s3_bucket(bucket_name: str) -> str:
        """
        Verifies that an S3 bucket exists, is accessible, and can perform write/read operations.
        Args:
            bucket_name (str): The name of the S3 bucket to verify.
        """
        try:
            s3 = TestingTools._get_aws_client("s3")
            # 1. Check if bucket exists
            s3.head_bucket(Bucket=bucket_name)
            
            # 2. Try to write a test file
            test_key = "behavior_test_file.txt"
            s3.put_object(Bucket=bucket_name, Key=test_key, Body=b"Verification successful")
            
            # 3. Read it back
            response = s3.get_object(Bucket=bucket_name, Key=test_key)
            content = response['Body'].read().decode('utf-8')
            
            # 4. Clean up
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            
            if content == "Verification successful":
                return f"✅ S3 Bucket '{bucket_name}' verified successfully (Read/Write test passed)."
            else:
                return f"❌ S3 Bucket '{bucket_name}' verification failed: Read content did not match."
        except Exception as e:
            return f"❌ S3 Bucket '{bucket_name}' verification failed: {str(e)}"

    @tool("AWS Resource Exists Verification")
    def verify_aws_resource_exists(service: str, resource_name_or_id: str) -> str:
        """
        Verifies if a specific AWS resource exists and is active.
        Args:
            service (str): The AWS service name (e.g., 'dynamodb', 'sqs', 'ec2', 'lambda', 'rds').
            resource_name_or_id (str): The identifier of the resource (e.g. table name, queue URL or name, instance ID, etc.).
        """
        service = service.lower()
        try:
            client = TestingTools._get_aws_client(service)
            if service == "dynamodb":
                resp = client.describe_table(TableName=resource_name_or_id)
                status = resp['Table']['TableStatus']
                return f"✅ DynamoDB Table '{resource_name_or_id}' exists. Status: {status}."
            elif service == "sqs":
                if resource_name_or_id.startswith("http"):
                    resp = client.get_queue_attributes(QueueUrl=resource_name_or_id, AttributeNames=['All'])
                else:
                    resp = client.get_queue_url(QueueName=resource_name_or_id)
                return f"✅ SQS Queue '{resource_name_or_id}' exists and is accessible."
            elif service == "ec2":
                resp = client.describe_instances(InstanceIds=[resource_name_or_id])
                state = resp['Reservations'][0]['Instances'][0]['State']['Name']
                return f"✅ EC2 Instance '{resource_name_or_id}' exists. State: {state}."
            elif service == "lambda":
                resp = client.get_function(FunctionName=resource_name_or_id)
                state = resp.get('Configuration', {}).get('State', 'Active')
                return f"✅ Lambda Function '{resource_name_or_id}' exists. State: {state}."
            elif service == "rds":
                resp = client.describe_db_instances(DBInstanceIdentifier=resource_name_or_id)
                status = resp['DBInstances'][0]['DBInstanceStatus']
                return f"✅ RDS DB Instance '{resource_name_or_id}' exists. Status: {status}."
            else:
                return f"⚠️ Service '{service}' verification is not specifically implemented. Checking generic client connection..."
        except Exception as e:
            return f"❌ Resource '{resource_name_or_id}' in service '{service}' verification failed: {str(e)}"
