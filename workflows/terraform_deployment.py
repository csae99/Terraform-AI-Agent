from crewai import Task

class TerraformDeploymentTasks:

    @staticmethod
    def deployment_task(agent, project_slug):
        return Task(
            description=f'Execute the live deployment for the `{project_slug}` workspace.\n'
                        f'1. Run `run_terraform_plan` to verify the changes.\n'
                        f'2. If the plan output shows resources to be created (e.g. "Plan: 3 to add"), '
                        f'you MUST IMMEDIATELY run `run_terraform_apply` to provision them.\n'
                        f'3. DO NOT repeat the plan more than once. If it looks correct, apply it.\n'
                        f'4. If any API errors occur, report the EXACT error log for self-healing.\n'
                        f'5. Return the final output (Bucket Name, ARN, etc.) if successful.',
            expected_output='A deployment status report confirming the resources are LIVE on AWS.',
            agent=agent
        )

    @staticmethod
    def decommissioning_task(agent, project_slug):
        return Task(
            description=f'Permanently destroy all infrastructure in the `{project_slug}` workspace.\n'
                        f'1. Use the `run_terraform_destroy` tool.\n'
                        f'2. Ensure all resources are successfully removed.\n'
                        f'3. If any "DependencyViolation" or "BucketNotEmpty" errors occur, '
                        f'report the EXACT log for remediation.',
            expected_output='A confirmation report that the infrastructure has been successfully destroyed.',
            agent=agent
        )

    @staticmethod
    def drift_detection_task(agent, project_slug):
        return Task(
            description=f'Perform a drift audit for the `{project_slug}` workspace.\n'
                        f'1. Use the `detect_drift` tool.\n'
                        f'2. Identify any resources that have been manually changed, added, or deleted in the cloud.\n'
                        f'3. Provide a clear summary of the drift status.',
            expected_output='A summary report indicating if the project is "In Sync" or "Drift Detected", with a list of changes.',
            agent=agent
        )
