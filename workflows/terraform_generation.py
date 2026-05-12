from crewai import Task

class TerraformGenerationTasks:

    @staticmethod
    def design_architecture_task(agent, requirement):
        return Task(
            description=f'Analyze the following infrastructure requirement and design a MINIMAL architecture.\n'
                        f'Requirement: {requirement}\n'
                        'IMPORTANT: DO NOT add NAT Gateways, Private Subnets, or Multi-AZ unless explicitly requested.\n'
                        '1. Identify necessary providers and resources.\n'
                        '2. You MUST provide a **Mermaid.js diagram string** representing the architecture.\n'
                        '3. The first line of your response must be: PROJECT_SLUG: <slug>',
            expected_output='A detailed architecture document including a Mermaid.js diagram block starting with ```mermaid. The first line must be: PROJECT_SLUG: <slug>',
            agent=agent
        )

    @staticmethod
    def write_terraform_task(agent, project_slug, arch_result):
        return Task(
            description=f'Based on the Architect\'s design, implement the Terraform project: {project_slug}.\n'
                        f'--- ARCHITECTURE DESIGN ---\n{arch_result}\n---------------------------\n'
                        '1. You MUST use the `write_terraform_file` tool for every single file.\n'
                        '2. Structure: Root `main.tf` calling the relevant modules designed by the Architect in the `modules/` directory.\n'
                        '   IMPORTANT: Module sources MUST be simple relative path strings (e.g., source = "./modules/s3"), NOT function calls like file().\n'
                        '3. Do NOT just output text. If you do not call the tool, the files will not exist and the task fails.\n'
                        '4. You MUST create a `README.md` in the project ROOT (not in modules) explaining the setup.\n'
                        f'Project Slug: {project_slug}',
            expected_output=f'A fully populated modular project in output/{project_slug}/ consisting of multiple .tf files.',
            agent=agent
        )
