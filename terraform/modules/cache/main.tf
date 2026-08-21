resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.project_name}-${var.environment}-redis"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${var.project_name}-${var.environment}-redis-subnet-group" }
}

resource "aws_elasticache_parameter_group" "this" {
  name   = "${var.project_name}-${var.environment}-redis"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = { Name = "${var.project_name}-${var.environment}-redis-params" }
}

resource "aws_security_group" "cache" {
  name_prefix = "${var.project_name}-${var.environment}-redis-"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Redis from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = { Name = "${var.project_name}-${var.environment}-redis-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.project_name}-${var.environment}"
  description          = "Redis cluster for ${var.project_name}"

  engine               = "redis"
  engine_version       = "7"
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.this.name
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [aws_security_group.cache.id]

  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.num_cache_nodes > 1

  at_rest_encryption_enabled = true
  transit_encryption_mode    = "preferred"

  maintenance_window       = "sun:05:00-sun:06:00"
  snapshot_retention_limit = 3

  tags = { Name = "${var.project_name}-${var.environment}-redis" }
}
