variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Public subnet IDs for the ALB"
  type        = list(string)
}

variable "container_port" {
  description = "Container port for the target group"
  type        = number
  default     = 8000
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
