"""Tests for multi-region failover Terraform module."""

from __future__ import annotations

import re
from pathlib import Path

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform"
MULTI_REGION_DIR = TERRAFORM_DIR / "modules" / "multi_region"


class TestMultiRegionModuleStructure:
    """Module directory and required files exist."""

    def test_module_directory_exists(self) -> None:
        assert MULTI_REGION_DIR.exists(), "Missing terraform/modules/multi_region/"

    def test_main_tf_exists(self) -> None:
        assert (MULTI_REGION_DIR / "main.tf").exists()

    def test_variables_tf_exists(self) -> None:
        assert (MULTI_REGION_DIR / "variables.tf").exists()

    def test_outputs_tf_exists(self) -> None:
        assert (MULTI_REGION_DIR / "outputs.tf").exists()


class TestRootModuleWiring:
    """Root main.tf references the multi_region module."""

    def test_multi_region_module_called(self) -> None:
        main = (TERRAFORM_DIR / "main.tf").read_text()
        assert re.search(r'module\s*"multi_region"', main)

    def test_multi_region_conditional_on_flag(self) -> None:
        main = (TERRAFORM_DIR / "main.tf").read_text()
        assert re.search(r"var\.enable_multi_region", main)

    def test_multi_region_passes_providers(self) -> None:
        main = (TERRAFORM_DIR / "main.tf").read_text()
        assert "aws.secondary" in main

    def test_enable_multi_region_variable_exists(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        assert "enable_multi_region" in variables

    def test_secondary_region_variable_exists(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        assert "secondary_region" in variables

    def test_secondary_alb_variables_exist(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        assert "secondary_alb_dns_name" in variables
        assert "secondary_alb_zone_id" in variables

    def test_cross_region_replica_variables_exist(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        assert "enable_cross_region_replica" in variables
        assert "secondary_vpc_id" in variables
        assert "secondary_subnet_ids" in variables

    def test_database_outputs_cluster_arn(self) -> None:
        db_outputs = (TERRAFORM_DIR / "modules" / "database" / "outputs.tf").read_text()
        assert "cluster_arn" in db_outputs

    def test_root_outputs_failover_records(self) -> None:
        outputs = (TERRAFORM_DIR / "outputs.tf").read_text()
        assert "route53_health_check_id" in outputs
        assert "failover_primary_fqdn" in outputs
        assert "failover_secondary_fqdn" in outputs
        assert "secondary_cluster_endpoint" in outputs


class TestSecondaryProvider:
    """Secondary AWS provider is configured in versions.tf."""

    def test_secondary_provider_alias(self) -> None:
        versions = (TERRAFORM_DIR / "versions.tf").read_text()
        assert re.search(r'provider\s*"aws"', versions)
        assert 'alias  = "secondary"' in versions or 'alias = "secondary"' in versions

    def test_secondary_provider_region_variable(self) -> None:
        versions = (TERRAFORM_DIR / "versions.tf").read_text()
        assert "var.secondary_region" in versions


class TestRoute53FailoverContent:
    """Module main.tf contains Route53 failover resources."""

    def _read(self) -> str:
        return (MULTI_REGION_DIR / "main.tf").read_text()

    def test_has_route53_health_check(self) -> None:
        content = self._read()
        assert "aws_route53_health_check" in content

    def test_health_check_uses_https(self) -> None:
        content = self._read()
        assert "HTTPS" in content

    def test_health_check_hits_healthz(self) -> None:
        content = self._read()
        assert "/healthz" in content

    def test_has_failover_records(self) -> None:
        content = self._read()
        assert "failover_routing_policy" in content

    def test_primary_record_is_primary(self) -> None:
        content = self._read()
        assert re.search(r'type\s*=\s*"PRIMARY"', content)

    def test_secondary_record_is_secondary(self) -> None:
        content = self._read()
        assert re.search(r'type\s*=\s*"SECONDARY"', content)

    def test_uses_alias_records(self) -> None:
        content = self._read()
        assert "alias {" in content

    def test_evaluate_target_health(self) -> None:
        content = self._read()
        assert "evaluate_target_health = true" in content


class TestCrossRegionReplicaContent:
    """Module main.tf contains cross-region Aurora replica resources."""

    def _read(self) -> str:
        return (MULTI_REGION_DIR / "main.tf").read_text()

    def test_has_aurora_replica_cluster(self) -> None:
        content = self._read()
        assert "aws_rds_cluster" in content
        assert "secondary" in content

    def test_uses_global_cluster(self) -> None:
        content = self._read()
        assert "global_cluster_identifier" in content

    def test_has_replica_instance(self) -> None:
        content = self._read()
        assert "aws_rds_cluster_instance" in content

    def test_has_security_group(self) -> None:
        content = self._read()
        assert "aws_security_group" in content

    def test_has_db_subnet_group(self) -> None:
        content = self._read()
        assert "aws_db_subnet_group" in content

    def test_replica_conditional(self) -> None:
        content = self._read()
        assert "enable_cross_region_replica" in content

    def test_uses_secondary_provider(self) -> None:
        content = self._read()
        assert "provider = aws.secondary" in content

    def test_skip_final_snapshot_dev(self) -> None:
        content = self._read()
        assert "skip_final_snapshot" in content


class TestModuleOutputs:
    """Module outputs.tf defines expected outputs."""

    def _read(self) -> str:
        return (MULTI_REGION_DIR / "outputs.tf").read_text()

    def test_has_health_check_id_output(self) -> None:
        assert "health_check_id" in self._read()

    def test_has_primary_record_fqdn(self) -> None:
        assert "primary_record_fqdn" in self._read()

    def test_has_secondary_record_fqdn(self) -> None:
        assert "secondary_record_fqdn" in self._read()

    def test_has_secondary_cluster_endpoint(self) -> None:
        assert "secondary_cluster_endpoint" in self._read()

    def test_has_secondary_security_group(self) -> None:
        assert "secondary_security_group_id" in self._read()


class TestModuleVariables:
    """Module variables.tf defines expected inputs."""

    def _read(self) -> str:
        return (MULTI_REGION_DIR / "variables.tf").read_text()

    def test_has_domain_name(self) -> None:
        assert "domain_name" in self._read()

    def test_has_hosted_zone_id(self) -> None:
        assert "hosted_zone_id" in self._read()

    def test_has_primary_alb_dns(self) -> None:
        assert "primary_alb_dns_name" in self._read()

    def test_has_primary_alb_zone(self) -> None:
        assert "primary_alb_zone_id" in self._read()

    def test_has_secondary_region(self) -> None:
        assert "secondary_region" in self._read()

    def test_has_replica_flag(self) -> None:
        assert "enable_cross_region_replica" in self._read()

    def test_has_replica_instance_class(self) -> None:
        assert "secondary_db_instance_class" in self._read()


class TestMultiRegionSafety:
    """Multi-region configuration is safe by default (disabled)."""

    def test_multi_region_disabled_by_default(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        pattern = r'variable\s+"enable_multi_region"\s*\{[^}]*default\s*=\s*(true|false)'
        match = re.search(pattern, variables, re.DOTALL)
        assert match, "enable_multi_region variable missing default"
        assert match.group(1) == "false", "enable_multi_region should default to false"

    def test_cross_region_replica_disabled_by_default(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        pattern = r'variable\s+"enable_cross_region_replica"\s*\{[^}]*default\s*=\s*(true|false)'
        match = re.search(pattern, variables, re.DOTALL)
        assert match, "enable_cross_region_replica variable missing default"
        assert match.group(1) == "false", "enable_cross_region_replica should default to false"
