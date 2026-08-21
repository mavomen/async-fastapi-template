variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "primary_region" {
  description = "Primary AWS region"
  type        = string
}

variable "secondary_region" {
  description = "Secondary (DR) AWS region"
  type        = string
}

variable "domain_name" {
  description = "Root domain for Route53 failover records (e.g. example.com)"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for the domain"
  type        = string
}

# ── Primary region references ──

variable "primary_alb_dns_name" {
  description = "DNS name of the primary ALB"
  type        = string
}

variable "primary_alb_zone_id" {
  description = "Route53 zone ID of the primary ALB"
  type        = string
}

# ── Secondary region references ──

variable "secondary_alb_dns_name" {
  description = "DNS name of the secondary (DR) ALB"
  type        = string
  default     = ""
}

variable "secondary_alb_zone_id" {
  description = "Route53 zone ID of the secondary ALB"
  type        = string
  default     = ""
}

# ── Database cross-region replication ──

variable "enable_cross_region_replica" {
  description = "Create an Aurora read replica in the secondary region"
  type        = bool
  default     = false
}

variable "primary_cluster_arn" {
  description = "ARN of the primary Aurora cluster (for cross-region replica)"
  type        = string
  default     = ""
}

variable "secondary_vpc_id" {
  description = "VPC ID in the secondary region for the replica"
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
  description = "Instance class for the cross-region replica"
  type        = string
  default     = "db.r6g.large"
}
