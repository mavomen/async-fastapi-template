variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "development"
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "fastapi-template"
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "fastapi_db"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "container_image" {
  description = "Docker image URI for the ECS task"
  type        = string
}

variable "container_port" {
  description = "Port exposed by the container"
  type        = number
  default     = 8000
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "domain_name" {
  description = "Custom domain name for the ALB (empty to skip)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (empty to skip)"
  type        = string
  default     = ""
}

variable "allowed_origins" {
  description = "Allowed CORS origins"
  type        = list(string)
  default     = ["*"]
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "backup_retention_period" {
  description = "RDS backup retention period in days"
  type        = number
  default     = 7
}

variable "single_nat_gateway" {
  description = "Use a single NAT gateway (cost-effective for dev)"
  type        = bool
  default     = true
}

# ── Multi-Region Failover ──

variable "enable_multi_region" {
  description = "Enable multi-region failover with Route53"
  type        = bool
  default     = false
}

variable "secondary_region" {
  description = "Secondary (DR) AWS region"
  type        = string
  default     = "us-west-2"
}

variable "route53_hosted_zone_id" {
  description = "Route53 hosted zone ID for failover records"
  type        = string
  default     = ""
}

variable "secondary_alb_dns_name" {
  description = "DNS name of the secondary region ALB (for failover alias)"
  type        = string
  default     = ""
}

variable "secondary_alb_zone_id" {
  description = "Route53 zone ID of the secondary region ALB"
  type        = string
  default     = ""
}

variable "enable_cross_region_replica" {
  description = "Create an Aurora read replica in the secondary region"
  type        = bool
  default     = false
}

variable "secondary_vpc_id" {
  description = "VPC ID in the secondary region"
  type        = string
  default     = ""
}

variable "secondary_subnet_ids" {
  description = "Subnet IDs in the secondary region for the replica"
  type        = list(string)
  default     = []
}

variable "secondary_vpc_cidr" {
  description = "VPC CIDR in the secondary region"
  type        = string
  default     = ""
}

variable "secondary_db_instance_class" {
  description = "Instance class for the cross-region Aurora replica"
  type        = string
  default     = "db.r6g.large"
}
