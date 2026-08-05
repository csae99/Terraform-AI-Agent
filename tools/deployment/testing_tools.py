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
    def verify_http_endpoint(url: str, expected_status: int = 200, timeout: int = 5, sla_max_latency: float = 2.0) -> str:
        """
        Sends an HTTP GET request to verify if an endpoint is reachable and returning the expected status code.
        Supports automatic retry with exponential backoff for transient errors (e.g. status codes 429, 502, 503, 504, or connection errors).
        Enforces an SLA latency check.
        Args:
            url (str): The full URL to test.
            expected_status (int): The expected HTTP status code (default: 200).
            timeout (int): Timeout in seconds.
            sla_max_latency (float): Maximum allowed latency in seconds for SLA check.
        """
        import time
        max_retries = 3
        base_delay = 1.0

        is_in_docker = os.path.exists('/.dockerenv') or os.environ.get("RUNNING_IN_DOCKER") == "true"
        target_url = url
        if is_in_docker:
            if "localhost" in url:
                target_url = url.replace("localhost", "floci")
            elif "127.0.0.1" in url:
                target_url = url.replace("127.0.0.1", "floci")

        for attempt in range(max_retries + 1):
            start_time = time.time()
            try:
                response = requests.get(target_url, timeout=timeout)
                latency = time.time() - start_time
                status_code = response.status_code
                is_transient = status_code in [429, 502, 503, 504]
                
                if not is_transient:
                    sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
                    if status_code == expected_status:
                        return f"✅ HTTP Endpoint Verification Succeeded: {url} returned status {status_code}{sla_status}."
                    else:
                        return f"❌ HTTP Endpoint Verification Failed: {url} returned status {status_code} (Expected {expected_status}){sla_status}."
                
                err_msg = f"HTTP status {status_code}"
            except requests.exceptions.RequestException as e:
                latency = time.time() - start_time
                is_transient = True
                err_msg = str(e)
            
            if attempt < max_retries:
                sleep_time = base_delay * (2 ** attempt)
                print(f"[QA Engine] Transient error encountered ({err_msg}). Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                return f"❌ HTTP Endpoint Verification Failed: Transient error persisted after {max_retries} retries. Last error: {err_msg}."

    @tool("AWS S3 Bucket Verification")
    def verify_s3_bucket(bucket_name: str, sla_max_latency: float = 2.0) -> str:
        """
        Verifies that an S3 bucket exists, is accessible, and can perform write/read operations.
        Includes an SLA latency check.
        Args:
            bucket_name (str): The name of the S3 bucket to verify.
            sla_max_latency (float): Maximum allowed latency in seconds for SLA check.
        """
        import time
        start_time = time.time()
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
            
            latency = time.time() - start_time
            sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
            
            if content == "Verification successful":
                return f"✅ S3 Bucket '{bucket_name}' verified successfully (Read/Write test passed){sla_status}."
            else:
                return f"❌ S3 Bucket '{bucket_name}' verification failed: Read content did not match."
        except Exception as e:
            return f"❌ S3 Bucket '{bucket_name}' verification failed: {str(e)}"

    @tool("AWS Resource Exists Verification")
    def verify_aws_resource_exists(service: str, resource_name_or_id: str, sla_max_latency: float = 2.0) -> str:
        """
        Verifies if a specific AWS resource exists and is active.
        Includes an SLA latency check.
        Args:
            service (str): The AWS service name (e.g., 'dynamodb', 'sqs', 'ec2', 'lambda', 'rds').
            resource_name_or_id (str): The identifier of the resource (e.g. table name, queue URL or name, instance ID, etc.).
            sla_max_latency (float): Maximum allowed latency in seconds for SLA check.
        """
        import time
        service = service.lower()
        start_time = time.time()
        try:
            client = TestingTools._get_aws_client(service)
            if service == "dynamodb":
                resp = client.describe_table(TableName=resource_name_or_id)
                status = resp['Table']['TableStatus']
                latency = time.time() - start_time
                sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
                return f"✅ DynamoDB Table '{resource_name_or_id}' exists. Status: {status}{sla_status}."
            elif service == "sqs":
                if resource_name_or_id.startswith("http"):
                    resp = client.get_queue_attributes(QueueUrl=resource_name_or_id, AttributeNames=['All'])
                else:
                    resp = client.get_queue_url(QueueName=resource_name_or_id)
                latency = time.time() - start_time
                sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
                return f"✅ SQS Queue '{resource_name_or_id}' exists and is accessible{sla_status}."
            elif service == "ec2":
                resp = client.describe_instances(InstanceIds=[resource_name_or_id])
                state = resp['Reservations'][0]['Instances'][0]['State']['Name']
                latency = time.time() - start_time
                sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
                return f"✅ EC2 Instance '{resource_name_or_id}' exists. State: {state}{sla_status}."
            elif service == "lambda":
                resp = client.get_function(FunctionName=resource_name_or_id)
                state = resp.get('Configuration', {}).get('State', 'Active')
                latency = time.time() - start_time
                sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
                return f"✅ Lambda Function '{resource_name_or_id}' exists. State: {state}{sla_status}."
            elif service == "rds":
                resp = client.describe_db_instances(DBInstanceIdentifier=resource_name_or_id)
                status = resp['DBInstances'][0]['DBInstanceStatus']
                latency = time.time() - start_time
                sla_status = f" (SLA Check Passed: {latency:.3f}s)" if latency <= sla_max_latency else f" (⚠️ SLA Warning: Latency was {latency:.3f}s, exceeding target of {sla_max_latency}s)"
                return f"✅ RDS DB Instance '{resource_name_or_id}' exists. Status: {status}{sla_status}."
            else:
                latency = time.time() - start_time
                return f"⚠️ Service '{service}' verification is not specifically implemented. Checking generic client connection took {latency:.3f}s."
        except Exception as e:
            return f"❌ Resource '{resource_name_or_id}' in service '{service}' verification failed: {str(e)}"
