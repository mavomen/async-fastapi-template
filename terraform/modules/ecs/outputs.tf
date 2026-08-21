output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.this.name
}

output "task_definition_arn" {
  description = "ECS task definition ARN"
  value       = aws_ecs_task_definition.this.arn
}

output "security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs.id
}

output "task_role_arn" {
  description = "IAM role ARN for ECS tasks"
  value       = aws_iam_role.task.arn
}

output "execution_role_arn" {
  description = "IAM role ARN for ECS task execution"
  value       = aws_iam_role.execution.arn
}
