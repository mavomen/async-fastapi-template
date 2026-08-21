terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
      configuration_aliases = [aws.secondary]
    }
  }
}

# ──────────────────────────────────────────────────────
# Route53 Health Check (primary ALB /healthz)
# ──────────────────────────────────────────────────────

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_alb_dns_name
  port               = 443
  type               = "HTTPS"
  resource_path      = "/healthz"
  failure_threshold  = 3
  request_interval   = 10

  tags = {
    Name        = "${var.project_name}-${var.environment}-primary-health"
    Environment = var.environment
  }
}

# ──────────────────────────────────────────────────────
# Route53 Failover Records
# ──────────────────────────────────────────────────────

resource "aws_route53_record" "primary" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  alias {
    name                   = var.primary_alb_dns_name
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }

  set_identifier  = "primary-${var.primary_region}"
  health_check_id = aws_route53_health_check.primary.id
}

resource "aws_route53_record" "secondary" {
  count = var.secondary_alb_dns_name != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  alias {
    name                   = var.secondary_alb_dns_name
    zone_id                = var.secondary_alb_zone_id
    evaluate_target_health = true
  }

  set_identifier = "secondary-${var.secondary_region}"
}

# ──────────────────────────────────────────────────────
# Cross-Region Aurora Read Replica
# ──────────────────────────────────────────────────────

resource "aws_security_group" "secondary_db" {
  count = var.enable_cross_region_replica ? 1 : 0

  provider    = aws.secondary
  name_prefix = "${var.project_name}-${var.environment}-db-replica-"
  description = "Security group for cross-region Aurora replica"
  vpc_id      = var.secondary_vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.secondary_vpc_cidr]
    description = "PostgreSQL from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = { Name = "${var.project_name}-${var.environment}-db-replica-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_rds_cluster" "secondary" {
  count = var.enable_cross_region_replica ? 1 : 0

  provider = aws.secondary

  cluster_identifier = "${var.project_name}-${var.environment}-replica"

  # Global database cluster replication
  global_cluster_identifier = var.primary_cluster_arn

  engine         = "aurora-postgresql"
  engine_version = "16"

  db_subnet_group_name   = aws_db_subnet_group.secondary[0].name
  vpc_security_group_ids = [aws_security_group.secondary_db[0].id]

  skip_final_snapshot = true
  deletion_protection = false

  tags = {
    Name        = "${var.project_name}-${var.environment}-replica-cluster"
    Environment = var.environment
  }
}

resource "aws_db_subnet_group" "secondary" {
  count = var.enable_cross_region_replica ? 1 : 0

  provider   = aws.secondary
  name       = "${var.project_name}-${var.environment}-db-replica"
  subnet_ids = var.secondary_subnet_ids
  tags       = { Name = "${var.project_name}-${var.environment}-db-replica-subnet-group" }
}

resource "aws_rds_cluster_instance" "secondary" {
  count = var.enable_cross_region_replica ? 1 : 0

  provider          = aws.secondary
  identifier         = "${var.project_name}-${var.environment}-replica-1"
  cluster_identifier = aws_rds_cluster.secondary[0].id
  instance_class     = var.secondary_db_instance_class
  engine             = aws_rds_cluster.secondary[0].engine
  engine_version     = aws_rds_cluster.secondary[0].engine_version

  performance_insights_enabled = true

  tags = { Name = "${var.project_name}-${var.environment}-replica-instance" }
}
