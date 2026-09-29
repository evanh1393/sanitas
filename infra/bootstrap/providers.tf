terraform {
  required_version = ">= 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "sanitas-tfstate-551626544335"
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1"
    profile      = "sanitas"
    kms_key_id   = "alias/sanitas"
    use_lockfile = true
  }

}

provider "aws" {
  region  = "us-east-1"
  profile = "sanitas"
}

