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
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "ALB security group ID to allow ingress from"
  type        = string
}

variable "container_image" {
  description = "Docker image URI"
  type        = string
}

variable "container_port" {
  description = "Port exposed by the container"
  type        = number
  default     = 8000
}

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 2
}

variable "task_cpu" {
  description = "Fargate task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB"
  type        = number
  default     = 1024
}

variable "health_check_path" {
  description = "Health check endpoint path"
  type        = string
  default     = "/healthz"
}

variable "environment_variables" {
  description = "Environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "execution_role_arn" {
  description = "Custom ECS execution role ARN (leave empty to create one)"
  type        = string
  default     = ""
}

variable "task_role_arn" {
  description = "Custom ECS task role ARN (leave empty to create one)"
  type        = string
  default     = ""
}

variable "target_group_arn" {
  description = "ALB target group ARN"
  type        = string
}
