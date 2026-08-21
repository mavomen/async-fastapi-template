"""Tests for Terraform module structure and HCL validity."""

from __future__ import annotations

import re
from pathlib import Path

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform"


class TestTerraformStructure:
    def test_main_tf_exists(self) -> None:
        assert (TERRAFORM_DIR / "main.tf").exists()

    def test_variables_tf_exists(self) -> None:
        assert (TERRAFORM_DIR / "variables.tf").exists()

    def test_outputs_tf_exists(self) -> None:
        assert (TERRAFORM_DIR / "outputs.tf").exists()

    def test_versions_tf_exists(self) -> None:
        assert (TERRAFORM_DIR / "versions.tf").exists()

    def test_tfvars_example_exists(self) -> None:
        assert (TERRAFORM_DIR / "terraform.tfvars.example").exists()


class TestTerraformModules:
    MODULES = ["vpc", "database", "cache", "ecs", "alb"]

    def test_all_modules_have_main_tf(self) -> None:
        for module in self.MODULES:
            assert (TERRAFORM_DIR / "modules" / module / "main.tf").exists(), (
                f"Missing modules/{module}/main.tf"
            )

    def test_all_modules_have_variables_tf(self) -> None:
        for module in self.MODULES:
            assert (TERRAFORM_DIR / "modules" / module / "variables.tf").exists(), (
                f"Missing modules/{module}/variables.tf"
            )

    def test_all_modules_have_outputs_tf(self) -> None:
        for module in self.MODULES:
            assert (TERRAFORM_DIR / "modules" / module / "outputs.tf").exists(), (
                f"Missing modules/{module}/outputs.tf"
            )


class TestTerraformHCL:
    def _read(self, path: str) -> str:
        return (TERRAFORM_DIR / path).read_text()

    def test_provider_aws_configured(self) -> None:
        content = self._read("main.tf")
        assert 'provider "aws"' in content or "provider aws" in content

    def test_required_version_constraint(self) -> None:
        versions = self._read("versions.tf")
        assert re.search(r"terraform\s*\{\s*required_version", versions)

    def test_module_vpc_called(self) -> None:
        assert re.search(r'module\s*"vpc"', self._read("main.tf"))

    def test_module_database_called(self) -> None:
        assert re.search(r'module\s*"database"', self._read("main.tf"))

    def test_module_cache_called(self) -> None:
        assert re.search(r'module\s*"cache"', self._read("main.tf"))

    def test_module_ecs_called(self) -> None:
        assert re.search(r'module\s*"ecs"', self._read("main.tf"))

    def test_module_alb_called(self) -> None:
        assert re.search(r'module\s*"alb"', self._read("main.tf"))

    def test_outputs_define_alb_dns(self) -> None:
        assert "alb_dns_name" in self._read("outputs.tf")

    def test_outputs_define_rds_endpoint(self) -> None:
        assert "rds_endpoint" in self._read("outputs.tf")

    def test_outputs_define_redis_endpoint(self) -> None:
        assert "redis_endpoint" in self._read("outputs.tf")


class TestTerraformModuleContent:
    def test_database_has_security_group(self) -> None:
        db_main = (TERRAFORM_DIR / "modules" / "database" / "main.tf").read_text()
        assert "aws_security_group" in db_main

    def test_database_has_password_variable(self) -> None:
        db_vars = (TERRAFORM_DIR / "modules" / "database" / "variables.tf").read_text()
        assert "db_password" in db_vars

    def test_database_has_reader_support(self) -> None:
        db_main = (TERRAFORM_DIR / "modules" / "database" / "main.tf").read_text()
        assert "reader" in db_main.lower() or "replica" in db_main.lower()

    def test_ecs_has_health_check(self) -> None:
        ecs_main = (TERRAFORM_DIR / "modules" / "ecs" / "main.tf").read_text()
        assert "health" in ecs_main.lower()

    def test_ecs_has_circuit_breaker(self) -> None:
        ecs_main = (TERRAFORM_DIR / "modules" / "ecs" / "main.tf").read_text()
        assert "circuit_breaker" in ecs_main.lower()

    def test_alb_has_https_listener(self) -> None:
        alb_main = (TERRAFORM_DIR / "modules" / "alb" / "main.tf").read_text()
        assert "443" in alb_main

    def test_vpc_has_nat_gateway(self) -> None:
        vpc_main = (TERRAFORM_DIR / "modules" / "vpc" / "main.tf").read_text()
        assert "nat" in vpc_main.lower()

    def test_cache_has_security_group(self) -> None:
        cache_main = (TERRAFORM_DIR / "modules" / "cache" / "main.tf").read_text()
        assert "security_group" in cache_main.lower() or "aws_security_group" in cache_main

    def test_cache_has_memory_policy(self) -> None:
        cache_main = (TERRAFORM_DIR / "modules" / "cache" / "main.tf").read_text()
        assert "allkeys-lru" in cache_main

    def test_vpc_outputs_subnet_ids(self) -> None:
        vpc_outputs = (TERRAFORM_DIR / "modules" / "vpc" / "outputs.tf").read_text()
        assert "public_subnets" in vpc_outputs
        assert "private_subnets" in vpc_outputs

    def test_database_outputs_reader_endpoint(self) -> None:
        db_outputs = (TERRAFORM_DIR / "modules" / "database" / "outputs.tf").read_text()
        assert "reader_endpoint" in db_outputs

    def test_tfvars_has_all_required_vars(self) -> None:
        tfvars = (TERRAFORM_DIR / "terraform.tfvars.example").read_text()
        required = [
            "environment",
            "project_name",
            "db_username",
            "db_password",
            "container_image",
            "container_port",
        ]
        for var in required:
            assert var in tfvars, f"Missing {var} in terraform.tfvars.example"
