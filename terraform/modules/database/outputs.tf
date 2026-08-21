output "endpoint" {
  description = "RDS cluster writer endpoint"
  value       = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  description = "RDS cluster reader endpoint"
  value       = aws_rds_cluster.this.reader_endpoint
}

output "port" {
  description = "RDS port"
  value       = aws_rds_cluster.this.port
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret for the master password"
  value       = aws_rds_cluster.this.master_user_secret[0].secret_arn
}

output "security_group_id" {
  description = "Security group ID for the RDS cluster"
  value       = aws_security_group.database.id
}

output "cluster_arn" {
  description = "ARN of the Aurora cluster (for global database replication)"
  value       = aws_rds_cluster.this.arn
}
