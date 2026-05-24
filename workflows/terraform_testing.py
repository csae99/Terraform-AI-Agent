from crewai import Task

class TerraformTestingTasks:

    @staticmethod
    def behavior_testing_task(agent, project_slug):
        return Task(
            description=f"Verify the runtime behavior of the deployed infrastructure in workspace `{project_slug}`.\n"
                        f"1. Check the resources configured for the project.\n"
                        f"2. Use `verify_s3_bucket` for any S3 buckets created to ensure they are writable and readable.\n"
                        f"3. Use `verify_aws_resource_exists` to verify database tables (DynamoDB), message queues (SQS), virtual servers (EC2), functions (Lambda), or databases (RDS).\n"
                        f"4. If any public HTTP endpoints, APIs, or website URLs are provisioned (or expected to run in Floci), use `verify_http_endpoint` to probe them.\n"
                        f"5. Report a detailed summary of all tests performed, listing successful validations and any failures.",
            expected_output="A QA validation report summarizing the health and reachability of all deployed resources.",
            agent=agent
        )
