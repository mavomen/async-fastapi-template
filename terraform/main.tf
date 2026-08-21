provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  env = var.environment
  name = "${var.project_name}-${var.environment}"
}

# ──────────────────────────────────────────────────────
# Sub-modules
# ──────────────────────────────────────────────────────

module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  single_nat_gateway = var.single_nat_gateway
}

module "database" {
  source = "./modules/database"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnets
  vpc_cidr              = var.vpc_cidr
  instance_class        = var.db_instance_class
  db_name               = var.db_name
  db_username           = var.db_username
  db_password           = var.db_password
  backup_retention_period = var.backup_retention_period
}

module "cache" {
  source = "./modules/cache"

  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.private_subnets
  vpc_cidr     = var.vpc_cidr
  node_type    = var.redis_node_type
}

module "alb" {
  source = "./modules/alb"

  project_name   = var.project_name
  environment    = var.environment
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.public_subnets
  container_port = var.container_port
  certificate_arn = var.certificate_arn
  allowed_origins = var.allowed_origins
}

module "ecs" {
  source = "./modules/ecs"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnets
  alb_security_group_id = module.alb.security_group_id
  container_image       = var.container_image
  container_port        = var.container_port
  desired_count         = var.desired_count
  target_group_arn      = module.alb.target_group_arn

  environment_variables = {
    DATABASE_URL = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${module.database.endpoint}/${var.db_name}"
    REDIS_URL    = "redis://${module.cache.endpoint}:6379/0"
  }
}

# ──────────────────────────────────────────────────────
# CloudWatch
# ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = var.log_retention_days
}
