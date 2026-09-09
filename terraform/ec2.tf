data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_eip" "app" {
  domain = "vpc"
  tags   = { Name = local.name }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.al2023_ami.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  metadata_options {
    http_tokens = "required" # IMDSv2 のみ
  }

  root_block_device {
    volume_size = 16
    volume_type = "gp3"
    encrypted   = true
  }

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region               = var.region
    cognito_user_pool_id = aws_cognito_user_pool.main.id
    cognito_client_id    = aws_cognito_user_pool_client.app.id
    db_secret_arn        = aws_db_instance.main.master_user_secret[0].secret_arn
    db_host              = aws_db_instance.main.address
    db_port              = aws_db_instance.main.port
    db_name              = aws_db_instance.main.db_name
    bedrock_model_id     = var.bedrock_model_id
    agentcore_memory_id  = var.agentcore_memory_id
    artifact_bucket      = aws_s3_bucket.artifacts.bucket
  })

  tags = { Name = local.name }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}
