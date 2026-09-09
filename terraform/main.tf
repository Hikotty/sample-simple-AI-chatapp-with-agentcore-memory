terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project = var.project
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name   = "${var.project}-${random_id.suffix.hex}"
  azs    = slice(data.aws_availability_zones.available.names, 0, 2)
  my_ip  = "${chomp(var.my_ip)}/32"
}
