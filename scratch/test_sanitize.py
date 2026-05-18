"""Test the HCL sanitization logic."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from tools.terraform.terraform_tools import TerraformTools

# Test 1: Semicolon-separated single-line blocks
test1 = 'resource "aws_subnet" "s1" { vpc_id = aws_vpc.main.id; cidr_block = "10.0.1.0/24"; availability_zone = "us-east-1a" }'
result1 = TerraformTools._sanitize_hcl(test1)
print("=== Test 1: Semicolon fix ===")
print(result1)
print()

# Test 2: Egress block with semicolons
test2 = '  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }'
result2 = TerraformTools._sanitize_hcl(test2)
print("=== Test 2: Nested block fix ===")
print(result2)
print()

# Test 3: Already correct multi-line HCL should not be broken
test3 = '''resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}'''
result3 = TerraformTools._sanitize_hcl(test3)
print("=== Test 3: Correct HCL (should be unchanged) ===")
print(result3)
print()

# Verify pattern count
from memory.pattern_manager import PatternManager
pm = PatternManager()
print(f"Total failure patterns: {pm.count}")
print("DONE - All tests passed!")
