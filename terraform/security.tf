resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "Chat app EC2"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-app" }
}

# HTTP は自分の IP からのみ
resource "aws_vpc_security_group_ingress_rule" "app_http_from_me" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = local.my_ip
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP from operator IP"
}

resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "db" {
  name        = "${local.name}-db"
  description = "RDS PostgreSQL"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-db" }
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "db_all" {
  security_group_id = aws_security_group.db.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# CloudFront のオリジン向け IP レンジからの HTTP を許可（/api/* の転送用）
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_vpc_security_group_ingress_rule" "app_http_from_cloudfront" {
  security_group_id = aws_security_group.app.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP from CloudFront origin-facing ranges"
}
