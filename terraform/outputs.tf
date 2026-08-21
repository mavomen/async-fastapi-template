output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "alb_dns_name" {
  description = "DNS name of the application load balancer"
  value       = module.alb.alb_dns_name
}

output "alb_zone_id" {
  description = "Route 53 zone ID of the ALB (for alias records)"
  value       = module.alb.alb_zone_id
}

output "rds_endpoint" {
  description = "RDS primary endpoint"
  value       = module.database.endpoint
}

output "rds_reader_endpoint" {
  description = "RDS read replica endpoint"
  value       = module.database.reader_endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.cache.endpoint
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = module.ecs.service_name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for the ECS service"
  value       = aws_cloudwatch_log_group.app.name
}
