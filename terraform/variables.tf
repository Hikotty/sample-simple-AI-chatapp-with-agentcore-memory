variable "project" {
  description = "Resource name prefix"
  type        = string
  default     = "memchat"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile used by Terraform"
  type        = string
  default     = "default"
}

variable "my_ip" {
  description = "Public IPv4 address allowed to reach the app (HTTP)"
  type        = string
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "bedrock_model_id" {
  description = "Inference profile ID used by the app"
  type        = string
  default     = "us.anthropic.claude-sonnet-5"
}

variable "agentcore_memory_id" {
  description = "AgentCore Memory ID. Empty disables the memory integration."
  type        = string
  default     = ""
}
