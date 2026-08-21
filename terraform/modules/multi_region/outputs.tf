output "health_check_id" {
  description = "Route53 health check ID for the primary endpoint"
  value       = aws_route53_health_check.primary.id
}

output "primary_record_fqdn" {
  description = "FQDN of the primary failover record"
  value       = aws_route53_record.primary.fqdn
}

output "secondary_record_fqdn" {
  description = "FQDN of the secondary failover record (empty if not created)"
  value       = try(aws_route53_record.secondary[0].fqdn, "")
}

output "secondary_cluster_endpoint" {
  description = "Endpoint of the cross-region Aurora replica (empty if not created)"
  value       = try(aws_rds_cluster.secondary[0].endpoint, "")
}

output "secondary_cluster_reader_endpoint" {
  description = "Reader endpoint of the cross-region Aurora replica"
  value       = try(aws_rds_cluster.secondary[0].reader_endpoint, "")
}

output "secondary_security_group_id" {
  description = "Security group ID for the cross-region replica"
  value       = try(aws_security_group.secondary_db[0].id, "")
}
