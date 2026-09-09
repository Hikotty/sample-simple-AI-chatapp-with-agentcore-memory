output "app_url" {
  value = "http://${aws_eip.app.public_ip}/"
}

output "instance_id" {
  value = aws_instance.app.id
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.app.id
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}

output "db_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "region" {
  value = var.region
}
